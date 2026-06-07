"""
Mode: scan — Search job boards for new offers.
Integrates: Indeed, LinkedIn, ZipRecruiter, Glassdoor (jobspy)
            Adzuna API, Remotive API, JSearch (RapidAPI)
"""

from pathlib import Path
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
import time

from shared import load_portals, load_profile
from job_boards import (
    search_jobspy,
    search_adzuna,
    search_remotive,
    search_jsearch,
    deduplicate,
    apply_title_filters,
)
from fetcher import search_with_tinyfish

console = Console()


def run():
    console.print(Panel.fit("[bold cyan]Job Board Scanner[/bold cyan]", border_style="cyan"))

    profile  = load_profile()
    portals  = load_portals()
    tf       = portals.get("title_filter", {})
    positive = tf.get("positive", [])
    negative = tf.get("negative", ["intern", "junior", "VP", "C-level", "director"])

    default_kw = profile.get("target_roles", "software engineer").split(",")[0].strip()
    keywords   = Prompt.ask("\nSearch keywords", default=default_kw)
    location   = Prompt.ask("Location (or 'Remote')", default="Remote")
    results_n  = IntPrompt.ask("Max results per source", default=10)

    console.print("\n[bold]Select sources to search:[/bold]")
    use_jobspy   = Confirm.ask("  Indeed / LinkedIn / ZipRecruiter / Glassdoor (no key needed)", default=True)
    use_adzuna   = Confirm.ask("  Adzuna API (free key needed)", default=False)
    use_remotive = Confirm.ask("  Remotive (remote only, no key needed)", default=True)
    use_jsearch  = Confirm.ask("  JSearch / RapidAPI (free tier)", default=False)
    use_tinyfish = Confirm.ask("  TinyFish web search (free key needed)", default=False)

    if not any([use_jobspy, use_adzuna, use_remotive, use_jsearch, use_tinyfish]):
        console.print("[yellow]No sources selected.[/yellow]")
        return

    all_jobs = []
    history  = _load_scan_history()

    console.print()
    with Progress(SpinnerColumn(), TextColumn("{task.description}")) as progress:

        if use_jobspy:
            task = progress.add_task("Searching Indeed / LinkedIn / ZipRecruiter...", total=None)
            jobs = search_jobspy(keywords, location=location, results_per_site=results_n)
            all_jobs.extend(jobs)
            progress.update(task, description=f"[green]jobspy[/green] — {len(jobs)} found")

        if use_adzuna:
            task = progress.add_task("Searching Adzuna...", total=None)
            jobs = search_adzuna(keywords, location=location, results=results_n)
            all_jobs.extend(jobs)
            progress.update(task, description=f"[green]Adzuna[/green] — {len(jobs)} found")
            time.sleep(0.5)

        if use_remotive:
            task = progress.add_task("Searching Remotive...", total=None)
            jobs = search_remotive(keywords)
            all_jobs.extend(jobs)
            progress.update(task, description=f"[green]Remotive[/green] — {len(jobs)} found")

        if use_jsearch:
            task = progress.add_task("Searching JSearch...", total=None)
            jobs = search_jsearch(keywords, location=location, results=results_n)
            all_jobs.extend(jobs)
            progress.update(task, description=f"[green]JSearch[/green] — {len(jobs)} found")

        if use_tinyfish:
            task = progress.add_task("Searching via TinyFish...", total=None)
            # Target direct ATS hosts — these return actual job postings, not search pages
            tf_query = (
                f"{keywords} {location} jobs "
                "site:greenhouse.io OR site:lever.co OR site:ashbyhq.com "
                "OR site:workable.com OR site:wellfound.com OR site:smartrecruiters.com"
            )
            jobs = search_with_tinyfish(tf_query, max_results=results_n)
            all_jobs.extend(jobs)
            progress.update(task, description=f"[green]TinyFish[/green] — {len(jobs)} found")

    console.print(f"\n[dim]Raw results: {len(all_jobs)}[/dim]")
    all_jobs = apply_title_filters(all_jobs, positive, negative)
    all_jobs = deduplicate(all_jobs, history)
    console.print(f"[dim]After filters and dedup: {len(all_jobs)}[/dim]")

    if not all_jobs:
        console.print("\n[yellow]No new jobs found after filtering.[/yellow]")
        console.print("[dim]Try broader keywords or adjust title_filter in portals.yml[/dim]")
        return

    _display_results(all_jobs)

    console.print("\n[bold]What would you like to do?[/bold]")
    action = Prompt.ask(
        "Action",
        choices=["pipeline", "batch", "select", "skip"],
        default="pipeline"
    )

    if action == "pipeline":
        _add_to_pipeline(all_jobs)
        console.print(f"[green]Added {len(all_jobs)} jobs to data/pipeline.md[/green]")
        console.print("[dim]Run: python main.py batch    to evaluate all at once[/dim]")
        console.print("[dim]Run: python main.py pipeline to review one by one[/dim]")

    elif action == "batch":
        _add_to_pipeline(all_jobs)
        from modes.batch import run as batch_run
        batch_run()

    elif action == "select":
        selected = _pick_jobs(all_jobs)
        if selected:
            _add_to_pipeline(selected)
            console.print(f"[green]{len(selected)} jobs added to pipeline.[/green]")

    _update_scan_history(history, all_jobs)


