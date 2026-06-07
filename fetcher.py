"""
fetcher.py â€” Unified job page fetcher for Career-Ops.

Priority chain:
  1. TinyFish Fetch  â€” fast, clean markdown, handles JS-rendered pages
  2. ScrapeGraphAI   â€” natural-language structured extraction (richer data)
  3. urllib fallback â€” original simple fetcher (no key needed)

Set in .env:
  TINYFISH_API_KEY   â†’ get free at https://agent.tinyfish.ai/api-keys
  SCRAPEGRAPH_API_KEY â†’ get at https://scrapegraphai.com/
"""

import json
import os
from urllib.parse import urlparse
from pathlib import Path
from rich.console import Console

console = Console()

JOB_URL_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "myworkdayjobs.com",
    "recruitee.com",
    "wellfound.com",
    "jobs.ashbyhq.com",
    "boards.greenhouse.io",
    "jobs.lever.co",
    "apply.workable.com",
)

BAD_SEARCH_HOSTS = (
    "linkedin.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "medium.com",
    "youtube.com",
)

BAD_SEARCH_PATH_PARTS = (
    "/posts/",
    "/activity-",
    "/pulse/",
    "/feed/",
    "/search",
    "/m/jobs",
)


def is_probable_job_url(url: str) -> bool:
    """Keep direct job/careers URLs and drop posts, articles, and search pages."""
    if not url:
        return False

    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.lower()

    if any(bad in host for bad in BAD_SEARCH_HOSTS):
        return False
    if any(part in path for part in BAD_SEARCH_PATH_PARTS):
        return False
    if "indeed." in host:
        return "/viewjob" in path or "/rc/clk" in path
    if any(good in host for good in JOB_URL_HOSTS):
        return True
    return "careers" in host or "/careers/" in path or "/jobs/" in path or "/job/" in path


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Env helper
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return val


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 1. TinyFish â€” fast clean fetch
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def fetch_with_tinyfish(url: str) -> str | None:
    """
    Fetch a URL using TinyFish Fetch API.
    Returns clean markdown text, or None on failure.
    Free API â€” get key at https://agent.tinyfish.ai/api-keys
    """
    api_key = _env("TINYFISH_API_KEY")
    if not api_key:
        return None

    try:
        from tinyfish import TinyFish
        client  = TinyFish(api_key=api_key)
        result  = client.fetch.get_contents(urls=[url], format="markdown")

        for page in getattr(result, "results", []) or []:
            content = getattr(page, "text", None) or getattr(page, "content", None)
            if content and len(content) > 100:
                console.print("[dim]  TinyFish fetch succeeded[/dim]")
                return content[:10000]

        errors = getattr(result, "errors", []) or []
        if errors:
            first_error = getattr(errors[0], "error", str(errors[0]))
            console.print(f"[dim]  TinyFish fetch error: {first_error}[/dim]")
        return None

    except ImportError:
        console.print("[yellow]  tinyfish not installed. Run: pip install tinyfish[/yellow]")
    except Exception as e:
        console.print(f"[dim]  TinyFish fetch failed ({e}), trying next method...[/dim]")

    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 2. ScrapeGraphAI â€” structured extraction
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SCRAPE_PROMPT = (
    "Extract job listing details from this page. Return only valid JSON, with no "
    "reasoning, markdown, bullets, code fences, or extra text. Use these keys: "
    "job_title, company_name, location, salary_or_compensation, job_description, "
    "required_skills, qualifications, how_to_apply. Use NA for missing fields."
)

def _dict_to_labeled_text(data: dict) -> str | None:
    """Convert extracted ScrapeGraph data into readable labeled text."""
    content = data.get("content")
    if isinstance(content, dict):
        data = content
    elif isinstance(content, str) and content.strip():
        return content[:10000]

    lines = [f"**{k}:** {v}" for k, v in data.items() if v]
    text = "\n".join(lines)
    return text[:10000] if text else None


def _extract_json_object(text: str) -> dict | None:
    """Best-effort recovery for models that include prose before final JSON."""
    decoder = json.JSONDecoder()
    best = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            best = obj
    return best

