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

# Ordered list of live coding/instruct models available on NVIDIA NIM API
DEFAULT_NVIDIA_MODELS = [
    "deepseek-ai/deepseek-v4.1-flash",
    "moonshotai/kimi-k3",
    "nvidia/nemotron-3-super-120b-a12b",
    "google/gemma-4-31b-it",
    "mistralai/codestral-22b-instruct-v0.1",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "mistralai/mistral-large-2-instruct",
    "z-ai/glm-5.3-flash",
]


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


def generate_with_nvidia(
    api_key: str,
    prompt: str,
    preferred_model: Optional[str] = None,
    max_attempts_per_model: int = 2,
) -> ProjectScaffold:
    """Call NVIDIA OpenAI-compatible API with model fallback and fast exponential backoff."""
    client = OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        timeout=120.0,
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

    for model_name in models_to_try:
        delay = 5.0
        for attempt in range(1, max_attempts_per_model + 1):
            try:
                print(f"[NVIDIA: {model_name}] Generation attempt {attempt}/{max_attempts_per_model}...")
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=4096,
                )
                content = completion.choices[0].message.content if completion.choices else None
                if not content:
                    raise RuntimeError(f"Model {model_name} returned an empty message content.")

                scaffold = extract_scaffold_from_text(content)
                if not scaffold.files:
                    raise ValueError(f"Model {model_name} returned an empty files list.")

                print(f"[NVIDIA: {model_name}] Successfully generated {len(scaffold.files)} file(s).")
                return scaffold

            except (RateLimitError, APITimeoutError) as e:
                last_error = e
                print(f"[{model_name}] Rate limit or timeout: {e}")
                if attempt < max_attempts_per_model:
                    sleep_s = delay + random.uniform(0.5, 2.0)
                    print(f"Waiting {sleep_s:.1f}s before retry...")
                    time.sleep(sleep_s)
                    delay *= 2.0
            except BadRequestError as e:
                last_error = e
                print(f"[{model_name}] Bad request / model unavailable ({e}); trying next model...")
                break
            except (APIError, Exception) as e:
                last_error = e
                print(f"[{model_name}] Attempt {attempt} failed: {e}")
                if attempt < max_attempts_per_model:
                    sleep_s = delay + random.uniform(0.5, 2.0)
                    time.sleep(sleep_s)
                    delay *= 2.0

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
        print(f"Created: {file_path.as_posix()}")
        created_count += 1

    if created_count == 0:
        raise RuntimeError("No files were written by the scaffolder.")


if __name__ == "__main__":
    main()
