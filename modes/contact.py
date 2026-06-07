"""
Mode: contact — Draft personalized LinkedIn outreach messages.
"""

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from gemini_client import ask
from shared import build_context

console = Console()

CONTACT_SYSTEM = """You are an expert at professional networking and LinkedIn outreach.
Write authentic, personalized messages that don't sound like templates.
Keep messages concise (under 300 characters for connection requests, under 1000 for InMail).
Never be sycophantic or generic. Be direct and human."""

def run():
    console.print(Panel.fit("[bold cyan]LinkedIn Outreach Drafter[/bold cyan]", border_style="cyan"))

    context = build_context()

    contact_name = Prompt.ask("\nContact's name")
    contact_role = Prompt.ask("Their role / title")
    company = Prompt.ask("Their company")
    purpose = Prompt.ask(
        "Purpose",
        choices=["referral", "coffee-chat", "job-inquiry", "after-applying", "after-interview"],
        default="referral"
    )
    notes = Prompt.ask("Any specific context or connection? (optional)", default="")

    console.print(f"\n[bold cyan]✍️  Drafting outreach to {contact_name}...[/bold cyan]\n")
    console.print("─" * 60)

    purpose_guides = {
        "referral": "Ask for a referral or internal recommendation. Be specific about the role.",
        "coffee-chat": "Request a 15-min call to learn about their experience at the company.",
        "job-inquiry": "Inquire about open roles or the hiring process.",
        "after-applying": "Follow up after submitting an application.",
        "after-interview": "Follow up after an interview to reiterate interest.",
    }

    prompt = f"""
## My Profile
{context}

## Contact
Name: {contact_name}
Role: {contact_role}
Company: {company}
Context: {notes if notes else 'No specific context'}

## Purpose
{purpose_guides.get(purpose, purpose)}

Please write 2 versions:

### Version 1: Connection Request (under 300 chars)
[Ultra concise, for sending with a connection request]

### Version 2: InMail / Follow-up Message (under 800 chars)
[More detailed, for after connecting or as a direct InMail]

### Notes on personalization
[1-2 sentences on how to make this more personal if they do more research]

Make both authentic, specific to {contact_name}'s role at {company}, and not templated.
"""

    ask(prompt, system=CONTACT_SYSTEM)
    console.print("\n" + "─" * 60)
