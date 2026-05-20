# ─────────────────────────────────────────────
#  JobHunt AI — Central Configuration
# ─────────────────────────────────────────────

import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Mode ──────────────────────────────────────────────────────────────────
USE_LOCAL_LLM = True          # True = Ollama (free, local) | False = Groq (free, online)

# ── Local Model (Ollama) ───────────────────────────────────────────────────────
OLLAMA_BASE_URL = "http://localhost:11434"
LOCAL_MODEL     = "gemma3:4b"

# ── Online Model (Groq — free tier) ───────────────────────────────────────────
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL      = "llama3-70b-8192"

# ── Active model (used everywhere in code) ────────────────────────────────────
ACTIVE_MODEL = LOCAL_MODEL if USE_LOCAL_LLM else GROQ_MODEL

# ── Agent Settings ─────────────────────────────────────────────────────────────
MAX_ITERATIONS  = 10          # max ReAct loop steps before stopping
MAX_TOKENS      = 2048        # max tokens per LLM response
TEMPERATURE     = 0.3         # lower = more focused, higher = more creative

# ── Database ───────────────────────────────────────────────────────────────────
DB_PATH         = "data/jobhunt.db"
CACHE_HOURS     = 24          # how long before re-scraping job listings

# ── Scraper Settings ───────────────────────────────────────────────────────────
SCRAPE_DELAY_MIN = 1.5        # min seconds between requests (anti-block)
SCRAPE_DELAY_MAX = 3.5        # max seconds between requests (anti-block)
MAX_JOBS_PER_SITE = 20        # max jobs to scrape per site per search

# ── Output ─────────────────────────────────────────────────────────────────────
REPORTS_DIR     = "output/reports"
RESUME_PATH     = "resume.pdf"