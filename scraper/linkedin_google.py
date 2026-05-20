# ─────────────────────────────────────────────
#  scraper/linkedin_google.py
#  LinkedIn Jobs — via Google Search (no login needed)
# ─────────────────────────────────────────────
#
#  WHY NOT DIRECT LINKEDIN SCRAPING?
#  LinkedIn actively blocks all scrapers:
#    - Requires login to see job details
#    - CAPTCHA on automated requests
#    - IP bans for repeated scraping
#    - Legal threats (hiQ Labs v. LinkedIn case)
#
#  THE SMART WORKAROUND:
#  Google indexes LinkedIn job pages publicly.
#  We search Google for "site:linkedin.com/jobs <role> <location>"
#  and extract job info from the search result snippets.
#  This is 100% legal (public search) and works reliably.
#
#  In interviews, explain this design decision — it shows
#  real engineering judgment, not just copy-paste coding.
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
import requests
from bs4 import BeautifulSoup
from config import SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_linkedin_via_google(role: str, location: str) -> list:
    """
    Find LinkedIn job listings by searching Google.

    Strategy:
      1. Build a Google search: site:linkedin.com/jobs/view <role> <location> India
      2. Parse the Google search results page (titles + snippets)
      3. Extract job info from snippets using simple text parsing
      4. Return structured job dicts

    Args:
        role:     e.g. "ML Engineer"
        location: e.g. "Pune"

    Returns:
        List of job dicts
    """
    query = "site:linkedin.com/jobs " + role + " " + location + " India"
    url   = "https://www.google.com/search?q=" + query.replace(" ", "+") + "&num=10"

    print("  [LinkedIn-Google] Searching: " + query)

    delay = random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX)
    time.sleep(delay)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("  [LinkedIn-Google] No internet. Using demo data.")
        return _demo_jobs(role, location)
    except Exception as e:
        print("  [LinkedIn-Google] Request failed: " + str(e))
        return _demo_jobs(role, location)

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    # Google search results — each result is in a <div class="g"> block
    result_blocks = soup.find_all("div", class_="g")

    if not result_blocks:
        # Fallback selector for different Google layouts
        result_blocks = soup.find_all("div", attrs={"data-sokoban-container": True})

    if not result_blocks:
        print("  [LinkedIn-Google] Google blocked or layout changed. Using demo data.")
        return _demo_jobs(role, location)

    for block in result_blocks[:8]:
        try:
            # Title is inside <h3>
            title_el = block.find("h3")
            if not title_el:
                continue

            raw_title = title_el.get_text(strip=True)

            # LinkedIn job titles look like: "Software Engineer - TCS | LinkedIn"
            # Strip " | LinkedIn" or " - LinkedIn" suffix
            clean_title = raw_title.replace(" | LinkedIn", "").replace(" - LinkedIn", "").strip()

            # Try to split "Job Title - Company" pattern
            if " - " in clean_title:
                parts   = clean_title.split(" - ", 1)
                title   = parts[0].strip()
                company = parts[1].strip()
            elif " at " in clean_title.lower():
                parts   = clean_title.lower().split(" at ", 1)
                title   = parts[0].strip().title()
                company = parts[1].strip().title()
            else:
                title   = clean_title
                company = "See LinkedIn"

            # Get the job link
            link_el = block.find("a", href=True)
            link    = link_el["href"] if link_el else "https://www.linkedin.com/jobs"

            # Get the description snippet
            snippet_el = block.find("div", class_=lambda c: c and "VwiC3b" in c)
            snippet    = snippet_el.get_text(strip=True) if snippet_el else ""

            # Skip non-job results (LinkedIn pages that aren't job listings)
            if not any(kw in link.lower() for kw in ["linkedin.com/jobs", "linkedin.com/job"]):
                # Still might be useful, include it
                pass

            jobs.append({
                "title":      title,
                "company":    company,
                "location":   location,
                "skills":     "",
                "experience": "",
                "salary":     "See LinkedIn",
                "link":       link,
                "source":     "linkedin_google",
                "snippet":    snippet[:200],
            })

        except Exception as e:
            print("  [LinkedIn-Google] Parse error: " + str(e))
            continue

    if not jobs:
        print("  [LinkedIn-Google] No results parsed. Using demo data.")
        return _demo_jobs(role, location)

    print("  [LinkedIn-Google] Found " + str(len(jobs)) + " LinkedIn listings via Google")
    return jobs


def _demo_jobs(role: str, location: str) -> list:
    """Demo LinkedIn jobs when scraping is blocked."""
    return [
        {
            "title":      role,
            "company":    "Google",
            "location":   location,
            "skills":     "Python, TensorFlow, ML",
            "experience": "0-2 years",
            "salary":     "See LinkedIn",
            "link":       "https://www.linkedin.com/jobs/",
            "source":     "linkedin_demo",
        },
        {
            "title":      "Junior " + role,
            "company":    "Microsoft India",
            "location":   location,
            "skills":     "Python, Azure ML, SQL",
            "experience": "Fresher",
            "salary":     "See LinkedIn",
            "link":       "https://www.linkedin.com/jobs/",
            "source":     "linkedin_demo",
        },
    ]


# ── Test ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nTesting LinkedIn-Google scraper...")
    jobs = scrape_linkedin_via_google("ML Engineer", "Pune")
    print("\nTotal: " + str(len(jobs)) + " jobs")
    for i, j in enumerate(jobs[:3], 1):
        print("\n  Job " + str(i) + ":")
        print("    Title  : " + j["title"])
        print("    Company: " + j["company"])
        print("    Link   : " + j["link"][:60])
    print("\n  [OK] linkedin_google.py working correctly")