"""
Mode: autoapply - Selenium-based auto form-filling agent.

Workflow:
  1. Fetch job page  (TinyFish / urllib)
  2. Gemini detects all form fields on the page
  3. Gemini drafts answers for every field from your CV + profile
  4. YOU review and approve each answer
  5. Selenium fills the form — but NEVER clicks Submit
  6. You review the filled form in the browser and submit manually

Human is always in the loop. This tool fills — you decide.
"""

import time
import json
import re
from pathlib import Path
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box

from gemini_client import ask, ask_json
from shared import build_context, save_tracker_entry, get_next_report_number
from fetcher import fetch_job_page

console = Console()

FIELD_DETECT_SYSTEM = """You are an expert at reading job application forms including Google Forms.
Given the text content of a job application page or Google Form, identify EVERY question and input field.
For Google Forms: every question line followed by a blank or answer area is a field.
Look for patterns like:
  - Lines ending with * (required fields)
  - Questions followed by "Short answer", "Paragraph", "Multiple choice", "Checkboxes"
  - Any text that looks like a question asking for user input
Return a JSON array of objects, each with:
  - "field_id": a short snake_case identifier (e.g. "full_name", "cover_letter", "years_exp")
  - "label": the exact question/field label
  - "type": "text" | "textarea" | "select" | "checkbox" | "file"
  - "required": true if marked with * or "required", else false
  - "options": list of options if multiple choice / select, else null
  - "word_limit": integer if specified, else null
Be thorough — include ALL questions, even ones that seem optional.
For a Google Form with 15 questions, return 15 objects.
Return ONLY a valid JSON array, no markdown, no explanation."""

ANSWER_SYSTEM = """You are an expert career coach filling out a job application.
Use ONLY information from the candidate's CV and profile — never invent or exaggerate.
Write answers that are specific, honest, and compelling.
For behavioral questions, use STAR format.
For word-limited fields, stay 10-20% under the limit to leave breathing room.
If a field is truly unanswerable from the CV (e.g. salary expectations), flag it clearly.
Return a JSON object where keys are field_ids and values are the drafted answers."""


