"""
Mode: setup — Onboarding wizard.
Guides user through creating cv.md, config/profile.yml, portals.yml, tracker.
"""

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
import yaml
import shutil
from datetime import date

console = Console()

def run_setup():
    console.print(Panel.fit(
        "[bold cyan]Career-Ops Setup Wizard[/bold cyan]\n"
        "[dim]Let's get you configured in a few steps.[/dim]",
        border_style="cyan"
    ))

    _step_cv()
    _step_profile()
    _step_portals()
    _step_tracker()
    _step_story_bank()
    _done()

def _step_cv():
    console.print("\n[bold yellow]Step 1: Your CV[/bold yellow]")
    cv_path = Path("cv.md")
    if cv_path.exists():
        console.print("[green]✅ cv.md already exists.[/green]")
        if not Confirm.ask("  Overwrite it?", default=False):
            return

    console.print("""
I don't have your CV yet. How would you like to provide it?
  [bold]1[/bold] — Paste your CV text (I'll convert to markdown)
  [bold]2[/bold] — I'll type my experience now
  [bold]3[/bold] — Skip for now (fill cv.md manually)
""")
    choice = Prompt.ask("Choice", choices=["1", "2", "3"], default="3")

    if choice == "1":
        console.print("[dim]Paste your CV below. Press Enter twice when done:[/dim]")
        lines = []
        empty_count = 0
        while empty_count < 2:
            line = input()
            if line == "":
                empty_count += 1
            else:
                empty_count = 0
            lines.append(line)
        raw_cv = "\n".join(lines).strip()

        from gemini_client import ask_structured
        console.print("\n[dim]Converting to clean markdown CV...[/dim]")
        md_cv = ask_structured(
            f"Convert this CV to clean, well-structured markdown with sections: Summary, Experience, Education, Skills, Projects (if any). Keep all metrics and details. Raw CV:\n\n{raw_cv}",
            system="You are a professional CV formatter. Output only the markdown CV, nothing else."
        )
        cv_path.write_text(md_cv, encoding="utf-8")
        console.print("[green]✅ cv.md created.[/green]")

    elif choice == "2":
        console.print("[dim]Tell me about your experience. I'll draft a CV. Press Enter twice when done:[/dim]")
        lines = []
        empty_count = 0
        while empty_count < 2:
            line = input()
            if line == "":
                empty_count += 1
            else:
                empty_count = 0
            lines.append(line)
        experience = "\n".join(lines).strip()

        from gemini_client import ask_structured
        console.print("\n[dim]Drafting your CV...[/dim]")
        md_cv = ask_structured(
            f"Draft a professional markdown CV based on this experience description. Include sections: Summary, Experience, Education, Skills. Make it ATS-friendly.\n\nExperience:\n{experience}",
            system="You are a professional CV writer. Output only the markdown CV."
        )
        cv_path.write_text(md_cv, encoding="utf-8")
        console.print("[green]✅ cv.md created. Review and edit it anytime.[/green]")

    else:
        # Create blank template
        if not cv_path.exists():
            cv_path.write_text("""# Your Name

## Summary
[Write your professional summary here]

## Experience

### Job Title - Company Name (YYYY-YYYY)
- Achievement 1
- Achievement 2

## Education
### Degree - University (YYYY)

## Skills
- Skill 1, Skill 2, Skill 3
""", encoding="utf-8")
            console.print("[yellow]📝 Blank cv.md template created. Edit it before evaluating jobs.[/yellow]")

