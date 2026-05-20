# JobHunt AI

An agentic AI system that autonomously finds jobs, scores your resume, and drafts cold emails — built from scratch without LangChain, running locally on an 8GB laptop.

---

## Why I built this

Applying for jobs manually is repetitive. You search the same sites, copy-paste your resume into every form, and write nearly identical emails. I wanted to build something that handles that entire flow as an autonomous agent — not a chatbot that just answers questions, but something that actually takes actions and produces usable output.

I also deliberately avoided LangChain. Most tutorials use it as a black box and you end up not understanding how agents actually work. Building the ReAct loop from scratch forced me to understand every part of the system.

---

## What it does

You type something like `"Find ML Engineer jobs in Pune and score my resume"` and the agent:

1. Scrapes job listings from Naukri, Internshala, and LinkedIn (via Google)
2. Reads your resume PDF and scores each job match (0–100%)
3. Drafts a personalized cold email for the best matching role
4. Generates a PDF report you can keep

It runs a ReAct loop (Reasoning + Acting) — it decides which tool to call next based on what it knows so far, not just a fixed script.

---

## Architecture

```
User message
     |
     v
Intent Detection  <-- fast keyword fallback when LLM output isn't JSON
     |
     v
ReAct Loop (orchestrator.py)
     |
     +---> web_scraper     (naukri.py, internshala.py, linkedin_google.py)
     |
     +---> resume_analyzer (reads resume.pdf via PyMuPDF, scores with LLM)
     |
     +---> email_drafter   (LLM writes email from resume + job context)
     |
     +---> report_builder  (ReportLab generates PDF)
     |
     v
SQLite (memory.py) -- persists jobs + conversation history across sessions
```

The LLM (gemma3:4b via Ollama) runs locally. No data leaves your machine.

---

## Stack

- **LLM**: Ollama + gemma3:4b (local) or Groq free tier (online, toggle in config)
- **Scraping**: requests + BeautifulSoup4
- **Resume parsing**: PyMuPDF
- **PDF generation**: ReportLab
- **Database**: SQLite
- **UI**: Streamlit

---

## Setup

Requires Python 3.10+ and [Ollama](https://ollama.com/download).

```bash
git clone https://github.com/yourusername/jobhunt-ai.git
cd jobhunt-ai

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
ollama pull gemma3:4b
```

Add your resume as `resume.pdf` in the project root.

**Run:**

```bash
# Terminal 1 — keep open
ollama serve

# Terminal 2
streamlit run ui/app.py
```

Open `http://localhost:8501`.

**Optional — Groq online mode** (smarter model, free API):

Get a key at [console.groq.com](https://console.groq.com), add to `.env`:
```
GROQ_API_KEY=gsk_xxxxxxxxxxxx
```
Then set `USE_LOCAL_LLM = False` in `config.py`.

---

## Project structure

```
jobhunt-ai/
├── agent/
│   ├── orchestrator.py   # ReAct loop + intent detection
│   ├── tools.py          # all 4 tools
│   ├── llm.py            # Ollama/Groq adapter
│   └── memory.py         # SQLite
├── scraper/
│   ├── naukri.py
│   ├── internshala.py
│   └── linkedin_google.py
├── ui/
│   └── app.py            # Streamlit UI
├── config.py
├── requirements.txt
└── resume.pdf            # add your own
```

---

## A few things worth noting

**Why no LangChain:** I wanted to understand how agents work internally — the tool dispatch loop, how memory gets injected into each LLM call, how to handle tool errors without crashing. LangChain hides all of that. This project doesn't.

**LinkedIn scraping:** LinkedIn blocks direct scraping (requires login + CAPTCHA). The workaround is searching Google with `site:linkedin.com/jobs <role> <location>` — Google's index of LinkedIn is public, no login needed.

**Small model reliability:** gemma3:4b sometimes responds conversationally instead of outputting the JSON the agent expects. I added an intent detection layer that reads the user's message directly and calls the right tool — the LLM is used as a secondary decision maker, not the only one. This keeps the system functional regardless of model output quality.

**RAM usage:** ~4GB total (3.3GB for the model, rest for Python + Streamlit). Tested on 8GB RAM, no GPU.

---

## Known limitations

- Naukri has updated their HTML — the scraper falls back to demo data for that source
- gemma3:4b is not very accurate for resume scoring (responses vary run to run)
- LinkedIn results depend on Google not blocking the search request
- The agent sometimes loops more steps than needed for simple queries

---

## License

MIT