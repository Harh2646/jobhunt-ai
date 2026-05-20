# ─────────────────────────────────────────────
#  agent/tools.py — All 4 Agent Tools
# ─────────────────────────────────────────────
#
#  Tool 1: web_scraper       — scrapes Naukri + Internshala + LinkedIn via Google
#  Tool 2: resume_analyzer   — scores resume match % using the LLM
#  Tool 3: email_drafter     — writes a personalized cold email using the LLM
#  Tool 4: report_builder    — generates a PDF report with top results
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
from datetime import datetime

from config import RESUME_PATH, REPORTS_DIR
from agent.memory import save_jobs, get_cached_jobs, get_top_jobs
from agent.llm import chat


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 1 — Web Scraper
# ══════════════════════════════════════════════════════════════════════════════

def tool_web_scraper(params: dict) -> dict:
    role      = params.get("role", "ML Engineer")
    location  = params.get("location", "Pune")
    use_cache = params.get("use_cache", True)

    print("\n[Tool: web_scraper] Searching '" + role + "' in '" + location + "'")

    if use_cache:
        cached = get_cached_jobs(role_query=role)
        if cached:
            print("  Using cached data: " + str(len(cached)) + " jobs")
            return {"status": "success", "jobs_found": len(cached),
                    "data": cached, "message": str(len(cached)) + " cached jobs returned"}

    all_jobs = []

    try:
        from scraper.naukri import scrape_naukri
        all_jobs.extend(scrape_naukri(role, location))
    except Exception as e:
        print("  [!] Naukri failed: " + str(e))

    try:
        from scraper.internshala import scrape_internshala
        all_jobs.extend(scrape_internshala(role, location))
    except Exception as e:
        print("  [!] Internshala failed: " + str(e))

    try:
        from scraper.linkedin_google import scrape_linkedin_via_google
        all_jobs.extend(scrape_linkedin_via_google(role, location))
    except Exception as e:
        print("  [!] LinkedIn-Google failed: " + str(e))

    if not all_jobs:
        return {"status": "error", "jobs_found": 0, "data": [],
                "message": "No jobs found. Check internet connection."}

    saved = save_jobs(all_jobs, role_query=role, source="mixed")
    print("  Saved " + str(saved) + " new jobs to database")

    return {"status": "success", "jobs_found": len(all_jobs), "data": all_jobs,
            "message": "Found " + str(len(all_jobs)) + " jobs from Naukri + Internshala + LinkedIn"}


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 2 — Resume Analyzer
# ══════════════════════════════════════════════════════════════════════════════

def _read_resume_text() -> str:
    if not os.path.exists(RESUME_PATH):
        print("  [!] resume.pdf not found. Using placeholder.")
        return (
            "Name: Student Name\n"
            "Skills: Python, Machine Learning, TensorFlow, SQL, Pandas, NumPy\n"
            "Projects: RAG-based QA system (custom, no LangChain), Image classifier\n"
            "Education: B.Tech Computer Science\n"
            "Experience: Fresher (0 years)"
        )
    try:
        import fitz
        doc  = fitz.open(RESUME_PATH)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text.strip()
    except Exception as e:
        print("  [!] Resume read failed: " + str(e))
        return "Resume could not be parsed."


def tool_resume_analyzer(params: dict) -> dict:
    job_title   = params.get("job_title", "Unknown Role")
    company     = params.get("company", "Unknown Company")
    skills      = params.get("skills", "")
    description = params.get("description", "")

    print("\n[Tool: resume_analyzer] Analyzing: " + job_title + " @ " + company)

    resume_text = _read_resume_text()

    desc_text = description[:500] if description else "Not provided"

    prompt = (
        "You are a professional resume reviewer.\n\n"
        "Analyze how well this resume matches the job. Return ONLY valid JSON, nothing else.\n\n"
        "=== RESUME ===\n"
        + resume_text[:2000]
        + "\n\n=== JOB ===\n"
        + "Title: " + job_title + "\n"
        + "Company: " + company + "\n"
        + "Required Skills: " + skills + "\n"
        + "Description: " + desc_text + "\n\n"
        + 'Return ONLY this JSON:\n'
        + '{"match_score": 75, "matching_skills": ["Python", "SQL"], '
        + '"missing_skills": ["Docker"], "strengths": ["Strong Python"], '
        + '"recommendation": "Learn Docker to improve match"}'
    )

    try:
        response = chat(
            [{"role": "user", "content": prompt}],
            system="You are a resume analysis expert. Respond with valid JSON only. No markdown."
        )

        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        analysis = json.loads(clean)
        score    = float(analysis.get("match_score", 0))
        print("  Match score: " + str(round(score)) + "%")

        return {
            "status":          "success",
            "match_score":     score,
            "matching_skills": analysis.get("matching_skills", []),
            "missing_skills":  analysis.get("missing_skills", []),
            "strengths":       analysis.get("strengths", []),
            "recommendation":  analysis.get("recommendation", ""),
            "data":            analysis,
        }

    except json.JSONDecodeError as e:
        print("  [!] JSON parse failed: " + str(e))
        numbers = re.findall(r'\b([0-9]{1,3})\b', response)
        score   = float(numbers[0]) if numbers else 50.0
        return {"status": "partial", "match_score": score,
                "matching_skills": [], "missing_skills": [],
                "recommendation": response[:300], "data": {}}
    except Exception as e:
        return {"status": "error", "match_score": 0, "message": str(e), "data": {}}


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 3 — Email Drafter
# ══════════════════════════════════════════════════════════════════════════════

