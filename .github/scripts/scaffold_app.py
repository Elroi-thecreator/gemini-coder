import os
import json
import time
import random
from pathlib import Path
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import ServerError, ClientError

class GeneratedFile(BaseModel):
    path: str = Field(description="Relative path of file, e.g., 'src/main.py' or 'Dockerfile'")
    content: str = Field(description="Complete raw source code for this file")

class ProjectScaffold(BaseModel):
    summary: str = Field(description="High-level description of what was implemented")
    files: list[GeneratedFile]

def generate_with_backoff(client, model_name, prompt, max_attempts=5):
    delay = 10.0
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[{model_name}] Generation attempt {attempt}/{max_attempts}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ProjectScaffold,
                ),
            )
            return response
        except ServerError as e:
            print(f"[{model_name}] Server temporarily busy (503/500): {e}")
            if attempt == max_attempts:
                raise
            # Add random jitter to avoid lockstep retries
            sleep_time = delay + random.uniform(1.0, 4.0)
            print(f"Waiting {sleep_time:.1f}s before retrying...")
            time.sleep(sleep_time)
            delay *= 1.8
        except ClientError as e:
            print(f"Fatal client error ({getattr(e, 'code', 'unknown')}): {e}")
            raise

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_body = os.environ.get("ISSUE_BODY", "")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
    You are an expert full-stack software engineer.
    Build an application from scratch based on this specification:
    
    Issue Title: {issue_title}
    Issue Requirements:
    {issue_body}
    
    Rules:
    1. Provide production-ready, functional code (no ellipses, placeholders, or TODOs).
    2. Include all configs, entry points, tests, dependencies, and a README.md.
    3. Ensure file paths are relative to repository root.
    """

    model_name = "gemini-3.6-flash"
    response = generate_with_backoff(client, model_name, prompt)

    if not response or not response.text:
        raise RuntimeError("Model returned an empty response.")

    result = ProjectScaffold.model_validate_json(response.text)
    
    print(f"\n--- Scaffold Completed: {result.summary} ---")
    for item in result.files:
        file_path = Path(item.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item.content, encoding="utf-8")
        print(f"Created: {item.path}")

if __name__ == "__main__":
    main()
