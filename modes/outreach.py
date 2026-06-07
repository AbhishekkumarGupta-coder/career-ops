"""
Mode: outreach - Recruiter outreach agent with follow-up scheduling.

Workflow:
  1. Find recruiter name/email from job URL or manual entry
  2. Gemini drafts a personalised cold email from your CV
  3. You review and edit
  4. Send via SMTP (Gmail) or copy to clipboard
  5. Follow-up reminder saved to data/followups.md
  6. Run 'python main.py outreach --followups' to see pending follow-ups
"""

import re
import smtplib
import ssl
from pathlib import Path
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

from gemini_client import ask, ask_json
from shared import build_context, load_profile
from fetcher import fetch_job_page

console = Console()

EMAIL_SYSTEM = """You are an expert at cold email outreach for job seekers.
Write emails that:
- Sound like a real human wrote them, not a template
- Reference something specific about the company or role
- Lead with value (what you bring), not with need (please give me a job)
- Are short — under 200 words for cold email, under 150 for follow-up
- Have a clear, single call to action
- Never use phrases like "I hope this email finds you well", "I am writing to express my interest", "I am passionate about"
- Never attach a CV in the first email — offer to share on request
Return ONLY the email subject and body, no explanation."""

FOLLOWUP_SYSTEM = """Write a short, human follow-up email.
3-4 sentences max. Reference the original email naturally.
Ask if they had a chance to look at your note.
Keep it warm but not desperate. Under 100 words."""


def run():
    import sys
    if "--followups" in sys.argv or "followups" in sys.argv:
        _show_followups()
        return

    console.print(Panel.fit(
        "[bold cyan]Recruiter Outreach Agent[/bold cyan]\n"
        "[dim]Cold emails that sound human. Follow-ups that don't annoy.[/dim]",
        border_style="cyan"
    ))

    # ── Mode selection ────────────────────────────────────────────
    mode = Prompt.ask(
        "\nWhat do you want to do?",
        choices=["cold-email", "follow-up", "thank-you", "check-followups"],
        default="cold-email"
    )

    if mode == "check-followups":
        _show_followups()
        return
    elif mode == "follow-up":
        _run_followup()
        return
    elif mode == "thank-you":
        _run_thankyou()
        return
    else:
        _run_cold_email()


