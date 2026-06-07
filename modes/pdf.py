"""
Mode: pdf — Generate ATS-optimized CV PDF tailored to a job description.
Uses weasyprint or pdfkit for HTML→PDF conversion.
"""

from pathlib import Path
from datetime import date
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from gemini_client import ask_structured
from shared import build_context, load_cv

console = Console()

PDF_SYSTEM = """You are an expert CV writer specializing in ATS optimization. 
Your task is to tailor a CV for a specific job description.

Rules:
- Keep all facts from the original CV (never invent metrics)
- Reorder and emphasize experiences that match the JD
- Inject relevant keywords from the JD naturally
- Keep summary punchy and role-specific (3-4 sentences)
- Output clean HTML using the provided template structure
- Don't add fake experiences or metrics"""

CV_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Arial', sans-serif; font-size: 11pt; color: #1a1a1a; padding: 2cm; }}
  h1 {{ font-size: 22pt; font-weight: bold; color: #1a1a1a; }}
  h2 {{ font-size: 11pt; font-weight: bold; color: #2563eb; border-bottom: 1px solid #2563eb; 
       padding-bottom: 2px; margin: 14px 0 6px; text-transform: uppercase; letter-spacing: 1px; }}
  h3 {{ font-size: 11pt; font-weight: bold; margin-bottom: 2px; }}
  .contact {{ color: #555; font-size: 10pt; margin-bottom: 12px; }}
  .role-date {{ display: flex; justify-content: space-between; }}
  .company {{ color: #555; font-style: italic; }}
  ul {{ margin-left: 18px; margin-top: 4px; }}
  li {{ margin-bottom: 2px; line-height: 1.4; }}
  .skills {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .skill-tag {{ background: #f0f4ff; color: #2563eb; padding: 2px 8px; border-radius: 3px; font-size: 10pt; }}
  p {{ line-height: 1.5; margin-bottom: 6px; }}
</style>
</head>
<body>
{content}
</body>
</html>"""

def run():
    console.print(Panel.fit("[bold cyan]CV PDF Generator[/bold cyan]", border_style="cyan"))

    cv_md = load_cv()
    if "[cv.md not found]" in cv_md:
        console.print("[red]cv.md not found. Run setup first.[/red]")
        return

    # Ask for job description (optional — for tailoring)
    console.print("\n[dim]Paste job description to tailor CV (or press Enter to generate generic CV):[/dim]\n")
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

    jd = "\n".join(lines).strip()
    context = build_context()

    console.print("\n[bold cyan]🤖 Generating tailored CV...[/bold cyan]")

    if jd:
        prompt = f"""
Tailor this CV for the following job description. Rewrite the summary to be role-specific.
Reorder bullet points to lead with most relevant experiences.
Inject keywords naturally. Output as HTML using these structure elements:
- <h1> for name
- <div class="contact"> for contact info
- <h2> for section headers (EXPERIENCE, EDUCATION, SKILLS, etc.)
- <h3> for job titles, <div class="role-date"> for title+date layout
- <ul><li> for bullet points
- <div class="skills"><span class="skill-tag"> for skills

## Original CV (Markdown)
{cv_md}

## Job Description to target:
{jd}

Output only the HTML body content (no <html>/<body> tags, just the inner content).
"""
    else:
        prompt = f"""
Convert this CV to clean HTML. Use these structure elements:
- <h1> for name
- <div class="contact"> for contact info
- <h2> for section headers (EXPERIENCE, EDUCATION, SKILLS, etc.)
- <h3> for job titles
- <ul><li> for bullet points
- <div class="skills"><span class="skill-tag"> for skills

## CV (Markdown)
{cv_md}

Output only the HTML body content.
"""

    html_content = ask_structured(prompt, system=PDF_SYSTEM)

    # Build full HTML
    full_html = CV_TEMPLATE.format(content=html_content)

    # Save HTML
    today = date.today().strftime("%Y-%m-%d")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    html_path = output_dir / f"cv-{today}.html"
    html_path.write_text(full_html)
    console.print(f"[green]✅ HTML CV saved: {html_path}[/green]")

    # Try to generate PDF
    pdf_path = output_dir / f"cv-{today}.pdf"
    pdf_generated = _generate_pdf(html_path, pdf_path)

    if pdf_generated:
        console.print(f"[green]✅ PDF saved: {pdf_path}[/green]")
    else:
        console.print(f"\n[yellow]PDF generation requires additional tools. Open the HTML file in your browser and print to PDF:[/yellow]")
        console.print(f"[dim]  {html_path.absolute()}[/dim]")

    console.print(f"\n[dim]Tip: Open {html_path} in Chrome, then File → Print → Save as PDF for best results.[/dim]")

def _generate_pdf(html_path: Path, pdf_path: Path) -> bool:
    """Try multiple PDF generation methods."""

    # Method 1: weasyprint
    try:
        import weasyprint
        weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return True
    except ImportError:
        pass
    except Exception as e:
        console.print(f"[dim]weasyprint failed: {e}[/dim]")

    # Method 2: pdfkit (requires wkhtmltopdf)
    try:
        import pdfkit
        pdfkit.from_file(str(html_path), str(pdf_path))
        return True
    except ImportError:
        pass
    except Exception as e:
        console.print(f"[dim]pdfkit failed: {e}[/dim]")

    # Method 3: subprocess with chromium/google-chrome
    try:
        import subprocess
        for browser in ["google-chrome", "chromium", "chromium-browser"]:
            result = subprocess.run([
                browser, "--headless", "--disable-gpu",
                f"--print-to-pdf={pdf_path}",
                str(html_path.absolute())
            ], capture_output=True, timeout=30)
            if result.returncode == 0:
                return True
    except Exception:
        pass

    return False
