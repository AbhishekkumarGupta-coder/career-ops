"""
Job board integrations for Career-Ops.
Supports: Indeed, LinkedIn, ZipRecruiter (via jobspy)
          Adzuna API, Remotive API, JSearch (RapidAPI)
"""

import os
import time
import requests
from pathlib import Path
from datetime import date
from rich.console import Console

console = Console()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# jobspy â€” Indeed, LinkedIn, ZipRecruiter
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def search_jobspy(
    keywords: str,
    location: str = "Remote",
    results_per_site: int = 10,
    sites: list = None,
) -> list:
    """
    Search Indeed, LinkedIn, ZipRecruiter, Glassdoor via jobspy.
    No API keys needed.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        console.print("[yellow]jobspy not installed. Run: pip install python-jobspy[/yellow]")
        return []

    if sites is None:
        sites = ["indeed", "linkedin", "zip_recruiter", "glassdoor"]

    console.print(f"  [dim]jobspy -> searching {', '.join(sites)} for '{keywords}' in '{location}'...[/dim]")

    try:
        df = scrape_jobs(
            site_name=sites,
            search_term=keywords,
            location=location,
            results_wanted=results_per_site,
            hours_old=72,           # Jobs posted in last 3 days
            country_indeed="USA",
        )
    except Exception as e:
        console.print(f"  [red]jobspy error: {e}[/red]")
        return []

    jobs = []
    for _, row in df.iterrows():
        job = {
            "title":       str(row.get("title", "")).strip(),
            "company":     str(row.get("company", "")).strip(),
            "location":    str(row.get("location", "")).strip(),
            "url":         str(row.get("job_url", "")).strip(),
            "source":      str(row.get("site", "")).strip(),
            "description": str(row.get("description", ""))[:500].strip(),
            "salary":      _fmt_salary(row),
            "posted":      str(row.get("date_posted", "")).strip(),
        }
        if job["url"] and job["title"]:
            jobs.append(job)

    console.print(f"  [green]âœ“ jobspy found {len(jobs)} jobs[/green]")
    return jobs


def _fmt_salary(row) -> str:
    lo = row.get("min_amount", "")
    hi = row.get("max_amount", "")
    interval = row.get("salary_interval", "")
    currency = row.get("currency", "USD")
    if lo and hi:
        return f"{currency} {lo:,.0f}â€“{hi:,.0f}/{interval}"
    elif lo:
        return f"{currency} {lo:,.0f}+/{interval}"
    return ""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Adzuna API (free, 250 req/day)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def search_adzuna(
    keywords: str,
    location: str = "",
    country: str = "us",
    results: int = 20,
) -> list:
    """
    Search via Adzuna API.
    Free key: https://developer.adzuna.com/
    Set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env
    """
    app_id  = _env("ADZUNA_APP_ID")
    app_key = _env("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        console.print("  [yellow]Adzuna: set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env[/yellow]")
        return []

    console.print(f"  [dim]Adzuna -> searching '{keywords}'...[/dim]")

    params = {
        "app_id":        app_id,
        "app_key":       app_key,
        "results_per_page": results,
        "what":          keywords,
        "content-type":  "application/json",
    }
    if location:
        params["where"] = location

    try:
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        console.print(f"  [red]Adzuna error: {e}[/red]")
        return []

    jobs = []
    for item in data.get("results", []):
        jobs.append({
            "title":       item.get("title", "").strip(),
            "company":     item.get("company", {}).get("display_name", "").strip(),
            "location":    item.get("location", {}).get("display_name", "").strip(),
            "url":         item.get("redirect_url", "").strip(),
            "source":      "adzuna",
            "description": item.get("description", "")[:500].strip(),
            "salary":      _adzuna_salary(item),
            "posted":      item.get("created", "")[:10],
        })

    console.print(f"  [green]âœ“ Adzuna found {len(jobs)} jobs[/green]")
    return jobs


def _adzuna_salary(item: dict) -> str:
    lo = item.get("salary_min")
    hi = item.get("salary_max")
    if lo and hi:
        return f"${lo:,.0f}â€“${hi:,.0f}"
    elif lo:
        return f"${lo:,.0f}+"
    return ""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Remotive API (free, remote jobs only)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def search_remotive(keywords: str, category: str = "") -> list:
    """
    Search Remotive for remote jobs. Completely free, no key needed.
    https://remotive.com/api
    """
    console.print(f"  [dim]Remotive -> searching '{keywords}'...[/dim]")

    params = {"search": keywords}
    if category:
        params["category"] = category

    try:
        resp = requests.get("https://remotive.com/api/remote-jobs", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        console.print(f"  [red]Remotive error: {e}[/red]")
        return []

    jobs = []
    for item in data.get("jobs", [])[:20]:
        jobs.append({
            "title":       item.get("title", "").strip(),
            "company":     item.get("company_name", "").strip(),
            "location":    item.get("candidate_required_location", "Remote").strip(),
            "url":         item.get("url", "").strip(),
            "source":      "remotive",
            "description": item.get("description", "")[:500].strip(),
            "salary":      item.get("salary", "").strip(),
            "posted":      item.get("publication_date", "")[:10],
        })

    console.print(f"  [green]âœ“ Remotive found {len(jobs)} jobs[/green]")
    return jobs


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# JSearch via RapidAPI (free tier: 10/min)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def search_jsearch(keywords: str, location: str = "Remote", results: int = 10) -> list:
    """
    JSearch aggregates Indeed + LinkedIn + Glassdoor.
    Free tier: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    Set RAPIDAPI_KEY in .env
    """
    api_key = _env("RAPIDAPI_KEY")
    if not api_key:
        console.print("  [yellow]JSearch: set RAPIDAPI_KEY in .env (free at rapidapi.com)[/yellow]")
        return []

    console.print(f"  [dim]JSearch -> searching '{keywords}' in '{location}'...[/dim]")

    try:
        resp = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key":  api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            params={
                "query":          f"{keywords} in {location}",
                "page":           "1",
                "num_pages":      "1",
                "date_posted":    "week",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        console.print(f"  [red]JSearch error: {e}[/red]")
        return []

    jobs = []
    for item in data.get("data", [])[:results]:
        jobs.append({
            "title":       item.get("job_title", "").strip(),
            "company":     item.get("employer_name", "").strip(),
            "location":    item.get("job_city", "") + ", " + item.get("job_country", ""),
            "url":         item.get("job_apply_link", "").strip(),
            "source":      f"jsearch/{item.get('job_publisher','').lower()}",
            "description": item.get("job_description", "")[:500].strip(),
            "salary":      _jsearch_salary(item),
            "posted":      item.get("job_posted_at_datetime_utc", "")[:10],
        })

    console.print(f"  [green]âœ“ JSearch found {len(jobs)} jobs[/green]")
    return jobs


def _jsearch_salary(item: dict) -> str:
    lo = item.get("job_min_salary")
    hi = item.get("job_max_salary")
    period = item.get("job_salary_period", "")
    currency = item.get("job_salary_currency", "USD")
    if lo and hi:
        return f"{currency} {lo:,.0f}â€“{hi:,.0f}/{period}"
    return ""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _env(key: str) -> str:
    """Read from environment or .env file."""
    val = os.environ.get(key, "")
    if not val:
        env_path = Path(".env")
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return val


def deduplicate(jobs: list, history: set) -> list:
    """Remove jobs already in scan history and collapse near-duplicate variants.

    Two jobs are considered duplicates when they share the same company AND
    the same base title (ignoring a trailing parenthesised city/location like
    'Staff Engineer (SÃ£o Paulo)' vs 'Staff Engineer (Porto Alegre)').
    Exact URL matches are also collapsed regardless of title.
    """
    import re
    seen_keys = set()
    seen_urls = set()
    result = []

    def _normalise(title: str) -> str:
        """Strip trailing '(anything)' location qualifiers and truncate."""
        normalised = re.sub(r'\s*\([^)]*\)\s*$', '', title).strip()
        return normalised.lower()[:50]

    for job in jobs:
        url = (job.get("url") or "").strip()
        company = (job.get("company") or "").lower().strip()
        title_key = _normalise(job.get("title", ""))
        dedup_key = f"{company}:{title_key}"

        # Skip if we've seen this URL or this company+title combo before
        if url and url in seen_urls:
            continue
        if dedup_key in history or dedup_key in seen_keys:
            continue
        if not url:          # Skip entries with no URL â€” nothing to act on
            continue

        seen_keys.add(dedup_key)
        seen_urls.add(url)
        result.append(job)
    return result


def apply_title_filters(jobs: list, positive: list, negative: list) -> list:
    """Filter jobs by title keywords."""
    filtered = []
    for job in jobs:
        title = job.get("title", "").lower()
        if negative and any(n.lower() in title for n in negative):
            continue
        if positive and not any(p.lower() in title for p in positive):
            continue
        filtered.append(job)
    return filtered

