import os
import json
import time
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

def call_gemini_with_retries(client, model_name, prompt, max_attempts=4):
    """Retries a specific model with exponential backoff on 503 / 429."""
    delay = 5.0
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"[{model_name}] Attempt {attempt}/{max_attempts}...")
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
            print(f"[{model_name}] ServerError 503/500 encountered: {e}")
            if attempt == max_attempts:
                raise
            print(f"[{model_name}] Backing off for {delay:.1f}s...")
            time.sleep(delay)
            delay *= 2  # Exponential backoff (5s -> 10s -> 20s)
        except ClientError as e:
            # Fatal client error (e.g., 404 or 400), no point retrying this specific model
            print(f"[{model_name}] ClientError encountered: {e}")
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

    # Active Gemini 3 models only
    active_models = ["gemini-3.6-flash", "gemini-3.1-pro-preview"]
    response = None

    for model_name in active_models:
        try:
            response = call_gemini_with_retries(client, model_name, prompt)
            if response and response.text:
                print(f"Successfully generated code using {model_name}.")
                break
        except Exception as e:
            print(f"Skipping {model_name} due to unrecoverable failure: {e}")

    if not response or not response.text:
        raise RuntimeError("Could not generate code across active Gemini models. Please retry.")

    result = ProjectScaffold.model_validate_json(response.text)
    
    print(f"Summary: {result.summary}")
    for item in result.files:
        file_path = Path(item.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item.content, encoding="utf-8")
        print(f"Created: {item.path}")

if __name__ == "__main__":
    main()
