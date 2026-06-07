"""
Mode: compare — Compare two or more job offers side by side.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt

from gemini_client import ask
from shared import build_context

console = Console()

def run():
    console.print(Panel.fit("[bold cyan]Offer Comparison[/bold cyan]", border_style="cyan"))

    context = build_context()
    num_offers = IntPrompt.ask("How many offers to compare?", default=2)

    offers = []
    for i in range(num_offers):
        console.print(f"\n[bold]Offer {i+1}[/bold] — Paste JD or description (Enter twice when done):\n")
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
        offers.append("\n".join(lines).strip())

    offers_text = "\n\n---\n\n".join(
        [f"## Offer {i+1}\n{o}" for i, o in enumerate(offers)]
    )

    console.print("\n[bold cyan]🤖 Comparing offers...[/bold cyan]\n")

    prompt = f"""
## Candidate Context
{context}

## Offers to Compare
{offers_text}

Please provide:
1. Side-by-side comparison table (role, company, comp, growth, culture, remote, overall score)
2. Strengths and weaknesses of each
3. Clear recommendation: which to prioritize and why
4. Negotiation tips for the preferred offer
"""

    ask(prompt, system="You are an expert career advisor. Compare job offers objectively and give clear, actionable recommendations.")