def _fetch_google_form_selenium(url: str) -> str:
    """
    Fetch a fully JS-rendered Google Form using Selenium.
    Returns all question text extracted from the DOM.
    Much more reliable than TinyFish for Google Forms.
    """
    # Initialize storage on first call
    if not hasattr(_fetch_google_form_selenium, "_last_fields"):
        _fetch_google_form_selenium._last_fields = []
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")          # Run invisible
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")

        console.print("[dim]  Opening headless Chrome to render Google Form...[/dim]")
        driver = webdriver.Chrome(options=options)

        try:
            driver.get(url)
            # Wait for form questions to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='listitem']"))
            )
            time.sleep(2)  # Extra wait for all questions to render

            # Extract all question text from the form
            questions = []

            # Google Forms question containers
            question_containers = driver.find_elements(
                By.CSS_SELECTOR, "div[role='listitem']"
            )

            console.print(f"[dim]  Found {len(question_containers)} question containers[/dim]")

            for container in question_containers:
                try:
                    # Get question title
                    title_els = container.find_elements(
                        By.CSS_SELECTOR,
                        "span[class*='M7eMe'], div[class*='HoXoMd'], div[class*='z12JJ']"
                    )
                    title = ""
                    for el in title_els:
                        t = el.text.strip()
                        if t and len(t) > 2:
                            title = t
                            break

                    if not title:
                        # Fallback: get all text from container
                        title = container.text.strip().split("\n")[0]

                    if not title or len(title) < 3:
                        continue

                    # Detect field type
                    is_required = "*" in container.text or container.find_elements(
                        By.CSS_SELECTOR, "span[aria-label*='required']"
                    )

                    # Check for radio/checkbox options
                    options_els = container.find_elements(
                        By.CSS_SELECTOR, "div[role='radio'], div[role='checkbox']"
                    )
                    options_text = [o.text.strip() for o in options_els if o.text.strip()]

                    # Check for textarea vs text
                    textareas = container.find_elements(By.CSS_SELECTOR, "textarea")
                    inputs    = container.find_elements(By.CSS_SELECTOR, "input[type='text']")

                    if textareas:
                        ftype = "textarea"
                    elif options_text:
                        ftype = "select"
                    else:
                        ftype = "text"

                    questions.append({
                        "title":    title,
                        "type":     ftype,
                        "required": bool(is_required),
                        "options":  options_text or None,
                    })

                except Exception:
                    continue

            # Build structured fields list and store on function
            structured_fields = []
            for q in questions:
                fid = re.sub(r'[^a-z0-9]+', '_', q["title"].lower())[:40].strip('_')
                structured_fields.append({
                    "field_id":   fid,
                    "label":      q["title"],
                    "type":       q["type"],
                    "required":   q["required"],
                    "options":    q["options"],
                    "word_limit": None,
                })

            # Store on function for retrieval in run()
            _fetch_google_form_selenium._last_fields = structured_fields

            # Also return text summary for Gemini detection fallback
            summary_lines = ["Google Form Questions:"]
            for i, q in enumerate(questions, 1):
                req = " *" if q["required"] else ""
                summary_lines.append(f"{i}. {q['title']}{req} [{q['type']}]")
                if q["options"]:
                    summary_lines.append(f"   Options: {', '.join(q['options'][:6])}")

            console.print(f"  [green]Extracted {len(structured_fields)} fields from Google Form[/green]")
            return "\n".join(summary_lines)

        finally:
            driver.quit()

    except ImportError:
        console.print("[yellow]  Selenium not installed for form rendering.[/yellow]")
        return ""
    except Exception as e:
        console.print(f"[yellow]  Headless Chrome fetch failed: {e}[/yellow]")
        return ""



