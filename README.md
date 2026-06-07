# Career-Ops — Gemini Edition

> AI-powered job search pipeline, rebuilt with Google Gemini (free tier).  
> Inspired by [santifer/career-ops](https://github.com/santifer/career-ops) — reimplemented as a local Python CLI.

**No Claude Code needed. No paid subscriptions. Just your free Gemini API key.**

---

## What It Does

- 🎯 **Evaluates job offers** — A-F scoring across 6 dimensions with detailed report
- 📄 **Generates tailored CVs** — ATS-optimized PDF per job description
- 🔍 **Scans job portals** — Auto-scans company career pages for new openings
- 📊 **Tracks your pipeline** — Full application lifecycle from Evaluated → Offer
- 🔬 **Deep company research** — Funding, culture, tech stack, red flags
- ✍️  **Drafts outreach** — LinkedIn messages tailored to context
- 📝 **Fills application forms** — Answers to common application questions
- 🎓 **Evaluates courses/certs** — Is it worth your time?
- 🛠️  **Evaluates projects** — Career impact of your portfolio work
- ⚖️  **Compares offers** — Side-by-side comparison with recommendation
- 📦 **Batch processing** — Evaluate 10+ jobs at once
- 📈 **Analytics** — Pipeline stats, funnel, score distribution

---

## Quick Start

### 1. Get Your Free Gemini API Key
Go to [Google AI Studio](https://aistudio.google.com/app/apikey) → Create API key → Copy it.

### 2. Install
```bash
git clone <this-repo>
cd career-ops-gemini

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure API Key
```bash
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

### 4. Run Setup Wizard
```bash
python main.py setup
```
The wizard will guide you through:
- Creating your CV (paste, type, or from scratch)
- Setting your profile (target roles, salary, preferences)
- Configuring job portals to scan
- Setting up the tracker

### 5. Start Using
```bash
python main.py evaluate    # Evaluate a job (paste URL or JD)
python main.py scan        # Scan portals for new jobs
python main.py tracker     # View your pipeline
python main.py stats       # Analytics dashboard
python main.py             # Interactive mode
```

---

## All Commands

| Command | What it does |
|---------|-------------|
| `evaluate` | Evaluate a job offer — paste URL or JD, get full A-F report |
| `scan` | Scan configured company career pages for new openings |
| `pdf` | Generate ATS-optimized CV PDF (generic or tailored to JD) |
| `batch` | Batch evaluate all URLs in data/pipeline.md |
| `tracker` | View and manage your application pipeline |
| `deep` | Deep company research (funding, culture, tech, red flags) |
| `contact` | Draft LinkedIn outreach message |
| `apply` | Draft answers to application form questions |
| `pipeline` | Process URLs in pipeline.md one by one interactively |
| `compare` | Compare 2+ job offers side by side |
| `training` | Evaluate whether a course/cert is worth pursuing |
| `project` | Evaluate a portfolio project's career impact |
| `setup` | Re-run onboarding wizard |
| `stats` | Pipeline analytics and funnel stats |

---

## Scoring System

Each offer is scored across 6 weighted dimensions:

| Dimension | Weight | What it measures |
|-----------|--------|-----------------|
| Role Match | 25% | How well JD matches your skills & targets |
| Compensation | 20% | Market rate competitiveness |
| Company Quality | 20% | Team, funding, PMF, trajectory |
| Growth | 15% | Career growth & learning potential |
| Culture Fit | 10% | Values & work style alignment |
| Location/Remote | 10% | Work arrangement match |

**Grades:** A (4.5+) · B (3.5–4.4) · C (2.5–3.4) · D (1.5–2.4) · F (<1.5)

> ⚠️ The system discourages applying to anything below 3.0/5. Quality over quantity.

---

## Project Structure

```
career-ops-gemini/
├── main.py                    # CLI entry point
├── gemini_client.py           # Gemini API wrapper
├── shared.py                  # Shared context loader
├── modes/
│   ├── setup.py               # Onboarding wizard
│   ├── evaluate.py            # Job evaluation (core)
│   ├── tracker.py             # Pipeline viewer
│   ├── scan.py                # Portal scanner
│   ├── pdf.py                 # CV PDF generator
│   ├── batch.py               # Batch evaluator
│   ├── deep.py                # Company research
│   ├── contact.py             # LinkedIn outreach
│   ├── apply.py               # Application answers
│   ├── pipeline.py            # URL processor
│   ├── compare.py             # Offer comparison
│   ├── training.py            # Course evaluator
│   ├── project.py             # Project evaluator
│   └── stats.py               # Analytics
├── config/
│   └── profile.example.yml    # Profile template
├── templates/
│   ├── portals.example.yml    # Portal config template
│   └── states.yml             # Canonical statuses
├── data/                      # Your data (gitignored)
│   ├── applications.md        # Application tracker
│   ├── pipeline.md            # Pending URLs queue
│   └── scan-history.tsv       # Dedup history
├── reports/                   # Evaluation reports (gitignored)
├── output/                    # Generated CVs/PDFs (gitignored)
├── interview-prep/
│   └── story-bank.md          # STAR stories (gitignored)
├── cv.md                      # Your CV — canonical (gitignored)
├── article-digest.md          # Proof points (optional, gitignored)
├── portals.yml                # Your portal config (gitignored)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## PDF Generation

The PDF mode generates an ATS-optimized HTML CV. To get a PDF:

**Option A (easiest):** Open the generated HTML in Chrome → Print → Save as PDF

**Option B (automatic):** Install weasyprint:
```bash
pip install weasyprint
```

**Option C:** Install pdfkit + wkhtmltopdf:
```bash
pip install pdfkit
# Then install wkhtmltopdf from https://wkhtmltopdf.org/downloads.html
```

---

## Ethical Use

This system is a **filter**, not a spray tool.

- ✅ Helps you find roles genuinely worth your time
- ✅ Tailors applications for quality over quantity
- ❌ Never auto-submits anything — you always review first
- ❌ Discourages applying to weak matches (<3.0/5)

---

## Customization

Edit these files to personalize:

- **`cv.md`** — Your CV (markdown format)
- **`config/profile.yml`** — Target roles, salary, preferences
- **`portals.yml`** — Companies and search queries to scan
- **`article-digest.md`** — Proof points and notable achievements

---

## Model

Uses **`gemini-2.0-flash`** — fast, capable, and free tier.  
Free tier: 15 requests/min, 1M tokens/day — more than enough for job searching.

---

## Credits

Inspired by [santifer/career-ops](https://github.com/santifer/career-ops).  
This is a reimplementation using the Google Gemini SDK for local, free usage.

---

## License

MIT
