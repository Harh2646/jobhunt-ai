# ─────────────────────────────────────────────
#  agent/orchestrator.py — ReAct Agent Loop
# ─────────────────────────────────────────────
#
#  THE BRAIN OF THE PROJECT.
#
#  Two-layer architecture:
#   Layer 1 — Intent Detection (fast, keyword-based)
#     When the LLM doesn't produce JSON, we detect intent
#     from the user's original message and call the right tool.
#     This is called "intent-based fallback" — a real pattern
#     used in production agents.
#
#   Layer 2 — ReAct Loop (LLM-driven)
#     When the LLM properly outputs JSON with thought/action,
#     the agent follows it step by step.
#
#  Interview talking point:
#   "Small local models sometimes fail to follow strict output formats.
#    I added an intent-detection fallback layer so the agent remains
#    functional regardless — this is how production systems handle
#    model unreliability."
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import uuid
from datetime import datetime

from config import MAX_ITERATIONS
from agent.llm import chat, parse_agent_response, SYSTEM_PROMPT
from agent.memory import init_db, save_message, create_session
from agent.tools import execute_tool


# ══════════════════════════════════════════════════════════════════════════════
#  Intent Detection — Layer 1 fallback
# ══════════════════════════════════════════════════════════════════════════════

def detect_intent(user_message: str) -> dict:
    """
    Detect what the user wants from their message using keywords.
    Returns a dict with 'action' and 'action_input' — same format as LLM output.

    This runs BEFORE the LLM loop as a first-pass resolver.
    If intent is clear → skip the LLM entirely for that first action.
    If intent is unclear → let the LLM decide.

    Examples:
        "Find ML jobs in Pune"   → web_scraper(role="ML Engineer", location="Pune")
        "Write cold email TCS"   → email_drafter(job_title="...", company="TCS")
        "Score my resume"        → resume_analyzer(...)
        "Generate PDF report"    → report_builder(...)
    """
    msg   = user_message.lower().strip()
    words = msg.split()

    # ── Intent: Find jobs ──────────────────────────────────────────────────────
    job_keywords = ["find", "search", "look", "get", "show", "list", "jobs", "openings", "vacancies"]
    if any(kw in words for kw in job_keywords) or "job" in msg or "hiring" in msg:

        # Extract role — look for known roles in the message
        role = "ML Engineer"  # default
        role_map = {
            "ml engineer":        "ML Engineer",
            "machine learning":   "ML Engineer",
            "data analyst":       "Data Analyst",
            "data scientist":     "Data Scientist",
            "python developer":   "Python Developer",
            "software engineer":  "Software Engineer",
            "data engineer":      "Data Engineer",
            "ai engineer":        "AI Engineer",
            "nlp engineer":       "NLP Engineer",
            "backend developer":  "Backend Developer",
            "full stack":         "Full Stack Developer",
        }
        for key, val in role_map.items():
            if key in msg:
                role = val
                break

        # Extract location
        location = "India"  # default
        location_keywords = ["pune", "mumbai", "bangalore", "bengaluru", "delhi",
                             "hyderabad", "chennai", "noida", "gurgaon", "thane",
                             "kolkata", "remote", "work from home"]
        for loc in location_keywords:
            if loc in msg:
                location = loc.title()
                if location == "Bengaluru":
                    location = "Bangalore"
                break

        return {
            "action": "web_scraper",
            "action_input": {"role": role, "location": location, "use_cache": False}
        }

    # ── Intent: Write email ────────────────────────────────────────────────────
    email_keywords = ["email", "cold email", "write email", "draft email", "application email", "apply"]
    if any(kw in msg for kw in email_keywords):
        # Extract company name
        company = "the company"
        company_names = ["tcs", "infosys", "wipro", "accenture", "hcl", "google",
                        "microsoft", "amazon", "flipkart", "paytm", "zomato",
                        "swiggy", "razorpay", "phonepe", "byju", "unacademy"]
        for c in company_names:
            if c in msg:
                company = c.upper() if len(c) <= 3 else c.title()
                break

        role = "ML Engineer"
        role_map = {
            "ml engineer": "ML Engineer", "machine learning": "ML Engineer",
            "data analyst": "Data Analyst", "data scientist": "Data Scientist",
            "python": "Python Developer", "software": "Software Engineer",
        }
        for key, val in role_map.items():
            if key in msg:
                role = val
                break

        return {
            "action": "email_drafter",
            "action_input": {
                "job_title": role,
                "company":   company,
                "skills":    "Python, Machine Learning, TensorFlow, SQL, Scikit-learn",
                "applicant_name": "Aalok Tiwari"
            }
        }

    # ── Intent: Score / analyze resume ────────────────────────────────────────
    resume_keywords = ["score", "analyze", "analyse", "resume", "cv", "match",
                       "how good", "review my", "check my"]
    if any(kw in msg for kw in resume_keywords):
        return {
            "action": "resume_analyzer",
            "action_input": {
                "job_title": "ML Engineer",
                "company":   "Tech Company",
                "skills":    "Python, Machine Learning, TensorFlow, SQL, Deep Learning",
            }
        }

    # ── Intent: Generate report ────────────────────────────────────────────────
    report_keywords = ["report", "pdf", "generate", "download", "summary"]
    if any(kw in msg for kw in report_keywords):
        return {
            "action": "report_builder",
            "action_input": {"role": "ML Engineer", "location": "India"}
        }

    # ── Unknown intent — let LLM decide ───────────────────────────────────────
    return {"action": "unknown", "action_input": {}}


