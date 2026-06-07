"""
Mode: apply — Draft answers to application form questions.
NEVER auto-submits. Always human-in-the-loop.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from gemini_client import ask
from shared import build_context

console = Console()

APPLY_SYSTEM = """You are an expert career coach helping draft compelling application answers.
Your answers should:
- Be specific and use real examples from the CV (never invent)
- Match the tone of the company (startup = casual; enterprise = formal)  
- Be honest and avoid buzzword soup
- Follow the STAR format for behavioral questions
- Be concise (respect word limits when given)

CRITICAL: You only draft answers. You NEVER submit applications. The human always reviews first."""

def run():
    console.print(Panel.fit("[bold cyan]Application Form Helper[/bold cyan]", border_style="cyan"))
    console.print("[yellow]⚠️  This tool drafts answers only. YOU always review and submit.[/yellow]\n")

    context = build_context()

    company = Prompt.ask("Company name")
    role = Prompt.ask("Role title")

    console.print("\n[dim]Paste the application questions below (one per line, or numbered).")
    console.print("Press Enter twice when done:[/dim]\n")

    lines = []
    empty_count = 0
    while empty_count < 2:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            empty_count += 1
        else:
            empty_count = 0
            lines.append(line)

    questions = "\n".join(lines).strip()
    if not questions:
        console.print("[red]No questions provided.[/red]")
        return

    console.print(f"\n[bold cyan]✍️  Drafting answers for {company}...[/bold cyan]\n")
    console.print("─" * 60)

    prompt = f"""
## Candidate Context
{context}

## Company & Role
Company: {company}
Role: {role}

## Application Questions
{questions}

For EACH question, provide:
1. A draft answer (concise, specific, from real CV data)
2. [Optional: Word count if they specified a limit]
3. A brief note on how to personalize further

Format each answer clearly with the question as a header.
Be specific. Use metrics from the CV. Never fabricate.
End with a reminder: "Review all answers carefully before submitting. You own this application."
"""

    ask(prompt, system=APPLY_SYSTEM)
    console.print("\n" + "─" * 60)
    console.print("\n[bold yellow]⚠️  Review all answers above before submitting your application.[/bold yellow]")
    console.print("[dim]This tool only drafts — you always make the final decision.[/dim]")
