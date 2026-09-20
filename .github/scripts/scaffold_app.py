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

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    issue_title = os.environ.get("ISSUE_TITLE", "")
    issue_body = os.environ.get("ISSUE_BODY", "")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    # Configure client with built-in HTTP retries for 503 / 429 errors
    retry_options = types.HttpRetryOptions(
        attempts=5,
        initial_delay=3.0,
        max_delay=60.0,
        http_status_codes=[408, 429, 500, 502, 503, 504],
    )
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(retry_options=retry_options)
    )

    prompt = f"""
    You are an expert full-stack software engineer.
    Build an application from scratch based on this specification:
    
    Issue Title: {issue_title}
    Issue Requirements:
    {issue_body}
    
    Rules:
    1. Provide production-ready, functional code (no ellipses, placeholders, or TODOs).
    2. Include all configs, entry points, tests, dependencies (e.g., requirements.txt or package.json), and a README.md.
    3. Ensure file paths are relative to repository root.
    """

    # Candidate models in order of preference
    candidate_models = ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.5-pro"]
    response = None

    for model_name in candidate_models:
        try:
            print(f"Attempting code generation using {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ProjectScaffold,
                    temperature=0.2,
                ),
            )
            print(f"Successfully generated payload with {model_name}.")
            break
        except (ServerError, ClientError) as e:
            print(f"Warning: {model_name} failed with status {getattr(e, 'code', 'unknown')}: {e}")
            print("Retrying with next fallback model in 5 seconds...")
            time.sleep(5)

    if not response or not response.text:
        raise RuntimeError("All candidate models were temporarily unavailable. Please retry shortly.")

    result = ProjectScaffold.model_validate_json(response.text)
    
    print(f"Summary: {result.summary}")
    for item in result.files:
        file_path = Path(item.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item.content, encoding="utf-8")
        print(f"Created: {item.path}")

if __name__ == "__main__":
    main()