def fetch_with_scrapegraph(url: str) -> str | None:
    """
    Fetch + extract structured job data using ScrapeGraphAI with Gemma 4 31B.
    Uses GEMINI_API_KEY via the google_genai provider â€” do NOT use
    SCRAPEGRAPH_API_KEY here as that is for ScrapeGraph's own cloud endpoint.
    """
    # Must be the Gemini/AI-Studio key â€” google_genai provider requires it
    api_key = _env("GEMINI_API_KEY")
    if not api_key:
        console.print("[yellow]  ScrapeGraphAI: set GEMINI_API_KEY in .env[/yellow]")
        return None

    try:
        from scrapegraphai.graphs import SmartScraperGraph
        from pydantic import BaseModel

        class JobListing(BaseModel):
            job_title: str
            company_name: str
            location: str
            salary_or_compensation: str
            job_description: str
            required_skills: str
            qualifications: str
            how_to_apply: str

        graph_config = {
            "llm": {
                "api_key":      api_key,
                "model":        "google_genai/gemma-4-31b-it",  # Gemma 4 31B via AI Studio
                "temperature":  0,
                "model_tokens": 32768,   # Gemma 4 has 256K ctx; 32K is a safe working chunk
            },
            "verbose":   False,
            "headless":  True,
        }

        scraper = SmartScraperGraph(
            prompt=SCRAPE_PROMPT,
            source=url,
            config=graph_config,
            schema=JobListing,
        )
        result = scraper.run()

        if result and isinstance(result, dict):
            text = _dict_to_labeled_text(result)
            if text and len(text) > 100:
                console.print("[dim]  âœ“ ScrapeGraphAI extraction succeeded[/dim]")
                return text[:10000]

        elif result and isinstance(result, str) and len(result) > 100:
            console.print("[dim]  âœ“ ScrapeGraphAI extraction succeeded[/dim]")
            return result[:10000]

    except ImportError:
        console.print("[yellow]  scrapegraphai not installed. Run: pip install scrapegraphai[/yellow]")
    except Exception as e:
        recovered = _extract_json_object(str(e))
        if recovered:
            text = _dict_to_labeled_text(recovered)
            if text and len(text) > 20:
                console.print("[dim]  ScrapeGraphAI extraction recovered from model output[/dim]")
                return text[:10000]
        console.print(f"[dim]  ScrapeGraphAI failed ({e}), trying fallback...[/dim]")

    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# 3. urllib fallback (original method)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def fetch_with_urllib(url: str) -> str | None:
    """Original simple HTML fetcher â€” no API key needed."""
    try:
        import urllib.request
        from html.parser import HTMLParser

        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
                self.skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "nav", "footer"):
                    self.skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "nav", "footer"):
                    self.skip = False

            def handle_data(self, data):
                if not self.skip and data.strip():
                    self.text.append(data.strip())

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        parser = TextExtractor()
        parser.feed(html)
        text = "\n".join(parser.text)
        if text.strip():
            console.print("[dim]  âœ“ urllib fallback succeeded[/dim]")
            return text[:8000]

    except Exception as e:
        console.print(f"[yellow]  urllib fetch failed: {e}[/yellow]")

    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main entry point â€” used by evaluate.py
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def fetch_job_page(url: str) -> str | None:
    """
    Fetch a job listing URL using the best available method.
    Priority: TinyFish â†’ ScrapeGraphAI â†’ urllib fallback
    """
    console.print(f"[dim]Fetching: {url}[/dim]")

    # 1. TinyFish â€” fastest, handles JS pages
    result = fetch_with_tinyfish(url)
    if result:
        return result

    # 2. ScrapeGraphAI â€” structured extraction
    result = fetch_with_scrapegraph(url)
    if result:
        return result

    # 3. urllib â€” simple fallback
    result = fetch_with_urllib(url)
    if result:
        return result

    console.print("[red]  âœ— All fetch methods failed.[/red]")
    return None


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# TinyFish Search â€” for scan mode
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def search_with_tinyfish(query: str, max_results: int = 10) -> list[dict]:
    """
    Search for job listings using TinyFish Search API.
    Returns list of {title, url, snippet} dicts.
    Use in scan.py as an additional job source.
    """
    api_key = _env("TINYFISH_API_KEY")
    if not api_key:
        console.print("[yellow]  TinyFish search: set TINYFISH_API_KEY in .env[/yellow]")
        return []

    try:
        from tinyfish import TinyFish
        client = TinyFish(api_key=api_key)
        resp   = client.search.query(query=query)

        jobs = []
        for r in resp.results or []:
            url = getattr(r, "url", "") or ""
            if not is_probable_job_url(url):
                continue
            jobs.append({
                "title":       getattr(r, "title",     "") or "",
                "url":         url,
                "company":     "",   # search results don't have company â€” fill via fetch
                "location":    "Remote",
                "source":      "tinyfish",
                "description": getattr(r, "snippet",   "") or "",
                "salary":      "",
                "posted":      "",
            })

        console.print(f"  [green]âœ“ TinyFish search found {len(jobs)} results[/green]")
        return jobs

    except ImportError:
        console.print("[yellow]  tinyfish not installed. Run: pip install tinyfish[/yellow]")
    except Exception as e:
        console.print(f"[red]  TinyFish search error: {e}[/red]")

    return []


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Quick test
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://remotive.com/remote-jobs/software-dev"
    console.print(f"[bold]Testing fetcher on:[/bold] {url}")
    content = fetch_job_page(url)
    if content:
        console.print(f"\n[green]âœ“ Got {len(content)} chars[/green]")
        console.print(content[:500])
    else:
        console.print("[red]Failed to fetch.[/red]")

