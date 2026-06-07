"""
Mode: evaluate - Core job offer evaluation pipeline.
Scores offer A-F across 6 blocks, writes report, updates tracker.
"""

from pathlib import Path
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
import re

from gemini_client import ask, ask_json
from shared import build_context, get_next_report_number, save_tracker_entry, load_story_bank
from fetcher import fetch_job_page

console = Console()

# Known placeholder / fake URLs — skip immediately
_FAKE_URL_PATTERNS = [
    "company.com/jobs",
    "example.com",
    "yourcompany.com",
    "placeholder.com",
    "test.com/jobs",
    "sample.com",
    "localhost",
    "127.0.0.1",
]

# If fetched content contains these strings it's a 404 / error page
_DEAD_PAGE_SIGNALS = [
    "page does not exist",
    "page not found",
    "404 not found",
    "this page could not be found",
    "sorry, the page",
    "no longer available",
    "job listing has expired",
    "job has been filled",
    "position has been filled",
    "this job is no longer",
]

EVAL_SYSTEM = """You are an expert career advisor and recruiter. Your job is to evaluate job offers
with brutal honesty. You help candidates find roles worth their time - not spray applications everywhere.

SCORING RUBRIC (each 0-5, weighted):
- Role Match (25%): How well does the JD match the candidate's skills and target roles?
- Compensation (20%): Is comp competitive for their experience and location?
- Company Quality (20%): Team, funding, product-market fit, growth trajectory?
- Growth (15%): Career growth potential, learning opportunities, trajectory?
- Culture Fit (10%): Values, work style, team dynamics alignment?
- Location/Remote (10%): Does work arrangement match preferences?

Overall score = weighted average. Grade: A(4.5+) B(3.5-4.4) C(2.5-3.4) D(1.5-2.4) F(<1.5)

EVALUATION BLOCKS:
1. Role Summary - What is this role actually about?
2. CV Match Analysis - Specific strengths vs gaps
3. Level & Strategy - Seniority fit, negotiation approach
4. Compensation Research - Market rate estimate, red flags
5. Personalization - What makes THIS candidate uniquely strong for this role
6. Interview Prep (STAR+R) - 3 behavioral stories tailored to this role

IMPORTANT: Be direct, specific, and honest. If the score is below 3.0, say clearly this is a weak match.
Never recommend applying to anything under 3.0 without a specific strategic reason.

CRITICAL: If the job content is empty, all NA, a 404 page, or contains no real job details,
do NOT produce a fake evaluation. Instead respond with exactly:
INVALID_JD: <reason why you cannot evaluate>"""


