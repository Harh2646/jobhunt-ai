# ─────────────────────────────────────────────
#  setup.py — One-Command Project Setup
# ─────────────────────────────────────────────

import os
import sys
import subprocess


def print_header():
    print("\n" + "=" * 45)
    print("       JobHunt AI — Setup Script")
    print("=" * 45 + "\n")


def check_python():
    print("Step 1 — Checking Python version...")
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 9):
        print(f"  [ERROR] Python 3.9+ required. You have {major}.{minor}")
        sys.exit(1)
    print(f"  [OK] Python {major}.{minor}")


def create_folders():
    print("\nStep 2 — Creating project folders...")
    folders = ["data", "output/reports", "agent", "scraper", "ui"]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"  [OK] {folder}/")

    # Create empty __init__.py files
    init_files = ["agent/__init__.py", "scraper/__init__.py", "ui/__init__.py"]
    for f in init_files:
        if not os.path.exists(f):
            open(f, "w").close()
            print(f"  [OK] {f} created")


def install_packages():
    print("\nStep 3 — Installing Python dependencies...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [ERROR] pip install failed:\n{result.stderr}")
        sys.exit(1)
    print("  [OK] All packages installed")


def init_database():
    print("\nStep 4 — Initialising SQLite database...")
    try:
        # Import and call init_db directly
        sys.path.insert(0, os.getcwd())
        from agent.memory import init_db
        init_db()
        print("  [OK] Database ready at data/jobhunt.db")
    except Exception as e:
        print(f"  [ERROR] Database init failed: {e}")
        sys.exit(1)


def check_ollama():
    print("\nStep 5 — Checking Ollama...")
    result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        print("  [WARN] Ollama not found. Install from: https://ollama.com/download")
        print("         Then run:  ollama serve")
        print("         Then run:  ollama pull gemma3:4b")
    else:
        version = result.stdout.strip()
        print(f"  [OK] {version}")

        # Check if model is already pulled
        list_result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "gemma3:4b" in list_result.stdout:
            print("  [OK] gemma3:4b model already downloaded")
        else:
            print("  [INFO] gemma3:4b not found. Run this to download it:")
            print("         ollama pull gemma3:4b  (~3.3 GB, one time)")


def create_env_file():
    print("\nStep 6 — Checking .env file...")
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("# JobHunt AI — Secret keys\n")
            f.write("# Get a free Groq key at: https://console.groq.com\n")
            f.write("GROQ_API_KEY=your_groq_api_key_here\n")
        print("  [OK] .env file created")
    else:
        print("  [OK] .env file already exists")


def print_next_steps():
    print("\n" + "=" * 45)
    print("       Setup Complete!")
    print("=" * 45)
    print("""
Next steps:
  1. Start Ollama (in a separate terminal):
       ollama serve

  2. Test the LLM:
       python agent/llm.py

  3. Test the database:
       python agent/memory.py

  4. Copy your resume into the project root:
       rename it to:  resume.pdf

  5. When tests pass, say "start Phase 2"!
""")


if __name__ == "__main__":
    print_header()
    check_python()
    create_folders()
    install_packages()
    init_database()
    check_ollama()
    create_env_file()
    print_next_steps()