def run():
    console.print(Panel.fit(
        "[bold cyan]Auto-Apply Agent[/bold cyan]\n"
        "[dim]Fills forms. You always submit.[/dim]",
        border_style="cyan"
    ))

    console.print("\n[bold yellow]How this works:[/bold yellow]")
    console.print("  1. Paste the application URL")
    console.print("  2. Gemini detects all form fields")
    console.print("  3. Gemini drafts answers from your CV")
    console.print("  4. You review and edit each answer")
    console.print("  5. Selenium fills the form in your browser")
    console.print("  6. [bold]YOU[/bold] review and hit Submit yourself\n")

    if not Confirm.ask("Ready to proceed?", default=True):
        return

    # ── Get job URL ───────────────────────────────────────────────
    url = Prompt.ask("\nPaste the application URL").strip()
    if not url.startswith("http"):
        console.print("[red]Invalid URL. Must start with http.[/red]")
        return

    company = Prompt.ask("Company name")
    role    = Prompt.ask("Role title")

    # ── Fetch page ────────────────────────────────────────────────
    console.print(f"\n[dim]Fetching application page...[/dim]")

    # Google Forms: use Selenium headless to get JS-rendered content
    if "docs.google.com/forms" in url:
        console.print("[dim]Google Form detected — using headless Chrome for full render...[/dim]")
        page_content = _fetch_google_form_selenium(url)
        if not page_content or len(page_content.strip()) < 50:
            console.print("[yellow]Headless fetch failed. Falling back to TinyFish...[/yellow]")
            page_content = fetch_job_page(url)
    else:
        page_content = fetch_job_page(url)

    if not page_content or len(page_content.strip()) < 100:
        console.print("[red]Could not fetch the application page.[/red]")
        console.print("[dim]Some ATS portals (Workday, Greenhouse) require login.")
        console.print("Try pasting the form fields manually instead.[/dim]")
        page_content = _manual_field_entry()
        if not page_content:
            return

    # ── Detect form fields ────────────────────────────────────────
    console.print("[dim]Detecting form fields...[/dim]")
    # Check if this is a job listing page (not an application form)
    listing_signals = ["apply now", "job description", "about the company",
                       "responsibilities", "requirements", "internshala",
                       "naukri.com", "linkedin.com/jobs/view"]
    is_listing = any(s in page_content.lower() for s in listing_signals)

    if is_listing:
        console.print("[yellow]This looks like a job listing page, not an application form.[/yellow]")
        console.print("[dim]Try:[/dim]")
        console.print("[dim]  1. Open the job page in Chrome[/dim]")
        console.print("[dim]  2. Click Apply / Easy Apply[/dim]")
        console.print("[dim]  3. Copy the URL of the form that opens[/dim]")
        console.print("[dim]  4. OR paste the form field labels manually below[/dim]\n")
        use_manual = Confirm.ask("Switch to manual field entry?", default=True)
        if not use_manual:
            return
        fields = _build_fields_manually()
        if not fields:
            return

    # Google Forms: use pre-parsed fields from selenium directly
    elif "docs.google.com/forms" in url and hasattr(_fetch_google_form_selenium, "_last_fields"):
        fields = _fetch_google_form_selenium._last_fields
        console.print(f"[green]Using {len(fields)} fields extracted directly from Google Form.[/green]")

    else:
        try:
            # Clean the page content before sending to Gemini
            clean_content = page_content[:5000].replace("\x00","").strip()
            fields = ask_json(
                f"Detect all form fields from this application page content:\n\n{clean_content}",
                system=FIELD_DETECT_SYSTEM
            )
            if not isinstance(fields, list) or not fields:
                raise ValueError("No fields detected")
        except Exception as e:
            console.print(f"[yellow]Auto-detection failed ({e}). Switching to manual entry.[/yellow]")
            fields = _build_fields_manually()
            if not fields:
                return

    # Show detected fields
    console.print(f"\n[green]Found {len(fields)} form fields:[/green]")
    t = Table(box=box.SIMPLE, show_header=True)
    t.add_column("#",        width=4)
    t.add_column("Field",    width=28)
    t.add_column("Type",     width=10)
    t.add_column("Required", width=10)
    for i, f in enumerate(fields, 1):
        req = "[red]yes[/red]" if f.get("required") else "no"
        t.add_row(str(i), f.get("label","?"), f.get("type","text"), req)
    console.print(t)

    if not Confirm.ask("Proceed with these fields?", default=True):
        console.print("[dim]Edit the detected fields or re-run.[/dim]")
        return

    # ── Draft answers in batches ──────────────────────────────────
    context = build_context()
    console.print("\n[bold cyan]Drafting answers from your CV...[/bold cyan]")

    answers = {}
    BATCH_SIZE = 8  # Draft 8 fields at a time to avoid token limits

    # Split fields into batches
    text_fields = [f for f in fields if f.get("type") != "file"]
    batches = [text_fields[i:i+BATCH_SIZE] for i in range(0, len(text_fields), BATCH_SIZE)]

    for batch_num, batch in enumerate(batches, 1):
        console.print(f"[dim]  Drafting batch {batch_num}/{len(batches)} ({len(batch)} fields)...[/dim]")

        fields_summary = json.dumps([
            {"field_id": f.get("field_id"), "label": f.get("label"),
             "type": f.get("type"), "word_limit": f.get("word_limit"),
             "options": f.get("options")}
            for f in batch
        ], indent=2)

        try:
            batch_answers = ask_json(
                f"## Candidate Profile\n{context}\n\n"
                f"## Job\nCompany: {company}\nRole: {role}\nURL: {url}\n\n"
                f"## Form Fields (draft answers for these {len(batch)} fields ONLY)\n{fields_summary}\n\n"
                f"Return a JSON object with field_id as key and answer as value. "
                f"Keep answers concise. For checkbox/multi-select fields return a single best option.",
                system=ANSWER_SYSTEM
            )
            if isinstance(batch_answers, dict):
                answers.update(batch_answers)
            console.print(f"[dim]  Batch {batch_num} done — {len(batch_answers)} answers[/dim]")
        except Exception as e:
            console.print(f"[yellow]  Batch {batch_num} failed ({e}), using placeholders.[/yellow]")
            for f in batch:
                answers[f.get("field_id","")] = f"[Please fill: {f.get('label','')}]"

    if not answers:
        console.print("[red]Failed to draft any answers.[/red]")
        return
    console.print(f"[green]Drafted {len(answers)} answers.[/green]")

    # ── Human review loop ─────────────────────────────────────────
    console.print("\n[bold yellow]Review each answer. Press Enter to accept, or type a replacement.[/bold yellow]\n")

    approved_answers = {}
    for field in fields:
        fid   = field.get("field_id", "")
        label = field.get("label", fid)
        ftype = field.get("type", "text")
        draft = answers.get(fid, "")

        if ftype == "file":
            console.print(f"[dim]Skipping file field: {label}[/dim]")
            continue

        console.print(f"\n[bold cyan]{label}[/bold cyan]")
        if field.get("word_limit"):
            wc = len(draft.split())
            console.print(f"[dim]Word limit: {field['word_limit']} | Draft: {wc} words[/dim]")
        if field.get("options"):
            console.print(f"[dim]Options: {', '.join(str(o) for o in field['options'][:8])}[/dim]")

        console.print(f"[dim]Draft:[/dim] {draft[:300]}{'...' if len(draft)>300 else ''}")

        edited = Prompt.ask("  Accept / edit", default=draft)
        approved_answers[fid] = edited

    # ── Save answers draft ────────────────────────────────────────
    today = date.today().strftime("%Y-%m-%d")
    slug  = re.sub(r'[^a-z0-9]+', '-', company.lower())[:20].strip('-')
    draft_path = Path(f"output/apply-{slug}-{today}.md")
    draft_path.parent.mkdir(exist_ok=True)

    lines = [f"# Application: {company} - {role}\n",
             f"**Date:** {today}\n**URL:** {url}\n\n---\n"]
    for field in fields:
        fid   = field.get("field_id","")
        label = field.get("label", fid)
        ans   = approved_answers.get(fid, "")
        if ans:
            lines.append(f"## {label}\n{ans}\n")
    draft_path.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"\n[green]Answers saved to: {draft_path}[/green]")

    # ── Selenium fill ─────────────────────────────────────────────
    console.print("\n[bold yellow]Ready to fill the form in your browser.[/bold yellow]")
    console.print("[dim]Selenium will open the URL and fill each field.[/dim]")
    console.print("[bold red]It will NOT click Submit. You do that.[/bold red]\n")

    if Confirm.ask("Open browser and fill form now?", default=True):
        _selenium_fill(url, fields, approved_answers)

    # ── Update tracker ────────────────────────────────────────────
    if Confirm.ask("\nMark as Applied in tracker?", default=False):
        num = get_next_report_number()
        save_tracker_entry({
            "num":     num,
            "date":    today,
            "company": company,
            "role":    role,
            "score":   "-",
            "status":  "Applied",
            "pdf":     "-",
            "report":  f"[draft]({draft_path})",
            "notes":   "Auto-filled via autoapply"
        })
        console.print("[green]Added to tracker as Applied.[/green]")


