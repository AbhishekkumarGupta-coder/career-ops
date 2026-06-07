"""
Mode: deep — Deep company research before applying or interviewing.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from gemini_client import ask
from shared import build_context

console = Console()

DEEP_SYSTEM = """You are a corporate intelligence analyst and career advisor. 
Your job is to research companies deeply to help candidates make informed decisions.
Be specific, balanced, and honest. Include both positives and red flags when relevant."""

def run():
    console.print(Panel.fit("[bold cyan]Deep Company Research[/bold cyan]", border_style="cyan"))

    company = Prompt.ask("\nCompany name")
    role = Prompt.ask("Role you're targeting (optional)", default="")

    context = build_context()

    console.print(f"\n[bold cyan]🔍 Researching {company}...[/bold cyan]\n")
    console.print("─" * 60)

    prompt = f"""
## Candidate Context
{context}

## Research Target
Company: {company}
Role: {role if role else 'Not specified'}

Please provide deep company research covering:

### 1. Company Overview
- What they do, business model, stage (startup/scaleup/enterprise)
- Key products/services
- Founded, HQ, size

### 2. Financial Health & Stability
- Funding status / public company financials
- Recent funding rounds or IPO details
- Burn rate concerns if applicable
- Revenue/growth trajectory if known

### 3. Technology Stack & Engineering Culture
- Known tech stack and architecture choices
- Engineering blog, open source presence
- How they're perceived by engineers (Glassdoor signals, Twitter/X buzz)

### 4. Market Position
- Main competitors
- Differentiation and moat
- Market share / growth trajectory

### 5. Culture & People
- CEO and leadership team background
- Team turnover signals
- Remote/hybrid policy
- DEI and culture indicators

### 6. Red Flags & Risks
- Any concerning signals (layoffs, pivots, leadership changes)
- Glassdoor rating and common complaints
- Funding risks

### 7. Interview Intel
- Known interview process
- Common interview questions (if known)
- Tips for standing out at {company}

### 8. Candidate Verdict
Given this candidate's profile, should they prioritize this company? Why/why not?
What's the best angle to approach their application?
"""

    ask(prompt, system=DEEP_SYSTEM)
    console.print("\n" + "─" * 60)

    from pathlib import Path
    from datetime import date
    from rich.prompt import Confirm

    if Confirm.ask("\n💾 Save research report?", default=True):
        today = date.today().strftime("%Y-%m-%d")
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', company.lower())[:30]
        path = Path(f"reports/research-{slug}-{today}.md")
        path.parent.mkdir(exist_ok=True)
        # Re-generate without streaming to save
        from gemini_client import ask_structured
        content = ask_structured(prompt, system=DEEP_SYSTEM)
        path.write_text(f"# Company Research: {company}\n**Date:** {today}\n\n{content}")
        console.print(f"[green]✅ Saved: {path}[/green]")
