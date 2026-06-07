"""
Mode: batch — Evaluate multiple job offers in parallel.
Reads URLs from data/pipeline.md and evaluates each one.
"""

from pathlib import Path
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
import concurrent.futures
import re

from gemini_client import ask_structured
from shared import build_context, get_next_report_number, save_tracker_entry
from modes.evaluate import _fetch_url, _extract_score, _extract_meta, EVAL_SYSTEM, _update_story_bank

console = Console()

def run():
    console.print(Panel.fit("[bold cyan]Batch Job Evaluator[/bold cyan]", border_style="cyan"))

    pipeline_path = Path("data/pipeline.md")
    if not pipeline_path.exists():
        console.print("[yellow]data/pipeline.md not found. Run setup or scan first.[/yellow]")
        return

    urls = _extract_urls(pipeline_path)
    if not urls:
        console.print("[yellow]No URLs found in data/pipeline.md.[/yellow]")
        console.print("[dim]Add job URLs to that file, one per line.[/dim]")
        return

    console.print(f"[green]Found {len(urls)} job URL(s) to evaluate.[/green]\n")
    for i, url in enumerate(urls, 1):
        console.print(f"  {i}. {url}")

    if not Confirm.ask(f"\nEvaluate all {len(urls)} jobs?", default=True):
        return

    context = build_context()
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
    ) as progress:
        task = progress.add_task("Evaluating jobs...", total=len(urls))

        for url in urls:
            progress.update(task, description=f"Evaluating: {url[:50]}...")
            try:
                result = _evaluate_single(url, context)
                results.append(result)
            except Exception as e:
                results.append({"url": url, "error": str(e)})
            progress.advance(task)

    # Show summary
    console.print("\n[bold]Batch Results:[/bold]\n")
    for r in results:
        if "error" in r:
            console.print(f"  [red]✗[/red] {r['url'][:50]} — Error: {r['error']}")
        else:
            grade_colors = {"A": "green", "B": "cyan", "C": "yellow", "D": "red", "F": "red"}
            color = grade_colors.get(r.get("grade", "?"), "white")
            console.print(
                f"  [{color}]{r.get('grade','?')}[/{color}] "
                f"[bold]{r.get('company','?')}[/bold] — {r.get('role','?')} "
                f"[dim]({r.get('score', '?')}/5)[/dim]"
            )

    # Save all reports
    if any("error" not in r for r in results) and Confirm.ask("\nSave all reports?", default=True):
        for r in results:
            if "error" not in r and r.get("report_text"):
                _save_report(r)
        # Clear pipeline
        if Confirm.ask("Clear processed URLs from pipeline.md?", default=True):
            _clear_pipeline(pipeline_path, urls)
        console.print("[green]✅ All reports saved.[/green]")

def _extract_urls(pipeline_path: Path) -> list:
    """Extract job URLs from pipeline.md."""
    content = pipeline_path.read_text()
    urls = re.findall(r'https?://[^\s<>\[\]"\']+', content)
    # Filter out comment URLs and dedup
    seen = set()
    result = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result

def _evaluate_single(url: str, context: str) -> dict:
    """Evaluate one job URL."""
    job_content = _fetch_url(url)
    if not job_content:
        return {"url": url, "error": "Could not fetch URL"}

    prompt = f"""
## Candidate Context
{context}

## Job URL
{url}

## Job Description
{job_content}

Provide a concise evaluation:
1. Company name and role title
2. Score breakdown (6 dimensions)
3. Overall score X.X/5, Grade A-F
4. Key strengths and gaps (3 each)
5. GO / NO-GO recommendation with reason

Keep response under 600 words for batch efficiency.
"""
    report_text = ask_structured(prompt, system=EVAL_SYSTEM)
    score, grade = _extract_score(report_text)
    company, role = _extract_meta(report_text, job_content)

    return {
        "url": url,
        "company": company,
        "role": role,
        "score": score,
        "grade": grade,
        "report_text": report_text,
    }

def _save_report(r: dict):
    num = get_next_report_number()
    today = date.today().strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', r.get('company', 'unknown').lower())[:20]
    report_path = Path(f"reports/{num:03d}-{slug}-{today}.md")
    report_path.parent.mkdir(exist_ok=True)

    content = f"""# {r['company']} — {r['role']}

**Date:** {today}  
**Score:** {r['score']}/5 (Grade: {r['grade']})  
**URL:** {r['url']}  
**PDF:** ❌

---

{r['report_text']}
"""
    report_path.write_text(content)
    save_tracker_entry({
        "num": num,
        "date": today,
        "company": r["company"],
        "role": r["role"],
        "score": f"{r['score']}/5",
        "status": "Evaluated",
        "pdf": "❌",
        "report": f"[{num:03d}]({report_path})",
        "notes": f"Grade {r['grade']}"
    })

def _clear_pipeline(pipeline_path: Path, processed_urls: list):
    content = pipeline_path.read_text()
    for url in processed_urls:
        content = content.replace(url, f"~~{url}~~")
    pipeline_path.write_text(content)