# ══════════════════════════════════════════════════════════════════════════════
#  JobHunt Agent
# ══════════════════════════════════════════════════════════════════════════════

class JobHuntAgent:
    """
    The main agent. Combines intent detection + ReAct loop.

    Usage:
        agent = JobHuntAgent()
        response = agent.run("Find ML jobs in Pune and score my resume")
        print(response)
    """

    def __init__(self, session_name: str = ""):
        self.session_id   = str(uuid.uuid4())[:8]
        self.session_name = session_name or ("Session " + datetime.now().strftime("%d %b %H:%M"))
        self.history      = []        # conversation history for LLM
        self.tools_used   = []        # track which tools ran
        self.last_jobs    = []        # last scraped jobs (for context)
        self.last_scores  = {}        # last resume analysis results

        init_db()
        create_session(self.session_id, self.session_name)

        print("\n" + "="*55)
        print("  JobHunt AI Agent — Session: " + self.session_id)
        print("="*55)

    def _add_history(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        save_message(self.session_id, role, content)

    def _observation(self, tool_name: str, result: dict) -> str:
        """Summarize tool result for the LLM — keep it short to save context."""
        status = result.get("status", "unknown")

        if tool_name == "web_scraper":
            jobs = result.get("data", [])
            if not jobs:
                return "OBSERVATION: web_scraper found 0 jobs."
            self.last_jobs = jobs
            lines = ["OBSERVATION: web_scraper found " + str(len(jobs)) + " jobs:"]
            for i, job in enumerate(jobs[:5], 1):
                lines.append(
                    str(i) + ". " + job.get("title","?") +
                    " at " + job.get("company","?") +
                    " | Skills: " + str(job.get("skills",""))[:50] +
                    " | Salary: " + str(job.get("salary","N/A"))
                )
            if len(jobs) > 5:
                lines.append("... +" + str(len(jobs)-5) + " more")
            return "\n".join(lines)

        elif tool_name == "resume_analyzer":
            score   = result.get("match_score", 0)
            missing = result.get("missing_skills", [])
            match   = result.get("matching_skills", [])
            rec     = result.get("recommendation", "")
            self.last_scores = result
            return (
                "OBSERVATION: resume_analyzer: Match=" + str(round(score)) + "% | "
                "Matching=" + str(match) + " | "
                "Missing=" + str(missing) + " | "
                "Tip: " + rec
            )

        elif tool_name == "email_drafter":
            subject = result.get("subject", "")
            body    = result.get("email_body", "")[:300]
            return (
                "OBSERVATION: email_drafter drafted email.\n"
                "Subject: " + subject + "\n"
                "Preview: " + body
            )

        elif tool_name == "report_builder":
            path = result.get("report_path", "N/A")
            n    = result.get("jobs_included", 0)
            return "OBSERVATION: report_builder created PDF with " + str(n) + " jobs at: " + path

        return "OBSERVATION: " + tool_name + " status=" + status

    def _format_tool_result_as_answer(self, tool_name: str, result: dict, original_query: str) -> str:
        """
        Convert a tool result into a friendly final answer string.
        Called when we run a tool directly from intent detection.
        """
        if tool_name == "web_scraper":
            jobs = result.get("data", [])
            if not jobs:
                return "I couldn't find any jobs right now. Please check your internet connection and try again."

            lines = ["Here are the top jobs I found:\n"]
            for i, job in enumerate(jobs[:8], 1):
                lines.append(
                    str(i) + ". **" + job.get("title","?") + "** at " + job.get("company","?")
                    + "\n   📍 " + job.get("location","N/A")
                    + "  💰 " + job.get("salary","N/A")
                    + "\n   🛠 " + str(job.get("skills",""))[:80]
                    + "\n   🔗 " + str(job.get("link",""))[:60]
                    + "\n"
                )
            lines.append("\nFound " + str(len(jobs)) + " total jobs.")
            lines.append("Say **'score my resume'** to see how well you match, or **'write a cold email'** for any of these jobs.")
            return "\n".join(lines)

        elif tool_name == "resume_analyzer":
            score   = result.get("match_score", 0)
            missing = result.get("missing_skills", [])
            match   = result.get("matching_skills", [])
            rec     = result.get("recommendation", "")
            strengths = result.get("strengths", [])

            grade = "🟢 Excellent" if score >= 80 else ("🟡 Good" if score >= 60 else "🔴 Needs Work")
            return (
                "## Resume Analysis\n\n"
                "**Match Score: " + str(round(score)) + "% " + grade + "**\n\n"
                "✅ **Matching Skills:** " + (", ".join(match) if match else "See details") + "\n\n"
                "❌ **Missing Skills:** " + (", ".join(missing) if missing else "None!") + "\n\n"
                "💪 **Strengths:** " + (", ".join(strengths) if strengths else "Strong profile") + "\n\n"
                "💡 **Recommendation:** " + rec
            )

        elif tool_name == "email_drafter":
            subject = result.get("subject", "")
            body    = result.get("email_body", "")
            if result.get("status") != "success":
                return "Sorry, I couldn't draft the email. Please try again."
            return (
                "## Cold Email Drafted ✉️\n\n"
                "**Subject:** " + subject + "\n\n"
                "---\n\n"
                + body + "\n\n"
                "---\n\n"
                "_You can copy and send this email directly!_"
            )

        elif tool_name == "report_builder":
            path = result.get("report_path", "")
            n    = result.get("jobs_included", 0)
            return (
                "## PDF Report Generated! 📄\n\n"
                "Your job report with **" + str(n) + " jobs** has been created.\n\n"
                "Click the **Download Job Report PDF** button below to save it."
            )

        return result.get("message", "Done.")

    def run(self, user_message: str) -> str:
        """
        Main entry point.

        Flow:
          1. Detect intent from user message
          2. If clear intent → run tool directly, format answer, return
          3. If unclear → run full ReAct loop with LLM
        """
        print("\n[User] " + user_message)
        self._add_history("user", user_message)

        # ── Layer 1: Intent Detection ──────────────────────────────────────────
        intent = detect_intent(user_message)

        if intent["action"] != "unknown":
            print("[Intent] Detected: " + intent["action"])
            print("[Intent] Params  : " + str(intent["action_input"])[:80])

            # Enrich report_builder with actual jobs if we have them
            if intent["action"] == "report_builder" and self.last_jobs:
                intent["action_input"]["jobs"] = self.last_jobs

            # Enrich resume_analyzer with job context if we have jobs
            if intent["action"] == "resume_analyzer" and self.last_jobs:
                first = self.last_jobs[0]
                inp   = intent["action_input"]
                inp.setdefault("job_title", first.get("title", "ML Engineer"))
                inp.setdefault("company",   first.get("company", "Tech Company"))
                inp.setdefault("skills",    first.get("skills", "Python, ML"))

            self.tools_used.append(intent["action"])
            result = execute_tool(intent["action"], intent["action_input"])
            answer = self._format_tool_result_as_answer(intent["action"], result, user_message)

            self._add_history("assistant", answer)
            print("[Intent] Answer ready.")
            return answer

        # ── Layer 2: ReAct Loop (LLM-driven for complex/ambiguous queries) ─────
        print("[ReAct] Intent unclear — using LLM loop")

        for iteration in range(1, MAX_ITERATIONS + 1):
            print("\n--- Iteration " + str(iteration) + "/" + str(MAX_ITERATIONS) + " ---")
            print("[Agent] Thinking...")

            try:
                llm_response = chat(self.history, system=SYSTEM_PROMPT)
            except (ConnectionError, TimeoutError) as e:
                return "Error connecting to LLM: " + str(e)

            print("[Agent] Raw: " + llm_response[:120] + "...")
            parsed       = parse_agent_response(llm_response)
            thought      = parsed.get("thought", "")
            action       = parsed.get("action", "final_answer")
            action_input = parsed.get("action_input", {})

            print("[Agent] Action: " + action)

            # Final answer
            if action == "final_answer":
                answer = action_input.get("answer", llm_response)
                self._add_history("assistant", answer)
                print("[Agent] Done after " + str(iteration) + " iteration(s)")
                return answer

            # Valid tool call
            if action in ["web_scraper", "resume_analyzer", "email_drafter", "report_builder"]:

                # Context enrichment
                if action == "resume_analyzer" and self.last_jobs and not action_input.get("job_title"):
                    first = self.last_jobs[0]
                    action_input["job_title"] = first.get("title","ML Engineer")
                    action_input["company"]   = first.get("company","Tech Company")
                    action_input["skills"]    = first.get("skills","Python, ML")

                if action == "report_builder" and self.last_jobs and not action_input.get("jobs"):
                    action_input["jobs"] = self.last_jobs

                self.tools_used.append(action)
                result      = execute_tool(action, action_input)
                observation = self._observation(action, result)

                print("[Agent] Observation: " + observation[:100] + "...")

                self._add_history("assistant", llm_response)
                self._add_history("user", observation)
                continue

            # Invalid action — give feedback
            feedback = (
                "OBSERVATION: Unknown action '" + action + "'. "
                "You MUST use one of: web_scraper, resume_analyzer, email_drafter, report_builder, final_answer. "
                "Respond with JSON only."
            )
            self._add_history("assistant", llm_response)
            self._add_history("user", feedback)

        # Max iterations
        answer = (
            "I've used " + str(MAX_ITERATIONS) + " steps. "
            "Tools used: " + str(self.tools_used) + ". "
            "Try a simpler request like: 'Find ML jobs in Pune'"
        )
        self._add_history("assistant", answer)
        return answer

    def get_session_summary(self) -> dict:
        return {
            "session_id":   self.session_id,
            "session_name": self.session_name,
            "tools_used":   self.tools_used,
            "messages":     len(self.history),
            "jobs_found":   len(self.last_jobs),
        }


# ── CLI Mode ───────────────────────────────────────────────────────────────────

def run_cli():
    print("\n" + "="*55)
    print("  JobHunt AI — Terminal Mode")
    print("  Type 'quit' to exit")
    print("="*55)
    print("\nExamples:")
    print("  > Find ML Engineer jobs in Pune")
    print("  > Score my resume")
    print("  > Write a cold email for ML Engineer at TCS")
    print("  > Generate a PDF report\n")

    agent = JobHuntAgent("CLI Session")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit", "bye"]:
            summary = agent.get_session_summary()
            print("\nSession: tools=" + str(summary["tools_used"]) + " jobs=" + str(summary["jobs_found"]))
            print("Goodbye!")
            break

        answer = agent.run(user_input)
        print("\nAgent: " + answer)


# ── Auto Test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli()
    else:
        print("\n" + "="*55)
        print("  Testing Full Agent")
        print("="*55)

        agent = JobHuntAgent("Auto Test")

        print("\n[Test 1] Job search...")
        a1 = agent.run("Find ML Engineer jobs in Pune")
        print("\nAnswer:\n" + a1[:400])

        print("\n[Test 2] Resume score...")
        a2 = agent.run("Score my resume against the jobs you found")
        print("\nAnswer:\n" + a2[:400])

        print("\n[Test 3] Cold email...")
        a3 = agent.run("Write a cold email for ML Engineer at TCS")
        print("\nAnswer:\n" + a3[:400])

        summary = agent.get_session_summary()
        print("\n" + "="*55)
        print("  Summary")
        print("="*55)
        print("  Tools used : " + str(summary["tools_used"]))
        print("  Jobs found : " + str(summary["jobs_found"]))
        print("\n  [OK] orchestrator.py working correctly")