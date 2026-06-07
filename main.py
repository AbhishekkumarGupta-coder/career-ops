#!/usr/bin/env python3
"""
Career-Ops — AI Job Search Pipeline
Powered by Google Gemini (free tier)
"""

import sys
import os
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

BANNER = """
[bold cyan]╔═══════════════════════════════════════════╗
║         CAREER-OPS  •  Gemini Edition      ║
║   AI-Powered Job Search Pipeline           ║
╚═══════════════════════════════════════════╝[/bold cyan]
"""

COMMANDS = {
    "evaluate": "Evaluate a job offer (paste URL or JD)",
    "scan":     "Scan job portals for new offers",
    "pdf":      "Generate ATS-optimized CV PDF",
    "batch":    "Batch evaluate multiple offers",
    "tracker":  "View application pipeline",
    "deep":     "Deep company research",
    "contact":  "Draft LinkedIn outreach message",
    "apply":    "Fill application form answers",
    "pipeline": "Process pending URLs from pipeline.md",
    "compare":  "Compare two or more offers",
    "training": "Evaluate a course or certification",
    "project":  "Evaluate a portfolio project",
    "setup":    "Onboarding / re-run setup wizard",
    "stats":    "Show pipeline stats & analytics",
    "autoapply":"Auto-fill job application forms (Selenium)",
    "outreach": "Cold email + follow-up scheduler",
    "followups":"Show pending follow-up reminders",
}

def show_help():
    console.print(BANNER)
    table = Table(box=box.ROUNDED, border_style="cyan", show_header=True)
    table.add_column("Command", style="bold yellow", width=14)
    table.add_column("Description", style="white")
    for cmd, desc in COMMANDS.items():
        table.add_row(f"  {cmd}", desc)
    console.print(table)
    console.print("\n[dim]Usage:[/dim]  [bold]python main.py [command][/bold]  or just  [bold]python main.py[/bold]  for interactive mode\n")

def check_setup():
    """Returns True if system is ready, False if onboarding needed."""
    missing = []
    if not Path("cv.md").exists():
        missing.append("cv.md")
    if not Path("config/profile.yml").exists():
        missing.append("config/profile.yml")
    return missing

def main():
    # Check if we're in the right directory
    if not Path("config").exists():
        console.print("[red]Please run career-ops from its project directory.[/red]")
        sys.exit(1)

    # Parse command
    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else None

    # Show help
    if cmd in (None, "help", "--help", "-h"):
        show_help()
        if cmd is None:
            interactive_mode()
        return

    # Import and dispatch
    missing = check_setup()
    if missing and cmd not in ("setup",):
        console.print(f"\n[yellow]⚠️  Setup incomplete. Missing: {', '.join(missing)}[/yellow]")
        console.print("[dim]Run:[/dim] [bold]python main.py setup[/bold]\n")
        from modes.setup import run_setup
        run_setup()
        return

    dispatch(cmd)

def dispatch(cmd):
    handlers = {
        "evaluate":  lambda: __import__("modes.evaluate", fromlist=["run"]).run(),
        "scan":      lambda: __import__("modes.scan",     fromlist=["run"]).run(),
        "pdf":       lambda: __import__("modes.pdf",      fromlist=["run"]).run(),
        "batch":     lambda: __import__("modes.batch",    fromlist=["run"]).run(),
        "tracker":   lambda: __import__("modes.tracker",  fromlist=["run"]).run(),
        "deep":      lambda: __import__("modes.deep",     fromlist=["run"]).run(),
        "contact":   lambda: __import__("modes.contact",  fromlist=["run"]).run(),
        "apply":     lambda: __import__("modes.apply",    fromlist=["run"]).run(),
        "pipeline":  lambda: __import__("modes.pipeline", fromlist=["run"]).run(),
        "compare":   lambda: __import__("modes.compare",  fromlist=["run"]).run(),
        "training":  lambda: __import__("modes.training", fromlist=["run"]).run(),
        "project":   lambda: __import__("modes.project",  fromlist=["run"]).run(),
        "setup":     lambda: __import__("modes.setup",    fromlist=["run_setup"]).run_setup(),
        "stats":     lambda: __import__("modes.stats",    fromlist=["run"]).run(),
        "autoapply": lambda: __import__("modes.autoapply",fromlist=["run"]).run(),
        "outreach":  lambda: __import__("modes.outreach", fromlist=["run"]).run(),
        "followups": lambda: __import__("modes.outreach", fromlist=["run"]).run(),
    }
    if cmd in handlers:
        handlers[cmd]()
    else:
        console.print(f"[red]Unknown command:[/red] {cmd}")
        show_help()

def interactive_mode():
    console.print("[dim]Enter a command (or 'quit' to exit):[/dim]")
    while True:
        try:
            cmd = console.input("\n[bold cyan]career-ops>[/bold cyan] ").strip().lower()
            if cmd in ("quit", "exit", "q"):
                break
            if cmd:
                dispatch(cmd)
        except (KeyboardInterrupt, EOFError):
            break
    console.print("\n[dim]Bye![/dim]")

if __name__ == "__main__":
    main()