def _display_results(jobs: list):
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold")
    table.add_column("#",        width=4)
    table.add_column("Source",   width=14)
    table.add_column("Company",  width=18)
    table.add_column("Title",    width=30)
    table.add_column("Location", width=16)
    table.add_column("Salary",   width=18)
    table.add_column("Posted",   width=10)

    source_colors = {
        "indeed":        "yellow",
        "linkedin":      "blue",
        "zip_recruiter": "cyan",
        "glassdoor":     "green",
        "adzuna":        "magenta",
        "remotive":      "green",
        "jsearch":       "white",
    }

    for i, job in enumerate(jobs, 1):
        src   = job.get("source", "").lower()
        color = next((v for k, v in source_colors.items() if k in src), "white")
        table.add_row(
            str(i),
            f"[{color}]{src[:14]}[/{color}]",
            job.get("company",  "")[:18],
            job.get("title",    "")[:30],
            job.get("location", "")[:16],
            job.get("salary",   "")[:18],
            job.get("posted",   "")[:10],
        )

    console.print()
    console.print(table)


def _pick_jobs(jobs: list) -> list:
    console.print("\n[dim]Enter job numbers to add (comma-separated, e.g. 1,3,5):[/dim]")
    raw = Prompt.ask("Jobs")
    selected = []
    for part in raw.split(","):
        try:
            idx = int(part.strip()) - 1
            if 0 <= idx < len(jobs):
                selected.append(jobs[idx])
        except ValueError:
            pass
    return selected


def _add_to_pipeline(jobs: list):
    p = Path("data/pipeline.md")
    p.parent.mkdir(exist_ok=True)
    existing = p.read_text(encoding="utf-8") if p.exists() else (
        "# Pending Job URLs\n\nRun `python main.py batch` to evaluate.\n\n"
    )
    today = date.today().strftime("%Y-%m-%d")
    block = f"\n## Scanned {today}\n\n"
    for job in jobs:
        sal = job.get("salary", "")
        sal_str = f" | {sal}" if sal else ""
        block += (
            f"- {job.get('url','')}  "
            f"<!-- [{job.get('source','')}] {job.get('company','')} "
            f"— {job.get('title','')}{sal_str} -->\n"
        )
    p.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")


def _load_scan_history() -> set:
    p = Path("data/scan-history.tsv")
    if not p.exists():
        return set()
    return set(
        line.split("\t")[0]
        for line in p.read_text(encoding="utf-8").splitlines()
        if "\t" in line
    )


def _update_scan_history(history: set, new_jobs: list):
    import re
    p = Path("data/scan-history.tsv")
    p.parent.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    lines = list(history)
    for job in new_jobs:
        company = (job.get("company") or "").lower().strip()
        raw_title = re.sub(r'\s*\([^)]*\)\s*$', '', job.get("title", "")).strip().lower()[:50]
        key = f"{company}:{raw_title}"
        lines.append(f"{key}\t{today}")
    p.write_text("\n".join(lines), encoding="utf-8")
