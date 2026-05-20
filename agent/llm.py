# ─────────────────────────────────────────────
#  agent/llm.py — LLM Interface (Ollama + Groq)
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import requests
from config import (
    USE_LOCAL_LLM, OLLAMA_BASE_URL, LOCAL_MODEL,
    GROQ_API_KEY, GROQ_MODEL, MAX_TOKENS, TEMPERATURE,
)

# ── System Prompt ──────────────────────────────────────────────────────────────
#
#  CRITICAL: This prompt must force small models (gemma3:4b) to output JSON.
#  Small models tend to respond conversationally. We fix this by:
#   1. Showing an exact example of what we want
#   2. Saying "NEVER explain, NEVER ask questions, ONLY output JSON"
#   3. Repeating the JSON instruction at the end
#
SYSTEM_PROMPT = """You are JobHunt AI, a job hunting agent. You ONLY respond in JSON.

AVAILABLE TOOLS:
- web_scraper: finds jobs from Naukri, Internshala, LinkedIn
- resume_analyzer: scores resume match % against a job
- email_drafter: writes a cold email for a job application
- report_builder: generates a PDF report of top jobs

STRICT RULES — NEVER BREAK THESE:
1. You MUST respond with ONLY a JSON object. No text before or after.
2. NEVER say "I need more information". NEVER ask questions. Just use the tools.
3. NEVER explain what you are doing. Just output the JSON.
4. If the user wants jobs → use web_scraper immediately.
5. If the user wants email → use email_drafter immediately with whatever info you have.
6. If the user wants resume scored → use resume_analyzer immediately.
7. If you have the final answer → use final_answer action.

JSON FORMAT — use EXACTLY this structure:

To call a tool:
{"thought": "I will search for jobs now", "action": "web_scraper", "action_input": {"role": "ML Engineer", "location": "Pune"}}

To give final answer:
{"thought": "I have the answer", "action": "final_answer", "action_input": {"answer": "your answer here"}}

REMEMBER: Output ONLY JSON. No explanations. No questions. No markdown. Just the JSON object."""


# ── Ollama Backend ─────────────────────────────────────────────────────────────

def _call_ollama(messages: list, system: str = SYSTEM_PROMPT) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": LOCAL_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
        }
    }
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "\n[ERROR] Cannot connect to Ollama.\n"
            "Open a new terminal and run: ollama serve\n"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            "\n[ERROR] Ollama timed out. Wait 30 seconds and try again."
        )


# ── Groq Backend ───────────────────────────────────────────────────────────────

def _call_groq(messages: list, system: str = SYSTEM_PROMPT) -> str:
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        raise ValueError(
            "\n[ERROR] Groq API key not set.\n"
            "Get free key at https://console.groq.com\n"
            "Add to .env: GROQ_API_KEY=gsk_xxxx\n"
            "Or set USE_LOCAL_LLM = True in config.py"
        )
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system}] + messages,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "json_object"},  # Groq supports forced JSON mode
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"\n[ERROR] Groq API error: {e}")


# ── Main chat function ─────────────────────────────────────────────────────────

def chat(messages: list, system: str = SYSTEM_PROMPT) -> str:
    """Send messages to LLM and return response string."""
    if USE_LOCAL_LLM:
        return _call_ollama(messages, system)
    else:
        return _call_groq(messages, system)


def parse_agent_response(response: str) -> dict:
    """
    Parse the agent's JSON response.
    Tries multiple strategies to extract valid JSON from the model output.
    Small models often wrap JSON in markdown or add extra text — we handle all cases.
    """
    text = response.strip()

    # Strategy 1: Strip markdown code fences (```json ... ```)
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                try:
                    return json.loads(part)
                except json.JSONDecodeError:
                    pass

    # Strategy 2: Direct parse
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find JSON object anywhere in the text
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    # Strategy 4: Model gave plain text — treat as final answer
    return {
        "thought": "Model returned plain text.",
        "action": "final_answer",
        "action_input": {"answer": response}
    }


# ── Test ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nTesting LLM connection...")
    backend = "Ollama (local)" if USE_LOCAL_LLM else "Groq (online)"
    print(f"  Backend : {backend}")
    print(f"  Model   : {LOCAL_MODEL if USE_LOCAL_LLM else GROQ_MODEL}")
    print(f"  Calling LLM...\n")
    try:
        test_msg = [{"role": "user", "content": 'Output this JSON exactly: {"thought": "test ok", "action": "final_answer", "action_input": {"answer": "LLM connection successful"}}'}]
        response = chat(test_msg)
        parsed   = parse_agent_response(response)
        print(f"  Raw     : {response[:100]}...")
        print(f"  Action  : {parsed.get('action')}")
        print(f"  Answer  : {parsed.get('action_input', {}).get('answer', 'N/A')}")
        print("\n  [OK] llm.py working correctly")
    except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
        print(e)
        sys.exit(1)