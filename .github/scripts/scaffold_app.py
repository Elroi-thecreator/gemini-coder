import os
import json
from pathlib import Path
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# 1. Define the exact output schema
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

    client = genai.Client(api_key=api_key)

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

    # 2. Query Gemini with structured output enforcement
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ProjectScaffold,
            temperature=0.2,
        ),
    )

    # 3. Parse and write files to the runner's workspace
    result = ProjectScaffold.model_validate_json(response.text)
    
    print(f"Summary: {result.summary}")
    for item in result.files:
        file_path = Path(item.path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item.content, encoding="utf-8")
        print(f"Created: {item.path}")

if __name__ == "__main__":
    main()
