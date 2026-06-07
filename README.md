# Career-Ops — AI Job Search Automation

End-to-end AI pipeline that handles the entire job search workflow.

## What it does
- Scans multiple job boards (Indeed, LinkedIn, ZipRecruiter, Remotive)
- Scores every job A-F using Gemini 2.5 Pro across 6 dimensions
- Auto-fills application forms using Selenium + headless Chrome
- Drafts personalised recruiter cold emails
- Schedules follow-up reminders automatically
- Tracks entire pipeline from evaluation to offer
- Voice output via Sarvam AI (Indian language support)

## Stack
Python, LangChain, Gemini 2.5 Pro, TinyFish, 
Sarvam AI, Selenium, jobspy, FAISS, Rich

## Setup
1. Clone the repo
2. pip install -r requirements.txt
3. Copy .env.example to .env and add your API keys
4. python main.py setup
5. python main.py

## Modes
| Command | What it does |
|---------|-------------|
| python main.py scan | Scan job boards |
| python main.py evaluate | Score a job A-F |
| python main.py autoapply | Auto-fill application forms |
| python main.py outreach | Draft recruiter emails |
| python main.py tracker | View pipeline |
| python main.py stats | Analytics |
| python main.py followups | Pending follow-ups |

## API Keys needed
- GEMINI_API_KEY — aistudio.google.com
- TINYFISH_API_KEY — agent.tinyfish.ai
- SARVAM_API_KEY — dashboard.sarvam.ai