def run():
    console.print(Panel.fit("[bold cyan]Job Offer Evaluator[/bold cyan]", border_style="cyan"))

    console.print("\n[dim]Paste the job URL or job description below.\nPress Enter twice when done.[/dim]\n")

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

    jd_input = "\n".join(lines).strip()
    if not jd_input:
        console.print("[red]No input provided. Skipping.[/red]")
        return

    # ── Fix #5: Placeholder / fake URL detection ──────────────────
    if jd_input.startswith("http"):
        job_url = jd_input.split()[0].lower()
        for pattern in _FAKE_URL_PATTERNS:
            if pattern in job_url:
                console.print(f"[yellow]Skipping placeholder URL: {job_url}[/yellow]")
                console.print("[dim]Add a real job URL to data/pipeline.md and try again.[/dim]")
                return

    # ── Fetch URL if real ─────────────────────────────────────────
    job_content = jd_input
    job_url = None

    if jd_input.startswith("http"):
        job_url = jd_input.split()[0]
        console.print(f"\n[dim]Fetching: {job_url}[/dim]")
        job_content = fetch_job_page(job_url)

        # Fix #2: Stop evaluating broken URLs
        if not job_content or len(job_content.strip()) < 100:
            console.print("[red]Could not fetch page content. Skipping.[/red]")
            console.print("[dim]Try pasting the job description directly instead.[/dim]")
            return

        # Fix #2: Detect 404 / expired / dead pages
        content_lower = job_content.lower()
        for signal in _DEAD_PAGE_SIGNALS:
            if signal in content_lower:
                console.print(f"[red]Page appears to be a 404 or expired listing ({signal!r}). Skipping.[/red]")
                return

    # ── Validate pasted JD has enough content ────────────────────
    if len(jd_input.strip()) < 80 and not job_url:
        console.print("[red]Job description is too short to evaluate. Paste the full JD.[/red]")
        return

    # ── Run evaluation ────────────────────────────────────────────
    context = build_context()
    story_bank = load_story_bank()

    console.print("\n[bold cyan]Evaluating offer...[/bold cyan]\n")
    console.print("-" * 60)

    prompt = f"""
## Candidate Context
{context}

## Existing Story Bank (don't repeat these exact stories)
{story_bank if story_bank else "None yet."}

## Job Offer to Evaluate
URL: {job_url or 'Pasted directly'}

{job_content}

---

Please provide a complete evaluation following the 6-block structure:

### 1. Role Summary
[2-3 sentences: what this role is really about]

### 2. CV Match Analysis
**Strengths:** [3-5 specific matches]
**Gaps:** [honest assessment of gaps]
**Overall fit:** [1-2 sentences]

### 3. Level & Strategy
[Seniority assessment, how to position, negotiation angle]

### 4. Compensation Research
[Market rate estimate for this role/location, red/green flags in JD]

### 5. Personalization - Why This Candidate
[3-5 specific reasons this candidate is strong for THIS role]

### 6. Interview Prep (STAR+R)
[3 behavioral stories tailored to this role's likely questions]
- Story 1: [Title] - S/T/A/R/Reflection
- Story 2: [Title] - S/T/A/R/Reflection
- Story 3: [Title] - S/T/A/R/Reflection

---

### Score Breakdown
| Dimension | Score /5 | Notes |
|-----------|----------|-------|
| Role Match (25%) | X.X | |
| Compensation (20%) | X.X | |
| Company Quality (20%) | X.X | |
| Growth (15%) | X.X | |
| Culture Fit (10%) | X.X | |
| Location/Remote (10%) | X.X | |
| **OVERALL** | **X.X/5** | **Grade: X** |

### Recommendation
[Clear GO / NO-GO / CONDITIONAL with reasoning]
"""

    report_text = ask(prompt, system=EVAL_SYSTEM)

    # Fix #2 + #3: Detect invalid evaluation from Gemini
    if report_text.strip().startswith("INVALID_JD:"):
        reason = report_text.strip().replace("INVALID_JD:", "").strip()
        console.print(f"\n[red]Cannot evaluate: {reason}[/red]")
        console.print("[dim]Skipping save — no valid job data found.[/dim]")
        return

    # Extract score and grade
    score, grade = _extract_score(report_text)

    # Fix #3: Skip saving invalid/empty reports
    if grade == "?" or (score == 0.0 and grade == "?"):
        console.print("\n[red]Evaluation returned no valid score. Skipping save.[/red]")
        console.print("[dim]The job content may not have contained enough information.[/dim]")
        return

    company, role_title = _extract_meta(report_text, job_content)

    # Fix #3: Skip saving if company/role are still unknown
    if company in ("Unknown", "Unknown Company", "NA", "N/A") and \
       role_title in ("Unknown Role", "NA", "N/A"):
        console.print("\n[red]Could not identify company or role. Skipping save.[/red]")
        console.print("[dim]Use a real job URL or paste the full job description.[/dim]")
        return

    console.print("\n" + "-" * 60)
    _print_verdict(score, grade, company, role_title)

    # Speak verdict via Sarvam (optional)
    try:
        from voice import speak_summary
        speak_summary(score, grade, company, role_title, language="en-IN")
    except Exception:
        pass

    # Fix #3: Only save valid reports
    if Confirm.ask("\nSave evaluation report?", default=True):
        num = get_next_report_number()
        today = date.today().strftime("%Y-%m-%d")
        slug = re.sub(r'[^a-z0-9]+', '-', company.lower())[:20].strip('-')
        report_path = Path(f"reports/{num:03d}-{slug}-{today}.md")
        report_path.parent.mkdir(exist_ok=True)

        full_report = (
            f"# {company} - {role_title}\n\n"
            f"**Date:** {today}\n"
            f"**Score:** {score}/5 (Grade: {grade})\n"
            f"**URL:** {job_url or 'N/A'}\n\n"
            f"---\n\n"
            f"{report_text}\n"
        )
        report_path.write_text(full_report, encoding="utf-8")
        console.print(f"[green]Report saved: {report_path}[/green]")

        save_tracker_entry({
            "num":     num,
            "date":    today,
            "company": company,
            "role":    role_title,
            "score":   f"{score}/5",
            "status":  "Evaluated",
            "pdf":     "-",
            "report":  f"[{num:03d}]({report_path})",
            "notes":   f"Grade {grade}",
        })
        console.print("[green]Added to tracker.[/green]")
        _update_story_bank(report_text)