def _run_cold_email():
    """Draft and optionally send a cold outreach email."""
    context   = build_context()
    profile   = load_profile()

    # ── Gather info ───────────────────────────────────────────────
    console.print("\n[bold]Tell me about the target:[/bold]")
    recruiter_name    = Prompt.ask("  Recruiter / hiring manager name")
    recruiter_email   = Prompt.ask("  Their email address")
    company           = Prompt.ask("  Company name")
    role              = Prompt.ask("  Role you are targeting")
    job_url           = Prompt.ask("  Job URL (optional, for context)", default="")
    personal_note     = Prompt.ask("  Any specific hook? (mutual contact, their blog post, etc.)", default="")

    # Optionally fetch job details for more personalisation
    job_context = ""
    if job_url and job_url.startswith("http"):
        console.print("[dim]Fetching job details for personalisation...[/dim]")
        content = fetch_job_page(job_url)
        if content:
            job_context = content[:2000]

    # ── Draft email ───────────────────────────────────────────────
    console.print(f"\n[bold cyan]Drafting email to {recruiter_name}...[/bold cyan]\n")

    prompt = f"""
## My Profile
{context}

## Target
Name: {recruiter_name}
Company: {company}
Role: {role}
{f'Personal hook: {personal_note}' if personal_note else ''}

## Job Details (for context)
{job_context if job_context else 'Not provided'}

Write a cold outreach email to {recruiter_name} at {company}.
The email should:
- Reference something specific about {company} or the {role} role
- Briefly show 1-2 things from my background most relevant to this role
- Be genuine, not desperate
- End with a soft CTA (15-min call, happy to share CV)

Format your response EXACTLY as:
SUBJECT: <subject line here>
BODY:
<email body here>
"""

    raw = ask(prompt, system=EMAIL_SYSTEM, stream=False)
    subject, body = _parse_email(raw, recruiter_name, company)

    # ── Human review ──────────────────────────────────────────────
    console.print("\n" + "─" * 60)
    console.print(f"[bold]Subject:[/bold] {subject}")
    console.print(f"\n[bold]Body:[/bold]\n{body}")
    console.print("─" * 60)

    action = Prompt.ask(
        "\nWhat to do?",
        choices=["send", "edit-subject", "edit-body", "copy", "save", "discard"],
        default="copy"
    )

    if action == "edit-subject":
        subject = Prompt.ask("New subject", default=subject)
        action  = Prompt.ask("Now?", choices=["send","copy","save","discard"], default="copy")

    if action == "edit-body":
        console.print("[dim]Paste new body (Enter twice to finish):[/dim]")
        lines, empty = [], 0
        while empty < 2:
            line = input()
            if line == "": empty += 1
            else: empty = 0; lines.append(line)
        body   = "\n".join(lines).strip()
        action = Prompt.ask("Now?", choices=["send","copy","save","discard"], default="copy")

    if action == "send":
        _send_email(profile, recruiter_email, subject, body)

    elif action == "copy":
        try:
            import pyperclip
            pyperclip.copy(f"Subject: {subject}\n\n{body}")
            console.print("[green]Copied to clipboard.[/green]")
        except ImportError:
            console.print("[yellow]pyperclip not installed. Run: pip install pyperclip[/yellow]")
            console.print("\n[bold]Subject:[/bold] " + subject)
            console.print("\n[bold]Body:[/bold]\n" + body)

    if action in ("send", "copy", "save"):
        _save_outreach(recruiter_name, recruiter_email, company, role, subject, body)
        _schedule_followup(recruiter_name, recruiter_email, company, role, subject, days=5)
        console.print(f"\n[green]Follow-up reminder set for 5 days from now.[/green]")
        console.print("[dim]Run: python main.py outreach --followups  to see pending follow-ups[/dim]")


def _run_followup():
    """Draft a follow-up to a previous outreach."""
    followups = _load_followups()
    if not followups:
        console.print("[dim]No outreach history found. Run a cold email first.[/dim]")
        return

    console.print("\n[bold]Previous outreach:[/bold]")
    for i, f in enumerate(followups[:10], 1):
        console.print(f"  {i}. {f['name']} @ {f['company']} — sent {f['sent_date']}")

    choice = Prompt.ask("Which to follow up on? (number)", default="1")
    try:
        target = followups[int(choice)-1]
    except (ValueError, IndexError):
        console.print("[red]Invalid choice.[/red]")
        return

    profile = load_profile()
    context = build_context()

    prompt = f"""
## My profile
{context}

## Original email sent on {target['sent_date']}
Subject: {target['subject']}

{target['body']}

Write a short follow-up email to {target['name']} at {target['company']}.
Format as:
SUBJECT: Re: {target['subject']}
BODY:
<body>
"""
    raw     = ask(prompt, system=FOLLOWUP_SYSTEM, stream=False)
    subject, body = _parse_email(raw, target['name'], target['company'])

    console.print("\n" + "─" * 60)
    console.print(f"[bold]Subject:[/bold] {subject}")
    console.print(f"\n[bold]Body:[/bold]\n{body}")
    console.print("─" * 60)

    if Confirm.ask("Send this follow-up?", default=False):
        _send_email(profile, target['email'], subject, body)
    elif Confirm.ask("Copy to clipboard?", default=True):
        try:
            import pyperclip
            pyperclip.copy(f"Subject: {subject}\n\n{body}")
            console.print("[green]Copied.[/green]")
        except ImportError:
            pass

    # Mark as followed up
    _mark_followed_up(target['name'], target['company'])
    console.print("[green]Marked as followed up.[/green]")


