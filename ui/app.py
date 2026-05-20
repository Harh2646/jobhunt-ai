# ─────────────────────────────────────────────
#  ui/app.py — Streamlit Web Interface
# ─────────────────────────────────────────────
#
#  Run with:  streamlit run ui/app.py
#
#  Features:
#   - Chat interface to talk to the agent
#   - Sidebar with quick-action buttons
#   - Live tool execution status
#   - PDF report download button
#   - Session history display
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# ── Page configuration — must be first Streamlit call ─────────────────────────
st.set_page_config(
    page_title="JobHunt AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main background */
    .stApp { background-color: #0f0f1a; }

    /* Chat message styling */
    .user-msg {
        background: #1e1e3a;
        border-left: 4px solid #4361ee;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 8px 0;
        color: #e0e0ff;
    }
    .agent-msg {
        background: #1a2a1a;
        border-left: 4px solid #06d6a0;
        padding: 12px 16px;
        border-radius: 8px;
        margin: 8px 0;
        color: #e0ffe0;
    }

    /* Header */
    .main-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        margin-bottom: 20px;
        border: 1px solid #4361ee;
    }

    /* Sidebar */
    .css-1d391kg { background-color: #0d0d1f; }

    /* Status badge */
    .status-ok  { color: #06d6a0; font-weight: bold; }
    .status-err { color: #ef233c; font-weight: bold; }

    /* Quick action buttons */
    .stButton > button {
        width: 100%;
        background: #1e1e3a;
        color: #a0a0ff;
        border: 1px solid #4361ee;
        border-radius: 6px;
        padding: 8px;
        text-align: left;
    }
    .stButton > button:hover {
        background: #4361ee;
        color: white;
    }
</style>
""", unsafe_allow_html=True)


# ── Session state initialization ───────────────────────────────────────────────
if "agent" not in st.session_state:
    st.session_state.agent       = None
if "messages" not in st.session_state:
    st.session_state.messages    = []    # list of {"role","content"}
if "report_path" not in st.session_state:
    st.session_state.report_path = None
if "last_jobs" not in st.session_state:
    st.session_state.last_jobs   = []
if "agent_ready" not in st.session_state:
    st.session_state.agent_ready = False


def get_agent():
    """Get or create the agent (cached in session state)."""
    if st.session_state.agent is None:
        from agent.orchestrator import JobHuntAgent
        st.session_state.agent       = JobHuntAgent(session_name="UI Session")
        st.session_state.agent_ready = True
    return st.session_state.agent


def check_ollama():
    """Check if Ollama is running."""
    try:
        import requests as req
        resp = req.get("http://localhost:11434", timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🤖 JobHunt AI")
    st.markdown("*Agentic Job Search — No LangChain*")
    st.divider()

    # Ollama status
    ollama_ok = check_ollama()
    if ollama_ok:
        st.markdown('<p class="status-ok">● Ollama: Online</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-err">● Ollama: Offline</p>', unsafe_allow_html=True)
        st.warning("Run `ollama serve` in a terminal first!")

    st.divider()
    st.markdown("### 🎯 Quick Actions")
    st.caption("Click any button to run a preset command")

    if st.button("🔍 Find ML Jobs in Pune"):
        st.session_state.quick_action = "Find ML Engineer jobs in Pune, analyze my resume match, and show the top 5 results"

    if st.button("📊 Find Data Analyst Jobs"):
        st.session_state.quick_action = "Find Data Analyst jobs in Bangalore and score my resume for the best match"

    if st.button("✉️ Write Cold Email"):
        st.session_state.quick_action = "Write a cold email for ML Engineer position at TCS with my skills"

    if st.button("📄 Generate PDF Report"):
        st.session_state.quick_action = "Generate a PDF report of all the jobs found so far"

    if st.button("🔄 Find Python Developer Jobs"):
        st.session_state.quick_action = "Find Python Developer jobs in Hyderabad and write a cold email for the best match"

    st.divider()
    st.markdown("### ⚙️ Settings")

    role_input     = st.text_input("Default Role",     "ML Engineer")
    location_input = st.text_input("Default Location", "Pune")

    st.divider()
    st.markdown("### 📊 Session Stats")
    if st.session_state.agent:
        summary = st.session_state.agent.get_session_summary()
        st.metric("Tools Used",  len(summary["tools_used"]))
        st.metric("Jobs Found",  summary["jobs_found"])
        st.metric("Messages",    summary["messages"])
    else:
        st.info("Start a conversation to see stats")

    if st.button("🗑️ New Session"):
        st.session_state.agent       = None
        st.session_state.messages    = []
        st.session_state.report_path = None
        st.session_state.last_jobs   = []
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN AREA
# ══════════════════════════════════════════════════════════════════════════════

# Header
st.markdown("""
<div class="main-header">
    <h1>🤖 JobHunt AI</h1>
    <p style="color:#a0a0ff; margin:0">
        Agentic Job Search Assistant &nbsp;|&nbsp;
        ReAct Loop &nbsp;|&nbsp;
        Built without LangChain &nbsp;|&nbsp;
        Runs 100% Locally
    </p>
</div>
""", unsafe_allow_html=True)

# Two columns: chat (left) + info panel (right)
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### 💬 Chat with the Agent")

    # ── Display conversation history ───────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.markdown("""
            <div style="text-align:center; padding:40px; color:#555577;">
                <h3>👋 Hello! I'm JobHunt AI</h3>
                <p>I can help you:</p>
                <ul style="text-align:left; display:inline-block;">
                    <li>Find jobs from Naukri, Internshala & LinkedIn</li>
                    <li>Score your resume against any job (0–100%)</li>
                    <li>Write personalized cold emails</li>
                    <li>Generate a professional PDF report</li>
                </ul>
                <p>Try: <em>"Find ML Engineer jobs in Pune"</em></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(
                        '<div class="user-msg">🧑 <b>You:</b> ' + msg["content"] + '</div>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown(
                        '<div class="agent-msg">🤖 <b>Agent:</b> ' + msg["content"].replace("\n", "<br>") + '</div>',
                        unsafe_allow_html=True
                    )

    # ── Chat input ─────────────────────────────────────────────────────────────
    user_input = st.chat_input("Ask the agent... e.g. Find ML jobs in Pune")

    # Handle quick action buttons from sidebar
    if "quick_action" in st.session_state and st.session_state.quick_action:
        user_input = st.session_state.quick_action
        st.session_state.quick_action = None

    if user_input:
        if not ollama_ok:
            st.error("Ollama is not running! Open a terminal and run: ollama serve")
        else:
            # Add user message to display
            st.session_state.messages.append({"role": "user", "content": user_input})

            # Run the agent with a spinner
            with st.spinner("Agent is thinking and working..."):
                try:
                    agent  = get_agent()
                    answer = agent.run(user_input)

                    # Check if a new report was generated
                    if agent.last_jobs:
                        st.session_state.last_jobs = agent.last_jobs

                    # Check for PDF report in output folder
                    if os.path.exists("output/reports"):
                        reports = sorted(
                            [f for f in os.listdir("output/reports") if f.endswith(".pdf")],
                            reverse=True
                        )
                        if reports:
                            st.session_state.report_path = os.path.join("output/reports", reports[0])

                except Exception as e:
                    answer = "Sorry, I encountered an error: " + str(e)

            st.session_state.messages.append({"role": "assistant", "content": answer})
            st.rerun()

    # ── PDF Download button ────────────────────────────────────────────────────
    if st.session_state.report_path and os.path.exists(st.session_state.report_path):
        st.divider()
        st.success("PDF Report ready!")
        with open(st.session_state.report_path, "rb") as f:
            st.download_button(
                label="📥 Download Job Report PDF",
                data=f.read(),
                file_name="jobhunt_report.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

with col2:
    st.markdown("### 📋 How It Works")
    st.markdown("""
    **ReAct Loop (Reasoning + Acting):**

    ```
    User asks a question
          ↓
    Agent THINKS
    "I need to scrape jobs first"
          ↓
    Agent ACTS
    Calls web_scraper tool
          ↓
    Agent OBSERVES
    "Found 8 jobs"
          ↓
    Agent THINKS again
    "Now I should score the resume"
          ↓
    Agent ACTS
    Calls resume_analyzer tool
          ↓
    Agent OBSERVES
    "Match: 74%"
          ↓
    Agent gives FINAL ANSWER
    ```

    **Built without LangChain** — every step of this loop is hand-coded in `orchestrator.py`
    """)

    st.divider()
    st.markdown("### 🛠️ Available Tools")
    tools = {
        "🔍 web_scraper":     "Naukri + Internshala + LinkedIn",
        "📊 resume_analyzer": "Scores resume 0-100%",
        "✉️ email_drafter":   "Writes cold emails",
        "📄 report_builder":  "Generates PDF report",
    }
    for tool, desc in tools.items():
        st.markdown("**" + tool + "**")
        st.caption(desc)

    st.divider()
    st.markdown("### 💡 Example Prompts")
    examples = [
        "Find ML Engineer jobs in Pune",
        "Find Data Analyst jobs in Mumbai",
        "Score my resume for TCS ML Engineer",
        "Write a cold email for Infosys DA job",
        "Generate a PDF report of top jobs",
        "Find Python jobs in Bangalore and email",
    ]
    for ex in examples:
        st.caption("• " + ex)