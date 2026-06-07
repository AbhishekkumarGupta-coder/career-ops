"""
Mode: project — Evaluate a portfolio project's career impact.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from gemini_client import ask
from shared import build_context

console = Console()

def run():
    console.print(Panel.fit("[bold cyan]Portfolio Project Evaluator[/bold cyan]", border_style="cyan"))

    context = build_context()

    project_name = Prompt.ask("\nProject name")
    description = Prompt.ask("What does it do? (brief description)")
    tech_stack = Prompt.ask("Tech stack used")
    status = Prompt.ask("Status", choices=["idea", "in-progress", "completed", "deployed"], default="completed")

    console.print(f"\n[bold cyan]🛠️  Evaluating project: {project_name}...[/bold cyan]\n")

    prompt = f"""
## Candidate Context
{context}

## Portfolio Project
Name: {project_name}
Description: {description}
Tech Stack: {tech_stack}
Status: {status}

Evaluate this project for career impact:
1. Relevance — How well does this project support their target roles?
2. Differentiation — Is this unique or is it another todo-app/weather-app?
3. Presentation tips — How to describe it in CV, interviews, LinkedIn
4. Missing pieces — What would make this project more impressive?
5. Related project ideas — 2-3 project ideas that would complement this
6. Verdict: HIGH / MEDIUM / LOW career impact with reasoning
"""

    ask(prompt, system="You are a senior engineering hiring manager and career coach. Be direct about what impresses employers.")
