"""
Mode: stats — Show pipeline analytics and job search metrics.
"""

from pathlib import Path
from collections import Counter, defaultdict
from datetime import date, datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich import box
import re

console = Console()

def run():
    console.print(Panel.fit("[bold cyan]Pipeline Analytics[/bold cyan]", border_style="cyan"))

    tracker_path = Path("data/applications.md")
    if not tracker_path.exists():
        console.print("[yellow]No tracker data found.[/yellow]")
        return

    apps = _parse_tracker(tracker_path)
    if not apps:
        console.print("[dim]No applications tracked yet.[/dim]")
        return

    _show_overview(apps)
    _show_funnel(apps)
    _show_score_distribution(apps)
    _show_recent(apps)
    _show_top_companies(apps)
    _show_timeline(apps)

def _parse_tracker(path: Path) -> list:
    apps = []
    lines = path.read_text().splitlines()
    headers = []
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not cells:
            continue
        if "---" in cells[0]:
            continue
        if not headers:
            headers = [h.lower().replace(" ", "_").strip("#").strip() for h in cells]
            continue
        if len(cells) == len(headers):
            apps.append(dict(zip(headers, cells)))
    return apps

def _show_overview(apps: list):
    statuses = Counter(a.get("status", "Unknown") for a in apps)
    scores = _get_scores(apps)

    console.print(f"\n[bold]📊 Overview[/bold]")
    console.print(f"  Total applications tracked: [cyan]{len(apps)}[/cyan]")
    if scores:
        avg = sum(scores) / len(scores)
        console.print(f"  Average score:             [cyan]{avg:.1f}/5[/cyan]")
        console.print(f"  High-fit (≥4.0):           [green]{sum(1 for s in scores if s >= 4.0)}[/green]")
        console.print(f"  Weak-fit (<3.0):           [red]{sum(1 for s in scores if s < 3.0)}[/red]")

    reports_dir = Path("reports")
    report_count = len(list(reports_dir.glob("*.md"))) if reports_dir.exists() else 0
    console.print(f"  Reports generated:         [cyan]{report_count}[/cyan]")

    output_dir = Path("output")
    pdf_count = len(list(output_dir.glob("*.pdf"))) if output_dir.exists() else 0
    console.print(f"  CVs/PDFs generated:        [cyan]{pdf_count}[/cyan]")

def _show_funnel(apps: list):
    funnel_order = ["Evaluated", "Applied", "Responded", "Interview", "Offer", "Rejected", "Discarded", "SKIP"]
    statuses = Counter(a.get("status", "Unknown") for a in apps)
    total = len(apps)

    console.print(f"\n[bold]🔽 Application Funnel[/bold]")

    colors = {
        "Evaluated": "cyan", "Applied": "blue", "Responded": "yellow",
        "Interview": "magenta", "Offer": "green", "Rejected": "red",
        "Discarded": "dim", "SKIP": "dim red"
    }

    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Stage", width=14)
    table.add_column("Count", width=6)
    table.add_column("Bar", width=30)
    table.add_column("Pct", width=8)

    for status in funnel_order:
        count = statuses.get(status, 0)
        if count == 0:
            continue
        color = colors.get(status, "white")
        bar = "█" * min(count * 2, 30)
        pct = f"{count/total*100:.0f}%"
        table.add_row(
            f"[{color}]{status}[/{color}]",
            f"[{color}]{count}[/{color}]",
            f"[{color}]{bar}[/{color}]",
            f"[dim]{pct}[/dim]"
        )

    console.print(table)

    # Conversion rates
    applied = statuses.get("Applied", 0) + statuses.get("Responded", 0) + \
              statuses.get("Interview", 0) + statuses.get("Offer", 0)
    interviews = statuses.get("Interview", 0) + statuses.get("Offer", 0)
    offers = statuses.get("Offer", 0)

    if applied > 0:
        console.print(f"  Evaluated → Applied:   [cyan]{applied}/{len(apps)} ({applied/len(apps)*100:.0f}%)[/cyan]")
    if applied > 0 and interviews > 0:
        console.print(f"  Applied → Interview:   [magenta]{interviews}/{applied} ({interviews/applied*100:.0f}%)[/magenta]")
    if interviews > 0 and offers > 0:
        console.print(f"  Interview → Offer:     [green]{offers}/{interviews} ({offers/interviews*100:.0f}%)[/green]")

def _show_score_distribution(apps: list):
    scores = _get_scores(apps)
    if not scores:
        return

    console.print(f"\n[bold]📈 Score Distribution[/bold]")

    buckets = {"A (4.5-5.0)": 0, "B (3.5-4.4)": 0, "C (2.5-3.4)": 0, "D (1.5-2.4)": 0, "F (<1.5)": 0}
    for s in scores:
        if s >= 4.5:   buckets["A (4.5-5.0)"] += 1
        elif s >= 3.5: buckets["B (3.5-4.4)"] += 1
        elif s >= 2.5: buckets["C (2.5-3.4)"] += 1
        elif s >= 1.5: buckets["D (1.5-2.4)"] += 1
        else:          buckets["F (<1.5)"] += 1

    grade_colors = {"A": "green", "B": "cyan", "C": "yellow", "D": "red", "F": "red"}
    for label, count in buckets.items():
        if count == 0:
            continue
        grade = label[0]
        color = grade_colors.get(grade, "white")
        bar = "█" * count
        console.print(f"  [{color}]{label:<14}[/{color}] {bar} {count}")

def _show_recent(apps: list, n: int = 5):
    console.print(f"\n[bold]🕐 Recent Applications (last {n})[/bold]")

    recent = apps[-n:][::-1]
    table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    table.add_column("Date", width=12)
    table.add_column("Company", width=18)
    table.add_column("Role", width=25)
    table.add_column("Score", width=8)
    table.add_column("Status", width=12)

    status_colors = {
        "Evaluated": "cyan", "Applied": "blue", "Responded": "yellow",
        "Interview": "magenta", "Offer": "green", "Rejected": "red",
        "Discarded": "dim", "SKIP": "dim red"
    }

    for app in recent:
        status = app.get("status", "")
        color = status_colors.get(status, "white")
        table.add_row(
            app.get("date", ""),
            app.get("company", ""),
            app.get("role", ""),
            app.get("score", ""),
            f"[{color}]{status}[/{color}]"
        )

    console.print(table)

def _show_top_companies(apps: list):
    companies = Counter(a.get("company", "Unknown") for a in apps)
    top = companies.most_common(5)
    if len(top) <= 1:
        return

    console.print(f"\n[bold]🏢 Most Evaluated Companies[/bold]")
    for company, count in top:
        console.print(f"  {company}: [cyan]{count}[/cyan]")

def _show_timeline(apps: list):
    # Group by month
    monthly = defaultdict(int)
    for app in apps:
        date_str = app.get("date", "")
        if date_str and len(date_str) >= 7:
            month = date_str[:7]
            monthly[month] += 1

    if len(monthly) <= 1:
        return

    console.print(f"\n[bold]📅 Monthly Activity[/bold]")
    for month in sorted(monthly.keys())[-6:]:  # Last 6 months
        count = monthly[month]
        bar = "█" * min(count, 20)
        console.print(f"  {month}  [cyan]{bar}[/cyan] {count}")

def _get_scores(apps: list) -> list:
    scores = []
    for a in apps:
        score_str = a.get("score", "").replace("/5", "").strip()
        try:
            scores.append(float(score_str))
        except ValueError:
            pass
    return scores
