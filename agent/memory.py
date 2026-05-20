# ─────────────────────────────────────────────
#  agent/memory.py — SQLite Database (Agent Memory)
# ─────────────────────────────────────────────
#
#  Why SQLite?
#  The LLM has zero memory between calls — it forgets everything.
#  SQLite is what gives the agent "memory" across sessions.
#  This is how ALL production AI systems work.
#
#  Tables:
#   jobs     — scraped job listings with match scores
#   messages — conversation history per session
#   sessions — named sessions (e.g. "ML jobs Pune 2025-04-07")
# ─────────────────────────────────────────────

import sqlite3
import os
from datetime import datetime


# ── Path to database file ──────────────────────────────────────────────────────
DB_PATH = "data/jobhunt.db"


def get_connection():
    """Return a SQLite connection. Creates the file if it doesn't exist."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # lets us access columns by name like a dict
    return conn


def init_db():
    """
    Create all tables if they don't exist yet.
    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    Called once at startup by setup.py and by the orchestrator.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # ── Jobs table ─────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            company     TEXT    NOT NULL,
            location    TEXT,
            skills      TEXT,
            salary      TEXT,
            link        TEXT    UNIQUE,
            source      TEXT,
            role_query  TEXT,
            match_score REAL    DEFAULT NULL,
            scraped_at  TEXT    NOT NULL
        )
    """)

    # ── Messages table (conversation history) ──────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            role        TEXT    NOT NULL,   -- 'user' or 'assistant'
            content     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL
        )
    """)

    # ── Sessions table ──────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT    PRIMARY KEY,
            name        TEXT,
            created_at  TEXT    NOT NULL,
            last_active TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print(f"  Database ready: {DB_PATH}")


# ── Job helpers ────────────────────────────────────────────────────────────────

def save_jobs(jobs: list, role_query: str = "", source: str = ""):
    """Insert jobs into the database. Skips duplicates (same link)."""
    conn = get_connection()
    saved = 0
    for job in jobs:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO jobs
                    (title, company, location, skills, salary, link, source, role_query, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("skills", ""),
                job.get("salary", ""),
                job.get("link", ""),
                source,
                role_query,
                datetime.now().isoformat()
            ))
            saved += 1
        except Exception as e:
            print(f"  [DB] Skipped duplicate: {job.get('title')} — {e}")
    conn.commit()
    conn.close()
    return saved


def get_cached_jobs(role_query: str, max_age_hours: int = 24):
    """Return cached jobs for this role if scraped within max_age_hours."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM jobs
        WHERE role_query = ? AND scraped_at > ?
        ORDER BY match_score DESC NULLS LAST
    """, (role_query, cutoff)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def update_match_score(job_id: int, score: float):
    """Update the match score for a job after resume analysis."""
    conn = get_connection()
    conn.execute("UPDATE jobs SET match_score = ? WHERE id = ?", (score, job_id))
    conn.commit()
    conn.close()


def get_top_jobs(limit: int = 10):
    """Return top jobs sorted by match score."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM jobs
        WHERE match_score IS NOT NULL
        ORDER BY match_score DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── Message/session helpers ────────────────────────────────────────────────────

def save_message(session_id: str, role: str, content: str):
    """Save a single message to conversation history."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO messages (session_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (session_id, role, content, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_messages(session_id: str):
    """Return all messages for a session as a list of dicts."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT role, content FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
    """, (session_id,)).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def create_session(session_id: str, name: str = ""):
    """Create a new session record."""
    now = datetime.now().isoformat()
    conn = get_connection()
    conn.execute("""
        INSERT OR IGNORE INTO sessions (id, name, created_at, last_active)
        VALUES (?, ?, ?, ?)
    """, (session_id, name, now, now))
    conn.commit()
    conn.close()


def get_db_stats():
    """Return a summary of what's in the database."""
    conn = get_connection()
    stats = {
        "total_jobs":     conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "jobs_with_scores": conn.execute("SELECT COUNT(*) FROM jobs WHERE match_score IS NOT NULL").fetchone()[0],
        "total_messages": conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        "total_sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
    }
    conn.close()
    return stats


# ── Run directly to test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nInitialising database...")
    init_db()
    stats = get_db_stats()
    print(f"  Stats: {stats}")
    print("\n  [OK] memory.py working correctly")