def _run_thankyou():
    """Draft a post-interview thank-you email."""
    context          = build_context()
    interviewer_name = Prompt.ask("Interviewer's name")
    company          = Prompt.ask("Company")
    role             = Prompt.ask("Role")
    topic            = Prompt.ask("One specific thing you discussed in the interview")
    email_addr       = Prompt.ask("Their email")

    prompt = f"""
## My profile
{context}

Write a short post-interview thank-you email to {interviewer_name} at {company} for the {role} role.
We discussed: {topic}
Reference that specific topic naturally. Keep it under 120 words.
Do NOT be sycophantic. Be genuine and brief.
Format as:
SUBJECT: <subject>
BODY:
<body>
"""
    raw     = ask(prompt, system=EMAIL_SYSTEM, stream=False)
    subject, body = _parse_email(raw, interviewer_name, company)

    console.print("\n" + "─" * 60)
    console.print(f"[bold]Subject:[/bold] {subject}")
    console.print(f"\n[bold]Body:[/bold]\n{body}")
    console.print("─" * 60)

    profile = load_profile()
    if Confirm.ask("Send?", default=False):
        _send_email(profile, email_addr, subject, body)
    elif Confirm.ask("Copy?", default=True):
        try:
            import pyperclip
            pyperclip.copy(f"Subject: {subject}\n\n{body}")
            console.print("[green]Copied.[/green]")
        except ImportError:
            pass


# ── Email sending via Gmail SMTP ──────────────────────────────────

def _send_email(profile: dict, to_email: str, subject: str, body: str):
    """Send email via Gmail SMTP. Requires GMAIL_ADDRESS + GMAIL_APP_PASSWORD in .env"""
    gmail_addr = _env("GMAIL_ADDRESS")
    gmail_pass = _env("GMAIL_APP_PASSWORD")

    if not gmail_addr or not gmail_pass:
        console.print("[yellow]Gmail not configured.[/yellow]")
        console.print("[dim]Add to .env:\n  GMAIL_ADDRESS=you@gmail.com\n  GMAIL_APP_PASSWORD=your_16_char_app_password[/dim]")
        console.print("[dim]Get app password: Google Account > Security > App passwords[/dim]")
        return

    from_addr  = gmail_addr
    from_name  = profile.get("name", gmail_addr)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{from_name} <{from_addr}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(body, "plain"))

    try:
        context_ssl = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context_ssl) as server:
            server.login(from_addr, gmail_pass)
            server.sendmail(from_addr, to_email, msg.as_string())
        console.print(f"[green]Email sent to {to_email}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to send: {e}[/red]")
        console.print("[dim]Check your GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env[/dim]")


# ── Follow-up tracking ────────────────────────────────────────────

FOLLOWUP_FILE = Path("data/followups.md")