def tool_email_drafter(params: dict) -> dict:
    job_title      = params.get("job_title", "ML Engineer")
    company        = params.get("company", "the company")
    skills         = params.get("skills", "Python, Machine Learning")
    applicant_name = params.get("applicant_name", "Applicant")

    print("\n[Tool: email_drafter] Writing email: " + job_title + " @ " + company)

    resume_text = _read_resume_text()

    # NOTE: We deliberately avoid backslashes inside f-strings (Python 3.10 bug)
    # So we build the prompt using string concatenation instead.
    signature_json = "Best regards,\\n" + applicant_name

    prompt = (
        "Write a professional cold email applying for a job.\n\n"
        "Job Title: " + job_title + "\n"
        "Company: " + company + "\n"
        "My Key Skills: " + skills + "\n"
        "My Resume Summary: " + resume_text[:800] + "\n\n"
        "Requirements:\n"
        "- Subject line: short and compelling\n"
        "- Length: 150-200 words\n"
        "- Tone: professional but enthusiastic\n"
        "- Mention 2-3 specific skills relevant to this role\n"
        "- End with a clear call to action\n"
        "- Do NOT use cliches like 'I hope this email finds you well'\n\n"
        "Return ONLY this JSON (no markdown, no extra text):\n"
        '{"subject": "subject here", "greeting": "Dear Hiring Manager,", '
        '"body": "email body here", '
        '"signature": "' + signature_json + '"}'
    )

    try:
        response = chat(
            [{"role": "user", "content": prompt}],
            system="You are an expert at writing job application emails. Respond with valid JSON only. No markdown."
        )

        clean = response.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        email_data = json.loads(clean)

        full_email = (
            email_data.get("greeting", "Dear Hiring Manager,")
            + "\n\n"
            + email_data.get("body", "")
            + "\n\n"
            + email_data.get("signature", "Best regards,\n" + applicant_name)
        )

        print("  Email drafted: " + str(len(full_email)) + " chars")
        return {
            "status":     "success",
            "subject":    email_data.get("subject", "Application for " + job_title),
            "email_body": full_email,
            "data":       email_data,
        }

    except json.JSONDecodeError:
        return {
            "status":     "success",
            "subject":    "Application for " + job_title + " at " + company,
            "email_body": response,
            "data":       {},
        }
    except Exception as e:
        return {"status": "error", "subject": "", "email_body": "", "message": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 4 — Report Builder
# ══════════════════════════════════════════════════════════════════════════════

def tool_report_builder(params: dict) -> dict:
    jobs     = params.get("jobs", [])
    role     = params.get("role", "Job")
    location = params.get("location", "India")

    print("\n[Tool: report_builder] Generating PDF...")

    if not jobs:
        jobs = get_top_jobs(limit=10)

    if not jobs:
        return {"status": "error", "message": "No jobs to include in report."}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORTS_DIR, "jobhunt_report_" + timestamp + ".pdf")

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        doc    = SimpleDocTemplate(report_path, pagesize=A4,
                                   leftMargin=2*cm, rightMargin=2*cm,
                                   topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story  = []

        title_style = ParagraphStyle("ReportTitle", parent=styles["Title"],
                                     fontSize=22, textColor=colors.HexColor("#1a1a2e"),
                                     spaceAfter=6)
        sub_style   = ParagraphStyle("ReportSub", parent=styles["Normal"],
                                     fontSize=11, textColor=colors.HexColor("#555555"),
                                     spaceAfter=20)

        gen_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
        story.append(Paragraph("JobHunt AI — Application Report", title_style))
        story.append(Paragraph(
            "Role: " + role + "  |  Location: " + location + "  |  Generated: " + gen_time,
            sub_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4361ee")))
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("Top Matching Jobs", styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))

        table_data = [["#", "Job Title", "Company", "Location", "Match %", "Salary"]]
        for i, job in enumerate(jobs[:10], 1):
            score = job.get("match_score") or 0
            score_str = (str(round(score)) + "%") if score else "N/A"
            table_data.append([
                str(i),
                str(job.get("title", ""))[:35],
                str(job.get("company", ""))[:25],
                str(job.get("location", ""))[:20],
                score_str,
                str(job.get("salary", "N/A"))[:15],
            ])

        tbl = Table(table_data, colWidths=[1*cm, 5*cm, 4*cm, 3*cm, 2*cm, 2.5*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#4361ee")),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",       (0, 0), (-1, 0),  9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
            ("FONTSIZE",       (0, 1), (-1, -1), 8),
            ("GRID",           (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("PADDING",        (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 0.8 * cm))

        job_heading = ParagraphStyle("JobHeading", parent=styles["Heading3"],
                                     textColor=colors.HexColor("#4361ee"),
                                     spaceBefore=12, spaceAfter=4)
        body_s = ParagraphStyle("BodyS", parent=styles["Normal"],
                                fontSize=9, leading=14, spaceAfter=4)

        story.append(Paragraph("Detailed Job Breakdown", styles["Heading2"]))
        for i, job in enumerate(jobs[:5], 1):
            score = job.get("match_score") or 0
            story.append(Paragraph(
                str(i) + ". " + job.get("title","N/A") + " — " + job.get("company","N/A"),
                job_heading))
            story.append(Paragraph(
                "<b>Location:</b> " + job.get("location","N/A") + "   "
                "<b>Salary:</b> " + job.get("salary","N/A") + "   "
                "<b>Match:</b> " + str(round(score)) + "%", body_s))
            if job.get("skills"):
                story.append(Paragraph("<b>Skills:</b> " + job.get("skills",""), body_s))
            if job.get("link"):
                story.append(Paragraph("<b>Apply:</b> " + job.get("link",""), body_s))
            story.append(Spacer(1, 0.3 * cm))

        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
        story.append(Paragraph(
            "Generated by JobHunt AI — Custom ReAct Agent, No LangChain",
            ParagraphStyle("Footer", parent=styles["Normal"],
                           fontSize=8, textColor=colors.grey, spaceBefore=6)))

        doc.build(story)
        print("  Saved: " + report_path)
        return {"status": "success", "report_path": report_path,
                "jobs_included": min(len(jobs), 10),
                "message": "PDF saved to " + report_path}

    except Exception as e:
        return {"status": "error", "message": "PDF failed: " + str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  Tool Dispatcher — called by orchestrator
# ══════════════════════════════════════════════════════════════════════════════

TOOL_MAP = {
    "web_scraper":     tool_web_scraper,
    "resume_analyzer": tool_resume_analyzer,
    "email_drafter":   tool_email_drafter,
    "report_builder":  tool_report_builder,
}


def execute_tool(tool_name: str, params: dict) -> dict:
    if tool_name not in TOOL_MAP:
        return {"status": "error",
                "message": "Unknown tool '" + tool_name + "'. Available: " + str(list(TOOL_MAP.keys()))}
    try:
        return TOOL_MAP[tool_name](params)
    except Exception as e:
        return {"status": "error", "message": "Tool '" + tool_name + "' crashed: " + str(e)}


# ── Test ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("  Testing all 4 tools")
    print("="*50)

    print("\n[TEST 1] Web Scraper")
    r1 = execute_tool("web_scraper", {"role": "ML Engineer", "location": "Pune"})
    print("  Status     : " + r1["status"])
    print("  Jobs found : " + str(r1.get("jobs_found", 0)))
    if r1.get("data"):
        print("  First job  : " + r1["data"][0]["title"] + " @ " + r1["data"][0]["company"])

    print("\n[TEST 2] Resume Analyzer")
    r2 = execute_tool("resume_analyzer", {
        "job_title": "ML Engineer", "company": "TCS",
        "skills": "Python, TensorFlow, SQL, Machine Learning"})
    print("  Status      : " + r2["status"])
    print("  Match score : " + str(round(r2.get("match_score", 0))) + "%")
    print("  Missing     : " + str(r2.get("missing_skills", [])))

    print("\n[TEST 3] Email Drafter")
    r3 = execute_tool("email_drafter", {
        "job_title": "ML Engineer", "company": "TCS",
        "skills": "Python, TensorFlow, ML", "applicant_name": "Your Name"})
    print("  Status  : " + r3["status"])
    print("  Subject : " + r3.get("subject", ""))
    preview = r3.get("email_body", "")[:100]
    print("  Preview : " + preview + "...")

    print("\n[TEST 4] Report Builder")
    demo = [
        {"title": "ML Engineer", "company": "TCS", "location": "Pune",
         "skills": "Python, TF", "salary": "6 LPA", "match_score": 78.0,
         "link": "https://naukri.com"},
        {"title": "Data Analyst", "company": "Infosys", "location": "Bangalore",
         "skills": "SQL, Tableau", "salary": "5 LPA", "match_score": 65.0,
         "link": "https://naukri.com"},
    ]
    r4 = execute_tool("report_builder", {"jobs": demo, "role": "ML Engineer", "location": "Pune"})
    print("  Status : " + r4["status"])
    print("  Path   : " + r4.get("report_path", "N/A"))

    print("\n" + "="*50)
    print("  All 4 tools tested!")
    print("="*50)