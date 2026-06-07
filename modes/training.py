"""
Mode: training — Evaluate whether a course/certification is worth pursuing.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from gemini_client import ask
from shared import build_context

console = Console()

def run():
    console.print(Panel.fit("[bold cyan]Course/Certification Evaluator[/bold cyan]", border_style="cyan"))

    context = build_context()

    course = Prompt.ask("\nCourse or certification name")
    provider = Prompt.ask("Provider (e.g. Coursera, AWS, Google)", default="")
    cost = Prompt.ask("Cost", default="Free")
    time_commit = Prompt.ask("Time commitment", default="Unknown")

    console.print(f"\n[bold cyan]🎓 Evaluating: {course}...[/bold cyan]\n")

    prompt = f"""
## Candidate Context
{context}

## Course/Certification
Name: {course}
Provider: {provider}
Cost: {cost}
Time: {time_commit}

Evaluate:
1. Market value — How much do employers care about this cert?
2. Skill gap — Does the candidate actually need this based on their CV?
3. ROI — Is the time/money worth it given their targets?
4. Alternatives — Better options to achieve the same goal?
5. Verdict: WORTH IT / SKIP / MAYBE with clear reasoning
"""

    ask(prompt, system="You are a career development advisor. Be honest about whether certifications are worth the investment.")
