"""
Scraper for IrishJobs.ie.

IrishJobs is one of the largest Irish job boards and typically serves
results as server-rendered HTML.
"""

import logging
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import JOB_TITLES, LOCATION_PRIORITY
from scrapers._base import build_session, safe_get, make_post, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://www.irishjobs.ie"
SOURCE = "IrishJobs"


def _search_url(query: str, page: int = 1) -> str:
    """Build an IrishJobs search URL."""
    q = quote_plus(query)
    loc = quote_plus(LOCATION_PRIORITY)
    return f"{BASE_URL}/Jobs/{q}?location={loc}&page={page}"


def _parse_card(card, session) -> dict | None:
    """Extract fields from an IrishJobs job card."""
    try:
        # Title & URL
        title_el = card.select_one("h2 a, .job-title a, a.job-result-title")
        if not title_el:
            return None
        job_title = title_el.get_text(strip=True)
        job_url = urljoin(BASE_URL, title_el.get("href", ""))

        # Company
        company_el = card.select_one(".job-company, .company-name, .job-result-company")
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = card.select_one(".job-location, .location, .job-result-location")
        location = location_el.get_text(strip=True) if location_el else ""

        # Date
        date_el = card.select_one(".job-date, .date, time")
        date_posted = ""
        if date_el:
            date_posted = date_el.get("datetime", "") or date_el.get_text(strip=True)

        # Salary snippet (if visible on card)
        salary_el = card.select_one(".job-salary, .salary")
        salary = salary_el.get_text(strip=True) if salary_el else ""

        # Fetch full description
        description = ""
        deadline = ""
        if job_url:
            detail_resp = safe_get(session, job_url, BASE_URL)
            if detail_resp:
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                desc_el = detail_soup.select_one(
                    ".job-description, .job-detail-description, "
                    "[class*='description'], article"
                )
                if desc_el:
                    description = desc_el.get_text(separator="\n", strip=True)

                # Try to pick up salary from detail if not on card
                if not salary:
                    sal_el = detail_soup.select_one(
                        ".job-detail-salary, [class*='salary']"
                    )
                    if sal_el:
                        salary = sal_el.get_text(strip=True)

                # Deadline
                dl_el = detail_soup.select_one(".closing-date, .job-detail-deadline")
                if dl_el:
                    deadline = dl_el.get_text(strip=True)

        return make_post(
            job_title=job_title,
            company=company,
            location=location,
            date_posted=date_posted,
            deadline=deadline,
            job_url=job_url,
            salary=salary,
            description=description,
            source=SOURCE,
        )
    except Exception as exc:
        logger.warning("Failed to parse IrishJobs card: %s", exc)
        return None


def scrape() -> list[dict]:
    """Scrape IrishJobs.ie for all configured job titles."""
    session = build_session()
    results: list[dict] = []

    for title in JOB_TITLES:
        logger.info("IrishJobs: searching for '%s'", title)
        for page in range(1, 4):
            url = _search_url(title, page)
            resp = safe_get(session, url, BASE_URL)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(
                ".job-result, .job-listing, .search-result, "
                "[class*='job-card']"
            )
            if not cards:
                break

            for card in cards:
                post = _parse_card(card, session)
                if post and post["job_url"]:
                    results.append(post)

            polite_delay()

    logger.info("IrishJobs: found %d listings", len(results))
    return results