def _schedule_followup(name, email, company, role, subject, days=5):
    FOLLOWUP_FILE.parent.mkdir(exist_ok=True)
    due     = (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")
    sent    = date.today().strftime("%Y-%m-%d")
    entry   = f"| {sent} | {due} | {name} | {email} | {company} | {role} | pending |\n"

    if not FOLLOWUP_FILE.exists():
        FOLLOWUP_FILE.write_text(
            "# Follow-up Tracker\n\n"
            "| Sent | Due | Name | Email | Company | Role | Status |\n"
            "|------|-----|------|-------|---------|------|--------|\n",
            encoding="utf-8"
        )
    content = FOLLOWUP_FILE.read_text(encoding="utf-8")
    FOLLOWUP_FILE.write_text(content.rstrip() + "\n" + entry, encoding="utf-8")


def _show_followups():
    """Show all pending follow-ups."""
    if not FOLLOWUP_FILE.exists():
        console.print("[dim]No follow-ups tracked yet.[/dim]")
        return

    today   = date.today().strftime("%Y-%m-%d")
    rows    = []
    for line in FOLLOWUP_FILE.read_text(encoding="utf-8").splitlines():
        if "|" in line and "Sent" not in line and "---" not in line:
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 7:
                rows.append(parts)

    overdue  = [r for r in rows if r[1] <= today and r[6] == "pending"]
    upcoming = [r for r in rows if r[1] >  today and r[6] == "pending"]

    if overdue:
        console.print(f"\n[bold red]Overdue follow-ups ({len(overdue)}):[/bold red]")
        t = Table(box=box.SIMPLE, show_header=True)
        t.add_column("Due",     width=12)
        t.add_column("Name",    width=18)
        t.add_column("Company", width=18)
        t.add_column("Role",    width=20)
        for r in overdue:
            t.add_row(r[1], r[2], r[4], r[5])
        console.print(t)

    if upcoming:
        console.print(f"\n[bold yellow]Upcoming follow-ups ({len(upcoming)}):[/bold yellow]")
        t = Table(box=box.SIMPLE, show_header=True)
        t.add_column("Due",     width=12)
        t.add_column("Name",    width=18)
        t.add_column("Company", width=18)
        t.add_column("Role",    width=20)
        for r in upcoming:
            t.add_row(r[1], r[2], r[4], r[5])
        console.print(t)

    if not overdue and not upcoming:
        console.print("[green]No pending follow-ups.[/green]")


def _load_followups() -> list:
    if not FOLLOWUP_FILE.exists():
        return []
    rows = []
    for line in FOLLOWUP_FILE.read_text(encoding="utf-8").splitlines():
        if "|" in line and "Sent" not in line and "---" not in line:
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 7:
                rows.append({
                    "sent_date": parts[0], "due": parts[1],
                    "name": parts[2],      "email": parts[3],
                    "company": parts[4],   "role": parts[5],
                    "status": parts[6],    "subject": "", "body": ""
                })
    return rows


def _save_outreach(name, email, company, role, subject, body):
    today    = date.today().strftime("%Y-%m-%d")
    out_dir  = Path("output/outreach")
    out_dir.mkdir(parents=True, exist_ok=True)
    slug     = re.sub(r'[^a-z0-9]+', '-', company.lower())[:20]
    path     = out_dir / f"{today}-{slug}.md"
    path.write_text(
        f"# Outreach: {name} @ {company}\n\n"
        f"**Date:** {today}\n**Role:** {role}\n**Email:** {email}\n\n"
        f"**Subject:** {subject}\n\n---\n\n{body}\n",
        encoding="utf-8"
    )


def _mark_followed_up(name, company):
    if not FOLLOWUP_FILE.exists():
        return
    content = FOLLOWUP_FILE.read_text(encoding="utf-8")
    content = content.replace(
        f"| {name} |", f"| {name} |"
    )
    # Simple mark: replace 'pending' with 'followed-up' for this person
    lines = []
    for line in content.splitlines():
        if name in line and company in line and "pending" in line:
            line = line.replace("pending", "followed-up", 1)
        lines.append(line)
    FOLLOWUP_FILE.write_text("\n".join(lines), encoding="utf-8")


# ── Helpers ───────────────────────────────────────────────────────

def _parse_email(raw: str, name: str, company: str):
    """Extract subject and body from Gemini's formatted response."""
    subject_match = re.search(r"SUBJECT:\s*(.+)", raw, re.IGNORECASE)
    body_match    = re.search(r"BODY:\s*\n(.*)", raw, re.IGNORECASE | re.DOTALL)

    subject = subject_match.group(1).strip() if subject_match else f"Quick note — {company} opportunity"
    body    = body_match.group(1).strip()    if body_match    else raw.strip()
    return subject, body


def _env(key: str) -> str:
    import os
    val = os.environ.get(key, "")
    if not val:
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith(f"{key}="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
    return val