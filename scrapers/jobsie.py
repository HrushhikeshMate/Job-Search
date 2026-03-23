"""
Scraper for Jobs.ie.

Jobs.ie is another major Irish job board with server-rendered search
results.
"""

import logging
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import JOB_TITLES, LOCATION_PRIORITY
from scrapers._base import build_session, safe_get, make_post, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://www.jobs.ie"
SOURCE = "Jobs.ie"


def _search_url(query: str, page: int = 1) -> str:
    """Build a Jobs.ie search URL."""
    q = quote_plus(query)
    return f"{BASE_URL}/jobs?query={q}&location={quote_plus(LOCATION_PRIORITY)}&page={page}"


def _parse_card(card, session) -> dict | None:
    """Extract fields from a Jobs.ie job card."""
    try:
        # Title & URL
        title_el = card.select_one("h2 a, .job-title a, a[class*='title']")
        if not title_el:
            return None
        job_title = title_el.get_text(strip=True)
        job_url = urljoin(BASE_URL, title_el.get("href", ""))

        # Company
        company_el = card.select_one(".company, .job-company, [class*='company']")
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = card.select_one(".location, .job-location, [class*='location']")
        location = location_el.get_text(strip=True) if location_el else ""

        # Date
        date_el = card.select_one(".date, time, [class*='date']")
        date_posted = ""
        if date_el:
            date_posted = date_el.get("datetime", "") or date_el.get_text(strip=True)

        # Salary
        salary_el = card.select_one(".salary, [class*='salary']")
        salary = salary_el.get_text(strip=True) if salary_el else ""

        # Fetch full description
        description = ""
        deadline = ""
        if job_url:
            detail_resp = safe_get(session, job_url, BASE_URL)
            if detail_resp:
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                desc_el = detail_soup.select_one(
                    ".job-description, [class*='description'], article, "
                    ".job-detail-content"
                )
                if desc_el:
                    description = desc_el.get_text(separator="\n", strip=True)

                if not salary:
                    sal_el = detail_soup.select_one("[class*='salary']")
                    if sal_el:
                        salary = sal_el.get_text(strip=True)

                dl_el = detail_soup.select_one(
                    ".closing-date, [class*='deadline'], [class*='closing']"
                )
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
        logger.warning("Failed to parse Jobs.ie card: %s", exc)
        return None


def scrape() -> list[dict]:
    """Scrape Jobs.ie for all configured job titles."""
    session = build_session()
    results: list[dict] = []

    for title in JOB_TITLES:
        logger.info("Jobs.ie: searching for '%s'", title)
        for page in range(1, 4):
            url = _search_url(title, page)
            resp = safe_get(session, url, BASE_URL)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(
                ".job-result, .job-listing, .search-result, "
                "[class*='job-card'], li[class*='result']"
            )
            if not cards:
                break

            for card in cards:
                post = _parse_card(card, session)
                if post and post["job_url"]:
                    results.append(post)

            polite_delay()

    logger.info("Jobs.ie: found %d listings", len(results))
    return results
