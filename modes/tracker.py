"""
Mode: tracker — View and manage the application pipeline.
Displays applications.md as a rich table with filters.
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
import re

console = Console()

STATUS_COLORS = {
    "Evaluated":  "cyan",
    "Applied":    "blue",
    "Responded":  "yellow",
    "Interview":  "magenta",
    "Offer":      "green",
    "Rejected":   "red",
    "Discarded":  "dim",
    "SKIP":       "dim red",
}

VALID_STATUSES = ["Evaluated", "Applied", "Responded", "Interview", "Offer", "Rejected", "Discarded", "SKIP"]

def run():
    console.print(Panel.fit("[bold cyan]Application Tracker[/bold cyan]", border_style="cyan"))

    tracker_path = Path("data/applications.md")
    if not tracker_path.exists():
        console.print("[yellow]No tracker found. Run 'python main.py setup' first.[/yellow]")
        return

    apps = _parse_tracker(tracker_path)

    if not apps:
        console.print("[dim]No applications tracked yet.[/dim]")
        return

    # Filter options
    console.print(f"\n[dim]Total: {len(apps)} applications[/dim]")
    filter_status = Prompt.ask(
        "Filter by status (or press Enter for all)",
        choices=VALID_STATUSES + [""],
        default=""
    )

    filtered = apps if not filter_status else [a for a in apps if a.get("status") == filter_status]

    _display_table(filtered)
    _show_stats(apps)

    # Update status
    if filtered and Confirm.ask("\nUpdate an application's status?", default=False):
        num = Prompt.ask("Enter application # to update")
        new_status = Prompt.ask("New status", choices=VALID_STATUSES)
        _update_status(tracker_path, num, new_status)
        console.print(f"[green]Updated #{num} to {new_status}[/green]")

def _parse_tracker(path: Path) -> list:
    """Parse markdown table into list of dicts."""
    apps = []
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="cp1252", errors="replace")

    lines = content.splitlines()
    headers = []

    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # Remove empty first and last cells from split
        cells = [c for c in cells if c != ""]
        if not cells:
            continue
        # Skip separator row
        if all(set(c.replace("-","").replace(" ","")) <= set("-") for c in cells):
            continue
        if not headers:
            # Normalize header names
            headers = []
            for h in cells:
                h = h.lower().strip()
                h = h.replace(" ", "_").replace("#", "num").replace("/","_")
                h = re.sub(r"[^a-z0-9_]", "", h)
                headers.append(h)
            continue
        # Data row — pad or trim to match headers
        while len(cells) < len(headers):
            cells.append("")
        cells = cells[:len(headers)]
        row = dict(zip(headers, cells))
        # Normalize key names for display
        app = {
            "#":       row.get("num", row.get("_", "")),
            "date":    row.get("date", ""),
            "company": row.get("company", ""),
            "role":    row.get("role", ""),
            "score":   row.get("score", ""),
            "status":  row.get("status", ""),
            "pdf":     row.get("pdf", ""),
            "report":  row.get("report", ""),
            "notes":   row.get("notes", ""),
        }
        # Skip completely empty rows
        if not any([app["company"], app["role"], app["date"]]):
            continue
        apps.append(app)

    return apps

def _display_table(apps: list):
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True, header_style="bold")
    table.add_column("#", width=4)
    table.add_column("Date", width=12)
    table.add_column("Company", width=18)
    table.add_column("Role", width=28)
    table.add_column("Score", width=8)
    table.add_column("Status", width=12)
    table.add_column("PDF", width=5)
    table.add_column("Notes", width=20)

    for app in apps:
        status = app.get("status", "")
        color = STATUS_COLORS.get(status, "white")
        table.add_row(
            app.get("#", ""),
            app.get("date", ""),
            app.get("company", ""),
            app.get("role", ""),
            app.get("score", ""),
            f"[{color}]{status}[/{color}]",
            app.get("pdf", ""),
            app.get("notes", ""),
        )

    console.print(table)

def _show_stats(apps: list):
    from collections import Counter
    statuses = Counter(a.get("status", "Unknown") for a in apps)

    console.print("\n[bold]Pipeline Stats:[/bold]")
    for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
        color = STATUS_COLORS.get(status, "white")
        bar = "█" * count
        console.print(f"  [{color}]{status:<12}[/{color}] {bar} {count}")

    # Score stats
    scores = []
    for a in apps:
        score_str = a.get("score", "").replace("/5", "").strip()
        try:
            scores.append(float(score_str))
        except ValueError:
            pass

    if scores:
        avg = sum(scores) / len(scores)
        console.print(f"\n  Average score: [cyan]{avg:.1f}/5[/cyan]")
        above_4 = sum(1 for s in scores if s >= 4.0)
        console.print(f"  High fit (≥4.0): [green]{above_4}[/green] of {len(scores)}")

def _update_status(path: Path, num: str, new_status: str):
    """Update status for a given application number."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated = []
    for line in lines:
        if line.startswith(f"| {num} |") or line.startswith(f"| {num.zfill(3)} |"):
            # Replace status field (column 6, index 5)
            cells = line.split("|")
            if len(cells) > 6:
                cells[6] = f" {new_status} "
                line = "|".join(cells)
        updated.append(line)
    path.write_text("\n".join(updated), encoding="utf-8")