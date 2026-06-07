"""
Mode: pipeline — Process all pending URLs in data/pipeline.md one by one.
"""

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
import re

from modes.evaluate import run as evaluate_run

console = Console()

def run():
    console.print(Panel.fit("[bold cyan]Pipeline Processor[/bold cyan]", border_style="cyan"))

    pipeline_path = Path("data/pipeline.md")
    if not pipeline_path.exists():
        console.print("[yellow]data/pipeline.md not found.[/yellow]")
        return

    content = pipeline_path.read_text()
    urls = re.findall(r'https?://[^\s<>\[\]"\'~]+', content)
    urls = list(dict.fromkeys(urls))  # dedup

    if not urls:
        console.print("[dim]No pending URLs in pipeline.md.[/dim]")
        return

    console.print(f"[green]{len(urls)} pending URL(s):[/green]")
    for i, url in enumerate(urls, 1):
        console.print(f"  {i}. {url}")

    for i, url in enumerate(urls, 1):
        console.print(f"\n[bold]─── Job {i}/{len(urls)} ───[/bold]")
        console.print(f"[dim]{url}[/dim]")

        if not Confirm.ask("Evaluate this one?", default=True):
            continue

        import sys
        original_argv = sys.argv[:]
        # Inject URL as input via monkeypatching input()
        import builtins
        original_input = builtins.input
        url_injected = [False]

        def patched_input(prompt_str=""):
            if not url_injected[0]:
                url_injected[0] = True
                print(url)  # Show what we're inputting
                return url
            return ""  # Return empty to signal end of input

        builtins.input = patched_input
        try:
            evaluate_run()
        finally:
            builtins.input = original_input
