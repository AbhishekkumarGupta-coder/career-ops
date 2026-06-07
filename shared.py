"""
Shared context loader.
Reads cv.md, config/profile.yml, article-digest.md into a context string
that all modes can inject into their prompts.
"""

from pathlib import Path
import yaml

def load_cv() -> str:
    p = Path("cv.md")
    return p.read_text(encoding="utf-8") if p.exists() else "[cv.md not found]"

def load_profile() -> dict:
    p = Path("config/profile.yml")
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}

def load_article_digest() -> str:
    p = Path("article-digest.md")
    return p.read_text(encoding="utf-8") if p.exists() else ""

def load_story_bank() -> str:
    p = Path("interview-prep/story-bank.md")
    return p.read_text(encoding="utf-8") if p.exists() else ""

def build_context() -> str:
    profile = load_profile()
    cv = load_cv()
    digest = load_article_digest()

    ctx = f"""## Candidate Profile
Name: {profile.get('name', 'Not set')}
Email: {profile.get('email', 'Not set')}
Location: {profile.get('location', 'Not set')}
Target roles: {profile.get('target_roles', 'Not set')}
Salary target: {profile.get('salary_target', 'Not set')}
Preferences: {profile.get('preferences', 'Not set')}

## CV (canonical source of truth)
{cv}
"""
    if digest:
        ctx += f"\n## Proof Points / Article Digest\n{digest}\n"
    return ctx

def get_next_report_number() -> int:
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    existing = list(reports_dir.glob("*.md"))
    if not existing:
        return 1
    nums = []
    for f in existing:
        try:
            nums.append(int(f.name.split("-")[0]))
        except (ValueError, IndexError):
            pass
    return (max(nums) + 1) if nums else 1

def load_portals() -> dict:
    p = Path("portals.yml")
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    # Try template
    t = Path("templates/portals.example.yml")
    if t.exists():
        return yaml.safe_load(t.read_text(encoding="utf-8")) or {}
    return {}

def load_applications() -> str:
    p = Path("data/applications.md")
    return p.read_text(encoding="utf-8") if p.exists() else "No applications tracked yet."

def save_tracker_entry(entry: dict):
    """Append a new application to data/applications.md"""
    p = Path("data/applications.md")
    p.parent.mkdir(exist_ok=True)

    # Read existing
    if not p.exists():
        p.write_text("# Applications Tracker\n\n| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n|---|------|---------|------|-------|--------|-----|--------|-------|\n", encoding="utf-8")

    content = p.read_text(encoding="utf-8")

    # Check for duplicate company+role
    if entry.get("company", "") in content and entry.get("role", "") in content:
        return False  # Already exists

    # Build row
    num = entry.get("num", "?")
    row = (f"| {num} | {entry.get('date','')} | {entry.get('company','')} | "
           f"{entry.get('role','')} | {entry.get('score','')} | {entry.get('status','Evaluated')} | "
           f"{entry.get('pdf','-')} | {entry.get('report','')} | {entry.get('notes','')} |")

    p.write_text(content.rstrip() + "\n" + row + "\n", encoding="utf-8")
    return True