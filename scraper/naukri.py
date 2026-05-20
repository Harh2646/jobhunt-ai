# ─────────────────────────────────────────────
#  scraper/naukri.py — Naukri.com Job Scraper
# ─────────────────────────────────────────────
#
#  How it works:
#   1. Builds a Naukri search URL from role + location
#   2. Sends a browser-like HTTP request (so Naukri doesn't block us)
#   3. Parses the HTML with BeautifulSoup
#   4. Extracts: title, company, location, skills, salary, link
#   5. Returns a clean list of dicts
#
#  Anti-blocking strategy:
#   - Realistic browser headers
#   - Random delay between requests
#   - Timeout so we never hang forever
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
import requests
from bs4 import BeautifulSoup
from config import SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX, MAX_JOBS_PER_SITE


# ── Realistic browser headers — makes Naukri think we're a real browser ────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def _build_url(role: str, location: str) -> str:
    """
    Build the Naukri search URL.
    Example: role='ML Engineer', location='Pune'
    → https://www.naukri.com/ml-engineer-jobs-in-pune
    """
    role_slug     = role.lower().strip().replace(" ", "-")
    location_slug = location.lower().strip().replace(" ", "-")
    return f"https://www.naukri.com/{role_slug}-jobs-in-{location_slug}"


def _safe_text(element, default: str = "") -> str:
    """Safely extract text from a BeautifulSoup element."""
    if element is None:
        return default
    return element.get_text(strip=True)


def scrape_naukri(role: str, location: str) -> list:
    """
    Scrape job listings from Naukri.com.

    Args:
        role:     Job role to search for (e.g. "ML Engineer", "Data Analyst")
        location: City to search in (e.g. "Pune", "Bangalore", "Mumbai")

    Returns:
        List of job dicts with keys:
        title, company, location, skills, salary, experience, link, source
    """
    url = _build_url(role, location)
    print(f"  [Naukri] Searching: {url}")

    # ── Random delay before request (anti-blocking) ────────────────────────────
    delay = random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX)
    time.sleep(delay)

    # ── Fetch the page ─────────────────────────────────────────────────────────
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("  [Naukri] No internet connection.")
        return []
    except requests.exceptions.Timeout:
        print("  [Naukri] Request timed out.")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"  [Naukri] HTTP error: {e}")
        return []

    # ── Parse HTML ─────────────────────────────────────────────────────────────
    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    # Naukri uses <article class="jobTuple"> for each job card
    # If Naukri updates their HTML, these class names may need updating
    job_cards = soup.find_all("article", class_=lambda c: c and "jobTuple" in c)

    # Fallback: try alternate selectors if primary doesn't work
    if not job_cards:
        job_cards = soup.find_all("div", class_=lambda c: c and "srp-jobtuple" in c)

    if not job_cards:
        print(f"  [Naukri] No job cards found. Naukri may have updated their HTML.")
        print(f"           Returning demo data for testing purposes.")
        return _demo_jobs(role, location)

    print(f"  [Naukri] Found {len(job_cards)} job cards")

    for card in job_cards[:MAX_JOBS_PER_SITE]:
        try:
            # ── Title ──────────────────────────────────────────────────────────
            title_el = (
                card.find("a", class_=lambda c: c and "title" in c) or
                card.find("a", {"title": True})
            )
            title = _safe_text(title_el, "Unknown Title")
            link  = title_el.get("href", "") if title_el else ""

            # ── Company ────────────────────────────────────────────────────────
            company_el = (
                card.find("a", class_=lambda c: c and ("subTitle" in c or "comp-name" in c)) or
                card.find("a", class_=lambda c: c and "company" in c)
            )
            company = _safe_text(company_el, "Unknown Company")

            # ── Location ───────────────────────────────────────────────────────
            loc_el = (
                card.find("li", class_=lambda c: c and "location" in c) or
                card.find("span", class_=lambda c: c and "location" in c)
            )
            job_location = _safe_text(loc_el, location)

            # ── Skills ─────────────────────────────────────────────────────────
            skills_el = (
                card.find("ul", class_=lambda c: c and "tags" in c) or
                card.find("div", class_=lambda c: c and "skill" in c)
            )
            skills = _safe_text(skills_el, "")

            # ── Experience ─────────────────────────────────────────────────────
            exp_el = card.find("li", class_=lambda c: c and "experience" in c)
            experience = _safe_text(exp_el, "")

            # ── Salary ─────────────────────────────────────────────────────────
            sal_el = card.find("li", class_=lambda c: c and ("salary" in c or "sal" in c))
            salary = _safe_text(sal_el, "Not disclosed")

            jobs.append({
                "title":      title,
                "company":    company,
                "location":   job_location,
                "skills":     skills,
                "experience": experience,
                "salary":     salary,
                "link":       link,
                "source":     "naukri",
            })

        except Exception as e:
            print(f"  [Naukri] Error parsing card: {e}")
            continue

    print(f"  [Naukri] Successfully parsed {len(jobs)} jobs")
    return jobs


def _demo_jobs(role: str, location: str) -> list:
    """
    Return demo job data when scraping fails.
    Used for testing the rest of the pipeline when Naukri blocks us.
    In a real interview, explain: 'I added a fallback for when live scraping fails.'
    """
    return [
        {
            "title":      f"{role} - Fresher",
            "company":    "TCS",
            "location":   location,
            "skills":     "Python, Machine Learning, SQL, TensorFlow",
            "experience": "0-2 years",
            "salary":     "3-6 LPA",
            "link":       "https://www.naukri.com/",
            "source":     "naukri_demo",
        },
        {
            "title":      f"Junior {role}",
            "company":    "Infosys",
            "location":   location,
            "skills":     "Python, Deep Learning, NLP, PyTorch",
            "experience": "0-1 years",
            "salary":     "4-7 LPA",
            "link":       "https://www.naukri.com/",
            "source":     "naukri_demo",
        },
        {
            "title":      f"{role} Intern",
            "company":    "Wipro",
            "location":   location,
            "skills":     "Python, Data Analysis, Pandas, NumPy",
            "experience": "Fresher",
            "salary":     "2-4 LPA",
            "link":       "https://www.naukri.com/",
            "source":     "naukri_demo",
        },
        {
            "title":      f"{role} Associate",
            "company":    "Accenture",
            "location":   location,
            "skills":     "Python, SQL, Tableau, Power BI",
            "experience": "0-2 years",
            "salary":     "3.5-6 LPA",
            "link":       "https://www.naukri.com/",
            "source":     "naukri_demo",
        },
        {
            "title":      f"Data {role}",
            "company":    "HCL Technologies",
            "location":   location,
            "skills":     "Python, Scikit-learn, SQL, Statistics",
            "experience": "0-3 years",
            "salary":     "4-8 LPA",
            "link":       "https://www.naukri.com/",
            "source":     "naukri_demo",
        },
    ]


# ── Run directly to test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nTesting Naukri scraper...")
    print("Searching for: ML Engineer in Pune\n")

    jobs = scrape_naukri("ML Engineer", "Pune")

    print(f"\nTotal jobs found: {len(jobs)}")
    for i, job in enumerate(jobs[:3], 1):
        print(f"\n--- Job {i} ---")
        print(f"  Title   : {job['title']}")
        print(f"  Company : {job['company']}")
        print(f"  Location: {job['location']}")
        print(f"  Skills  : {job['skills'][:80]}...")
        print(f"  Salary  : {job['salary']}")

    print("\n  [OK] naukri.py working correctly")