# ── Helpers ───────────────────────────────────────────────────────

def _extract_score(report: str):
    """Extract numeric score and grade from evaluation report."""
    match = re.search(r'\*\*OVERALL\*\*.*?(\d+\.?\d*)/5.*?Grade:\s*([A-F])', report, re.IGNORECASE)
    if match:
        return float(match.group(1)), match.group(2)
    match = re.search(r'(\d+\.?\d*)/5.*?Grade:\s*([A-F])', report, re.IGNORECASE)
    if match:
        return float(match.group(1)), match.group(2)
    return 0.0, "?"


def _extract_meta(report: str, jd: str) -> tuple:
    """Extract company name and role title from job content."""
    try:
        result = ask_json(
            f"Extract the company name and job title from this job description. "
            f"Return JSON with keys 'company' and 'role'. "
            f"If you cannot find them, return 'Unknown' for each.\n\nText:\n{jd[:2000]}"
        )
        company   = result.get("company", "Unknown") or "Unknown"
        role      = result.get("role",    "Unknown Role") or "Unknown Role"
        # Reject generic placeholder values
        if company.upper() in ("NA", "N/A", "NONE", "NULL", ""):
            company = "Unknown"
        if role.upper() in ("NA", "N/A", "NONE", "NULL", ""):
            role = "Unknown Role"
        return company, role
    except Exception:
        return "Unknown", "Unknown Role"


def _print_verdict(score: float, grade: str, company: str, role: str):
    colors = {"A": "green", "B": "cyan", "C": "yellow", "D": "red", "F": "red"}
    color  = colors.get(grade, "white")
    rec    = {
        "A": "[GO] STRONG MATCH - Apply immediately",
        "B": "[GO] Good opportunity",
        "C": "[!] CONDITIONAL - Review carefully",
        "D": "[NO] WEAK MATCH - Reconsider",
        "F": "[NO-GO] Not worth applying",
    }.get(grade, "No recommendation")

    console.print(Panel(
        f"[bold]{company}[/bold] - {role}\n\n"
        f"Score: [{color}]{score}/5[/{color}]   Grade: [{color}]{grade}[/{color}]\n\n"
        f"{rec}",
        border_style=color,
        title="Evaluation Result"
    ))


def _update_story_bank(report: str):
    """Extract STAR stories and append to interview story bank."""
    story_section = re.search(r'### 6\. Interview Prep.*?(?=###|$)', report, re.DOTALL)
    if not story_section:
        return
    story_bank_path = Path("interview-prep/story-bank.md")
    story_bank_path.parent.mkdir(exist_ok=True)
    existing    = story_bank_path.read_text(encoding="utf-8") \
                  if story_bank_path.exists() \
                  else "# Interview Story Bank (STAR+R)\n\n"
    new_stories = story_section.group(0).strip()
    today       = date.today().strftime("%Y-%m-%d")
    story_bank_path.write_text(
        existing.rstrip() + f"\n\n---\n\n## Added {today}\n\n{new_stories}\n",
        encoding="utf-8"
    )