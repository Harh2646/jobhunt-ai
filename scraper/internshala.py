# ─────────────────────────────────────────────
#  scraper/internshala.py — Internshala Scraper
# ─────────────────────────────────────────────
#
#  Internshala is the best source for:
#   - Fresher jobs (0-2 years experience)
#   - Internships (paid + unpaid)
#   - Work from home roles
#
#  Same strategy as naukri.py:
#   - Browser-like headers
#   - Random delay
#   - BeautifulSoup parsing
#   - Demo fallback if scraping blocked
# ─────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
import requests
from bs4 import BeautifulSoup
from config import SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX, MAX_JOBS_PER_SITE


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://internshala.com/",
}


def scrape_internshala(role: str, location: str = "") -> list:
    """
    Scrape job/internship listings from Internshala.

    Args:
        role:     Role to search for (e.g. "machine learning", "data analyst")
        location: Optional city filter

    Returns:
        List of job dicts
    """
    role_slug = role.lower().strip().replace(" ", "-")
    url = f"https://internshala.com/jobs/{role_slug}-jobs"
    print(f"  [Internshala] Searching: {url}")

    delay = random.uniform(SCRAPE_DELAY_MIN, SCRAPE_DELAY_MAX)
    time.sleep(delay)

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("  [Internshala] No internet connection.")
        return _demo_jobs(role, location)
    except Exception as e:
        print(f"  [Internshala] Request failed: {e}")
        return _demo_jobs(role, location)

    soup = BeautifulSoup(response.text, "html.parser")
    jobs = []

    # Internshala job cards
    job_cards = soup.find_all("div", class_=lambda c: c and "job_meta" in c)

    if not job_cards:
        # Try alternate selector
        job_cards = soup.find_all("div", class_=lambda c: c and "individual_internship" in c)

    if not job_cards:
        print("  [Internshala] No cards found. Using demo data.")
        return _demo_jobs(role, location)

    print(f"  [Internshala] Found {len(job_cards)} listings")

    for card in job_cards[:MAX_JOBS_PER_SITE]:
        try:
            title_el   = card.find("h3") or card.find("a", class_=lambda c: c and "job-title" in c)
            company_el = card.find("h4") or card.find("p", class_=lambda c: c and "company" in c)
            loc_el     = card.find("div", class_=lambda c: c and "location" in c)
            sal_el     = card.find("div", class_=lambda c: c and "stipend" in c)

            title   = title_el.get_text(strip=True)   if title_el   else "Unknown Title"
            company = company_el.get_text(strip=True) if company_el else "Unknown Company"
            loc     = loc_el.get_text(strip=True)     if loc_el     else location
            salary  = sal_el.get_text(strip=True)     if sal_el     else "Not disclosed"

            # Get the job link
            link_el = card.find("a", href=True)
            link = "https://internshala.com" + link_el["href"] if link_el else url

            jobs.append({
                "title":      title,
                "company":    company,
                "location":   loc,
                "skills":     "",        # Internshala doesn't always show skills on listing page
                "experience": "Fresher/Intern",
                "salary":     salary,
                "link":       link,
                "source":     "internshala",
            })

        except Exception as e:
            print(f"  [Internshala] Error parsing card: {e}")
            continue

    print(f"  [Internshala] Parsed {len(jobs)} jobs")
    return jobs


def _demo_jobs(role: str, location: str) -> list:
    """Demo data fallback."""
    return [
        {
            "title":      f"{role} Intern",
            "company":    "StartupXYZ",
            "location":   "Work From Home",
            "skills":     "Python, Machine Learning, NumPy",
            "experience": "Fresher",
            "salary":     "10,000/month",
            "link":       "https://internshala.com/",
            "source":     "internshala_demo",
        },
        {
            "title":      f"Junior {role}",
            "company":    "DataCorp India",
            "location":   location or "Bangalore",
            "skills":     "Python, SQL, Tableau",
            "experience": "0-1 years",
            "salary":     "15,000/month",
            "link":       "https://internshala.com/",
            "source":     "internshala_demo",
        },
        {
            "title":      f"{role} Trainee",
            "company":    "Analytics India Pvt Ltd",
            "location":   location or "Pune",
            "skills":     "Python, Excel, Power BI",
            "experience": "Fresher",
            "salary":     "12,000/month",
            "link":       "https://internshala.com/",
            "source":     "internshala_demo",
        },
    ]


# ── Run directly to test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nTesting Internshala scraper...")

    jobs = scrape_internshala("machine learning", "Pune")

    print(f"\nTotal jobs found: {len(jobs)}")
    for i, job in enumerate(jobs[:3], 1):
        print(f"\n--- Job {i} ---")
        print(f"  Title   : {job['title']}")
        print(f"  Company : {job['company']}")
        print(f"  Salary  : {job['salary']}")

    print("\n  [OK] internshala.py working correctly")