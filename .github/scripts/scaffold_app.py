import os
import json
import time
import random
from pathlib import Path
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError

# 1. Stripped schema: Removed verbose Field descriptions (saves ~150 input/grammar tokens)
class GeneratedFile(BaseModel):
    path: str
    content: str

class ProjectScaffold(BaseModel):
    files: list[GeneratedFile]

def generate_with_backoff(client, model_name, prompt, max_attempts=5):
    delay = 10.0
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[{model_name}] Generation attempt {attempt}/{max_attempts}...")
            chat = client.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ProjectScaffold,
                    temperature=0.1,
                    # Cap output tokens to prevent runway generation
                    max_output_tokens=4096,
                ),
            )
            return chat.send_message(prompt)
        except ServerError as e:
            print(f"Server busy: {e}")
            if attempt == max_attempts:
                raise
            time.sleep(delay + random.uniform(1.0, 3.0))
            delay *= 1.8
        except ClientError as e:
            print(f"Client error ({getattr(e, 'code', 'unknown')}): {e}")
            raise

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    issue_title = os.environ.get("ISSUE_TITLE", "").strip()
    issue_body = os.environ.get("ISSUE_BODY", "").strip()

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    # 2. Compact Prompt: Direct, dense instructions without conversational filler
    prompt = f"""Task: Scaffold a complete, minimal app from this spec.
Title: {issue_title}
Requirements:
{issue_body}

Constraints:
- Output full, working code only (no ellipses, placeholders, or TODOs).
- Keep implementations concise and idiomatic.
- Relative paths only.
"""

    response = generate_with_backoff(client, "gemini-3.6-flash", prompt)

    if not response or not response.text:
        raise RuntimeError("Model returned an empty response.")

    result = ProjectScaffold.model_validate_json(response.text)

    for item in result.files:
        file_path = Path(item.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item.content, encoding="utf-8")
        print(f"Created: {item.path}")

if __name__ == "__main__":
    main()
