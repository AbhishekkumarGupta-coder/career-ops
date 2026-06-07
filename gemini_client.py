"""
Gemini AI client — central wrapper for all AI calls.
Uses google-genai SDK (free tier: gemini-2.0-flash).
"""

import os
import re
import json
from pathlib import Path
from rich.console import Console
from google import genai
from google.genai import types

console = Console()

_client = None
MODEL = "gemma-4-31b-it"

def _load_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        console.print("[red]❌ GEMINI_API_KEY not found![/red]")
        console.print("Set it in [bold].env[/bold] file or as environment variable.")
        console.print("Get a free key at: [link]https://aistudio.google.com/app/apikey[/link]")
        raise SystemExit(1)
    return api_key

def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=_load_api_key())
    return _client

def ask(prompt: str, system: str = None, stream: bool = True) -> str:
    """Send a prompt to Gemini and return the response text."""
    client = get_client()

    config = types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=8192,
        system_instruction=system if system else None,
    )

    if stream:
        response_text = ""
        for chunk in client.models.generate_content_stream(
            model=MODEL,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                print(chunk.text, end="", flush=True)
                response_text += chunk.text
        print()
        return response_text
    else:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=config,
        )
        return response.text

def ask_json(prompt: str, system: str = None) -> dict:
    """Ask Gemini and parse JSON response."""
    client = get_client()
    json_instruction = (system or "") + "\n\nRespond ONLY with valid JSON. No markdown, no backticks, no explanation."

    config = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=8192,
        system_instruction=json_instruction,
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )
    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Try to extract JSON array
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        # Try to fix truncated JSON by closing open brackets
        fixed = _fix_truncated_json(text)
        if fixed:
            return fixed
        raise ValueError(f"Could not parse JSON from response:\n{text[:200]}")

def _fix_truncated_json(text: str):
    """Attempt to fix truncated JSON by closing open structures."""
    text = text.strip()
    if not text:
        return None
    # Count open/close braces and brackets
    opens  = text.count('{') - text.count('}')
    arrays = text.count('[') - text.count(']')
    # Remove trailing incomplete key-value pair
    # Find last complete key-value (ends with " or number or true/false/null)
    last_complete = max(
        text.rfind(',\n'),
        text.rfind(', \n'),
        text.rfind('",'),
        text.rfind('"}'),
    )
    if last_complete > 0:
        text = text[:last_complete]
    # Close open structures
    text += '}' * max(0, opens) + ']' * max(0, arrays)
    try:
        return json.loads(text)
    except Exception:
        return None

def ask_structured(prompt: str, system: str = None) -> str:
    """Ask without streaming, return raw text."""
    return ask(prompt, system=system, stream=False)