def _step_profile():
    console.print("\n[bold yellow]Step 2: Your Profile[/bold yellow]")
    profile_path = Path("config/profile.yml")
    profile_path.parent.mkdir(exist_ok=True)

    existing = {}
    if profile_path.exists():
        existing = yaml.safe_load(profile_path.read_text()) or {}
        console.print("[green]✅ config/profile.yml already exists.[/green]")
        if not Confirm.ask("  Update it?", default=True):
            return

    console.print("[dim]A few quick questions to personalize the system:[/dim]\n")

    name = Prompt.ask("  Full name", default=existing.get("name", ""))
    email = Prompt.ask("  Email", default=existing.get("email", ""))
    location = Prompt.ask("  Location (city, country)", default=existing.get("location", ""))
    target_roles = Prompt.ask("  Target roles (e.g. 'Senior Backend Engineer, AI Product Manager')",
                               default=existing.get("target_roles", ""))
    salary_target = Prompt.ask("  Salary target range (e.g. '$120k-$160k')",
                                default=existing.get("salary_target", ""))
    preferences = Prompt.ask("  Preferences (e.g. 'remote-first, no travel, startup ok')",
                              default=existing.get("preferences", ""))
    avoid = Prompt.ask("  Things to avoid (e.g. 'no consulting, no on-call')",
                       default=existing.get("avoid", ""))

    profile = {
        "name": name,
        "email": email,
        "location": location,
        "target_roles": target_roles,
        "salary_target": salary_target,
        "preferences": preferences,
        "avoid": avoid,
        "scoring_weights": existing.get("scoring_weights", {
            "role_match": 0.25,
            "compensation": 0.20,
            "company_quality": 0.20,
            "growth": 0.15,
            "culture_fit": 0.10,
            "location_remote": 0.10,
        })
    }

    profile_path.write_text(yaml.dump(profile, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    console.print("[green]✅ config/profile.yml saved.[/green]")

def _step_portals():
    console.print("\n[bold yellow]Step 3: Job Portals[/bold yellow]")
    portals_path = Path("portals.yml")

    if portals_path.exists():
        console.print("[green]✅ portals.yml already exists.[/green]")
        return

    template = Path("templates/portals.example.yml")
    if template.exists():
        shutil.copy(template, portals_path)
        console.print("[green]✅ portals.yml created from template.[/green]")
    else:
        # Create default portals config
        portals = {
            "search_queries": [
                "AI engineer site:greenhouse.io",
                "machine learning engineer site:lever.co",
                "applied AI site:ashbyhq.com",
            ],
            "companies": [
                {"name": "Anthropic",   "url": "https://www.anthropic.com/careers"},
                {"name": "OpenAI",      "url": "https://openai.com/careers"},
                {"name": "Mistral",     "url": "https://mistral.ai/careers"},
                {"name": "ElevenLabs",  "url": "https://elevenlabs.io/careers"},
                {"name": "Retool",      "url": "https://retool.com/careers"},
                {"name": "Vercel",      "url": "https://vercel.com/careers"},
                {"name": "n8n",         "url": "https://n8n.io/careers"},
            ],
            "title_filter": {
                "positive": ["AI", "ML", "machine learning", "LLM", "applied AI", "engineer"],
                "negative": ["intern", "junior", "VP", "C-level"]
            }
        }
        portals_path.write_text(yaml.dump(portals, default_flow_style=False, allow_unicode=True), encoding="utf-8")
        console.print("[green]✅ portals.yml created with defaults.[/green]")

def _step_tracker():
    console.print("\n[bold yellow]Step 4: Application Tracker[/bold yellow]")
    tracker = Path("data/applications.md")
    tracker.parent.mkdir(exist_ok=True)

    if not tracker.exists():
        tracker.write_text(
            "# Applications Tracker\n\n"
            "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
            "|---|------|---------|------|-------|--------|-----|--------|-------|\n",
            encoding="utf-8"
        )
        console.print("[green]✅ data/applications.md created.[/green]")
    else:
        console.print("[green]✅ Tracker already exists.[/green]")

    pipeline = Path("data/pipeline.md")
    if not pipeline.exists():
        pipeline.write_text(
            "# Pending Job URLs\n\n"
            "Add job URLs below, one per line. Run `python main.py pipeline` to process them.\n\n"
            "<!-- Example:\nhttps://company.com/jobs/ai-engineer\n-->\n",
            encoding="utf-8"
        )
        console.print("[green]✅ data/pipeline.md created.[/green]")

def _step_story_bank():
    console.print("\n[bold yellow]Step 5: Interview Story Bank[/bold yellow]")
    story_bank = Path("interview-prep/story-bank.md")
    story_bank.parent.mkdir(exist_ok=True)

    if not story_bank.exists():
        story_bank.write_text(
            "# Interview Story Bank (STAR+R)\n\n"
            "Stories accumulate here from each job evaluation.\n"
            "Format: Situation - Task - Action - Result - Reflection\n\n",
            encoding="utf-8"
        )
        console.print("[green]✅ interview-prep/story-bank.md created.[/green]")
    else:
        console.print("[green]✅ Story bank already exists.[/green]")

def _done():
    console.print(Panel(
        "[bold green]✅ Setup complete![/bold green]\n\n"
        "You can now:\n"
        "  • [bold]python main.py evaluate[/bold]  — Evaluate a job offer\n"
        "  • [bold]python main.py scan[/bold]       — Scan job portals\n"
        "  • [bold]python main.py tracker[/bold]    — View your pipeline\n"
        "  • [bold]python main.py pdf[/bold]        — Generate your CV PDF\n\n"
        "[dim]Tip: Edit cv.md and portals.yml anytime to customize.[/dim]",
        border_style="green",
        title="Career-Ops Ready"
    ))
    