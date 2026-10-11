import json
import os
import random
import re
import time
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from openai import OpenAI, APIError, APITimeoutError, RateLimitError, BadRequestError

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Active models verified on NVIDIA NIM for this account
DEFAULT_NVIDIA_MODELS = [
    "z-ai/glm-5.3-flash",
    "deepseek-ai/deepseek-v4.1-flash",
    "google/gemma-4-31b-it",
    "moonshotai/kimi-k3",
    "moonshotai/kimi-k2.6",
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
]

# Default API response timeout (seconds) - 300s (5 minutes) to allow long reasoning and multi-file code generation
DEFAULT_API_TIMEOUT_SECONDS = float(os.environ.get("NVIDIA_API_TIMEOUT", "300.0"))

# Minimum cooldown interval between any two consecutive API requests (seconds)
BASE_REQUEST_INTERVAL_SECONDS = float(os.environ.get("NVIDIA_REQUEST_INTERVAL", "30.0"))


class GeneratedFile(BaseModel):
    path: str = Field(..., description="Relative file path to create")
    content: str = Field(..., description="Complete file source content")


class ProjectScaffold(BaseModel):
    files: list[GeneratedFile]


def extract_scaffold_from_text(raw_text: str) -> ProjectScaffold:
    """Resiliently extract and validate ProjectScaffold JSON from model output."""
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned empty text.")

    # Remove reasoning blocks (<think>...</think>) if emitted by reasoning models
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

    # Try direct JSON validation first
    try:
        return ProjectScaffold.model_validate_json(cleaned)
    except Exception:
        pass

    # Try extracting from ```json ... ``` or ``` ... ``` code blocks
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        fenced_body = fence_match.group(1).strip()
        try:
            return ProjectScaffold.model_validate_json(fenced_body)
        except Exception:
            try:
                parsed = json.loads(fenced_body)
                if isinstance(parsed, list):
                    return ProjectScaffold(files=parsed)
            except Exception:
                pass

    # Try extracting the outermost JSON object {...}
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace : last_brace + 1]
        try:
            return ProjectScaffold.model_validate_json(candidate)
        except Exception:
            pass

    # Try extracting a top-level JSON array [...]
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        candidate_list = cleaned[first_bracket : last_bracket + 1]
        try:
            parsed_list = json.loads(candidate_list)
            if isinstance(parsed_list, list):
                return ProjectScaffold(files=parsed_list)
        except Exception:
            pass

    raise ValueError(f"Could not parse valid ProjectScaffold JSON from model output:\n{cleaned[:500]}")


def wait_between_requests(base_delay: float = BASE_REQUEST_INTERVAL_SECONDS) -> None:
    """Wait with jitter between consecutive API calls to avoid rate/concurrency throttling."""
    sleep_s = base_delay + random.uniform(2.0, 5.0)
    print(f"Waiting {sleep_s:.1f}s before next API request...", flush=True)
    time.sleep(sleep_s)


def generate_with_nvidia(
    api_key: str,
    prompt: str,
    preferred_model: Optional[str] = None,
    max_attempts_per_model: int = 2,
) -> ProjectScaffold:
    """Call NVIDIA OpenAI-compatible API using streaming and enforced cooldown intervals between requests."""
    client = OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        timeout=DEFAULT_API_TIMEOUT_SECONDS,
        max_retries=0,
    )

    models_to_try = []
    if preferred_model:
        models_to_try.append(preferred_model)
    for m in DEFAULT_NVIDIA_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

    system_prompt = (
        "You are an expert software architect and full-stack developer. "
        "You must respond ONLY with a valid JSON object matching this exact schema:\n"
        '{"files": [{"path": "relative/path/to/file.ext", "content": "full file content"}]}\n'
        "Do not include markdown explanations or any text outside the JSON object."
    )

    last_error: Optional[Exception] = None
    is_first_request = True

    for model_name in models_to_try:
        delay = BASE_REQUEST_INTERVAL_SECONDS
        for attempt in range(1, max_attempts_per_model + 1):
            if not is_first_request:
                wait_between_requests(delay)
            is_first_request = False

            try:
                print(
                    f"[NVIDIA: {model_name}] Streaming generation attempt {attempt}/{max_attempts_per_model} "
                    f"(timeout={DEFAULT_API_TIMEOUT_SECONDS:.0f}s)...",
                    flush=True,
                )
                start_time = time.time()
                stream = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=16384,
                    stream=True,
                )

                content_parts: list[str] = []
                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    text_piece = getattr(delta, "content", None)
                    if text_piece:
                        content_parts.append(text_piece)

                elapsed = time.time() - start_time
                content = "".join(content_parts).strip()
                print(
                    f"[NVIDIA: {model_name}] Stream finished in {elapsed:.1f}s ({len(content)} chars).",
                    flush=True,
                )

                if not content:
                    raise RuntimeError(f"Model {model_name} returned empty streamed content.")

                scaffold = extract_scaffold_from_text(content)
                if not scaffold.files:
                    raise ValueError(f"Model {model_name} returned an empty files list.")

                print(
                    f"[NVIDIA: {model_name}] Successfully generated {len(scaffold.files)} file(s).",
                    flush=True,
                )
                return scaffold

            except (RateLimitError, APITimeoutError) as e:
                last_error = e
                print(f"[{model_name}] Rate limit or timeout: {e}", flush=True)
                delay *= 1.5
            except BadRequestError as e:
                last_error = e
                print(f"[{model_name}] Bad request / model unavailable ({e}); moving to next model...", flush=True)
                break
            except (APIError, Exception) as e:
                last_error = e
                print(f"[{model_name}] Attempt {attempt} failed: {e}", flush=True)
                delay *= 1.5

    raise RuntimeError(f"All NVIDIA model attempts failed. Last error: {last_error}")


def sanitize_relative_path(raw_path: str) -> Path:
    """Ensure the generated path is a safe relative path within the workspace."""
    cleaned = raw_path.strip().replace("\\", "/").lstrip("/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    path_obj = Path(cleaned)
    if not cleaned or ".." in path_obj.parts or path_obj.parts[0] in (".github", "knowledge"):
        raise ValueError(f"Unsafe or reserved file path rejected: {raw_path}")
    return path_obj


def main():
    nvidia_api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    nvidia_model = os.environ.get("NVIDIA_MODEL", "").strip() or None
    issue_title = os.environ.get("ISSUE_TITLE", "").strip() or "Sample Application"
    issue_body = os.environ.get("ISSUE_BODY", "").strip() or "Create a clean, modern single-page web application."

    if not nvidia_api_key:
        raise ValueError("NVIDIA_API_KEY environment variable is not configured.")

    prompt = f"""Task: Scaffold a complete, minimal, self-contained application from this specification.
Title: {issue_title}
Requirements:
{issue_body}

Constraints:
- Output ONLY valid JSON matching {{"files": [{{"path": "...", "content": "..."}}]}}.
- Output full, working, production-ready code only (no ellipses, placeholders, or TODOs).
- Keep implementations concise, modern, responsive, and idiomatic.
- Use relative file paths only (e.g. "index.html", "styles.css", "script.js").
"""

    result = generate_with_nvidia(
        api_key=nvidia_api_key,
        prompt=prompt,
        preferred_model=nvidia_model,
    )

    created_count = 0
    for item in result.files:
        file_path = sanitize_relative_path(item.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item.content, encoding="utf-8")
        print(f"Created: {file_path.as_posix()}", flush=True)
        created_count += 1

    if created_count == 0:
        raise RuntimeError("No files were written by the scaffolder.")


if __name__ == "__main__":
    main()