# ── Selenium filler ───────────────────────────────────────────────

def _selenium_fill(url: str, fields: list, answers: dict):
    """Open browser, fill form fields. Never submits."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait, Select
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
    except ImportError:
        console.print("[yellow]selenium not installed. Run: pip install selenium[/yellow]")
        console.print("[dim]Also install ChromeDriver: https://chromedriver.chromium.org/[/dim]")
        console.print(f"\n[dim]Your answers are saved. Fill manually using: {url}[/dim]")
        return

    console.print("[dim]Opening Chrome...[/dim]")
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # Keep browser open after script ends so user can review + submit
    options.add_experimental_option("detach", True)

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        wait = WebDriverWait(driver, 15)

        console.print(f"[green]Browser opened: {url}[/green]")
        console.print("[dim]Waiting 3s for page to load...[/dim]")
        time.sleep(3)

        # Use Google Forms special filler if applicable
        if "docs.google.com/forms" in url:
            console.print("[dim]  Using Google Forms fill strategy...[/dim]")
            filled, skipped = _fill_google_form(driver, fields, answers)
        else:
            filled  = 0
            skipped = 0
            for field in fields:
                fid    = field.get("field_id", "")
                label  = field.get("label", fid)
                ftype  = field.get("type", "text")
                answer = answers.get(fid, "")

                if not answer or ftype == "file":
                    skipped += 1
                    continue

                element = _find_element(driver, label, ftype)
                if not element:
                    console.print(f"[yellow]  Could not find field: {label}[/yellow]")
                    skipped += 1
                    continue

                try:
                    if ftype in ("text", "textarea", "email", "tel", "number"):
                        element.clear()
                        element.send_keys(answer)
                        filled += 1
                        console.print(f"[green]  Filled: {label}[/green]")
                    elif ftype == "select":
                        sel = Select(element)
                        try:
                            sel.select_by_visible_text(answer)
                            filled += 1
                            console.print(f"[green]  Selected: {label} = {answer}[/green]")
                        except Exception:
                            console.print(f"[yellow]  Could not select for: {label}[/yellow]")
                            skipped += 1
                    time.sleep(0.3)
                except Exception as e:
                    console.print(f"[yellow]  Error filling {label}: {e}[/yellow]")
                    skipped += 1

        console.print(f"\n[bold green]Form filling complete.[/bold green]")
        console.print(f"  Filled:  {filled} fields")
        console.print(f"  Skipped: {skipped} fields")
        console.print("\n[bold red]The browser is open. Review everything, then Submit yourself.[/bold red]")
        console.print("[dim]Close the browser window when done.[/dim]")

    except Exception as e:
        console.print(f"[red]Browser error: {e}[/red]")
        console.print("[dim]Fill manually using the saved answers file.[/dim]")





def _find_element(driver, label: str, ftype: str):
    """Try multiple strategies to find a form element by its label.
    Includes special handling for Google Forms custom elements."""
    from selenium.webdriver.common.by import By

    # Truncate label for matching (Google Forms labels can be very long)
    short_label = label[:60].strip()
    # First word(s) for fuzzy matching
    first_words  = " ".join(label.split()[:4])

    strategies = [
    # Google Forms: aria-label exact
    (By.XPATH, f"//*[@aria-label='{short_label}']"),
    # Google Forms: aria-label contains first words
    (By.XPATH, f"//*[contains(@aria-label, '{first_words}')]"),
    # Google Forms: data-params contains label text
    (By.XPATH, f"//*[contains(@data-params, '{first_words}')]//input"),
    (By.XPATH, f"//*[contains(@data-params, '{first_words}')]//textarea"),
    # Standard: associated label text
    (By.XPATH, f"//label[contains(.,'{first_words}')]/following::input[1]"),
    (By.XPATH, f"//label[contains(.,'{first_words}')]/following::textarea[1]"),
    (By.XPATH, f"//label[contains(.,'{first_words}')]/following::select[1]"),
    # Google Forms: find question container then input inside it
    (By.XPATH, f"//*[contains(.,'{first_words}')]/following::input[@type!='hidden'][1]"),
    (By.XPATH, f"//*[contains(.,'{first_words}')]/following::textarea[1]"),
    # By placeholder
    (By.XPATH, f"//*[@placeholder='{short_label}']"),
    # By name/id
    (By.XPATH, f"//*[contains(@name,'{label.lower().replace(' ','_')[:30]}')]"),
    (By.XPATH, f"//*[contains(@id,'{label.lower().replace(' ','-')[:30]}')]"),
]

    for by, selector in strategies:
        try:
            elements = driver.find_elements(by, selector)
            visible  = [e for e in elements if e.is_displayed()]
            if visible:
                return visible[0]
        except Exception:
            continue

    return None


def _fill_google_form(driver, fields: list, answers: dict) -> tuple:
    """
    Special filler for Google Forms.
    Google Forms renders questions as custom divs — we find them by
    scrolling through all visible text inputs and textareas in order.
    Returns (filled, skipped) counts.
    """
    from selenium.webdriver.common.by import By
    import time

    filled, skipped = 0, 0

    # Get all visible input/textarea elements on the page
    inputs    = driver.find_elements(By.CSS_SELECTOR,
                    "input[type='text']:not([type='hidden']), "
                    "input[type='email'], input[type='tel'], "
                    "input[type='url'], input[type='number'], textarea")
    visible   = [e for e in inputs if e.is_displayed()]

    # Get all radio/checkbox groups
    radios    = driver.find_elements(By.CSS_SELECTOR, "div[role='radio']")
    checks    = driver.find_elements(By.CSS_SELECTOR, "div[role='checkbox']")

    console.print(f"  [dim]Found {len(visible)} text inputs on page[/dim]")

    # Match fields to inputs by order (Google Forms preserves question order)
    text_fields = [f for f in fields
                   if f.get("type") not in ("file", "checkbox", "select")]

    for i, field in enumerate(text_fields):
        fid    = field.get("field_id","")
        label  = field.get("label","")
        answer = answers.get(fid,"")

        if not answer or answer.startswith("[UNANSWERABLE"):
            console.print(f"  [yellow]Skip (no answer): {label[:40]}[/yellow]")
            skipped += 1
            continue

        if i < len(visible):
            try:
                elem = visible[i]
                driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                time.sleep(0.3)
                elem.click()
                elem.clear()
                elem.send_keys(answer)
                filled += 1
                console.print(f"  [green]Filled[{i+1}]: {label[:40]}[/green]")
                time.sleep(0.2)
            except Exception as e:
                console.print(f"  [yellow]Error on field {i+1}: {e}[/yellow]")
                skipped += 1
        else:
            console.print(f"  [yellow]No input found for: {label[:40]}[/yellow]")
            skipped += 1

    # Handle radio buttons (select options)
    select_fields = [f for f in fields if f.get("type") == "select" and f.get("options")]
    for field in select_fields:
        fid    = field.get("field_id","")
        answer = answers.get(fid,"")
        if not answer:
            continue
        # Find radio with matching text
        for radio in radios:
            try:
                if answer.lower() in radio.text.lower():
                    radio.click()
                    filled += 1
                    console.print(f"  [green]Selected: {radio.text[:40]}[/green]")
                    break
            except Exception:
                continue

    return filled, skipped


# ── Manual fallback helpers ───────────────────────────────────────

def _manual_field_entry() -> str:
    """Let user paste form field names manually if auto-fetch fails."""
    console.print("\n[dim]Paste the form field labels (one per line).")
    console.print("[dim]Press Enter twice when done.[/dim]\n")
    lines = []
    empty = 0
    while empty < 2:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            empty += 1
        else:
            empty = 0
            lines.append(line)
    return "\n".join(lines).strip()


def _build_fields_manually() -> list:
    """Build field list from manually entered labels."""
    raw = _manual_field_entry()
    if not raw:
        return []
    fields = []
    for i, label in enumerate(raw.splitlines()):
        label = label.strip()
        if label:
            fields.append({
                "field_id": re.sub(r'[^a-z0-9]+', '_', label.lower())[:30],
                "label":    label,
                "type":     "textarea" if len(label) > 30 else "text",
                "required": True,
                "options":  None,
                "word_limit": None,
            })
    return fields