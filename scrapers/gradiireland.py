"""
Scraper for GradIreland (gradireland.com).

GradIreland focuses on graduate and entry-level roles in Ireland —
an ideal source for the target seniority level.
"""

import logging
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import JOB_TITLES
from scrapers._base import build_session, safe_get, make_post, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://gradireland.com"
SOURCE = "GradIreland"


def _search_url(query: str, page: int = 1) -> str:
    """Build a GradIreland search URL."""
    q = quote_plus(query)
    return f"{BASE_URL}/jobs?query={q}&page={page}"


def _parse_card(card, session) -> dict | None:
    """Extract fields from a GradIreland job card."""
    try:
        # Title & URL
        title_el = card.select_one("h3 a, .job-title a, a.job-card__title")
        if not title_el:
            return None
        job_title = title_el.get_text(strip=True)
        job_url = urljoin(BASE_URL, title_el.get("href", ""))

        # Company
        company_el = card.select_one(".job-card__company, .company-name")
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = card.select_one(".job-card__location, .location")
        location = location_el.get_text(strip=True) if location_el else ""

        # Date posted
        date_el = card.select_one(".job-card__date, .date-posted, time")
        date_posted = ""
        if date_el:
            date_posted = date_el.get("datetime", "") or date_el.get_text(strip=True)

        # Deadline
        deadline_el = card.select_one(".job-card__deadline, .closing-date")
        deadline = deadline_el.get_text(strip=True) if deadline_el else ""

        # Fetch full description
        description = ""
        salary = ""
        if job_url:
            detail_resp = safe_get(session, job_url, BASE_URL)
            if detail_resp:
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                desc_el = detail_soup.select_one(
                    ".job-description, .job-detail__description, article"
                )
                if desc_el:
                    description = desc_el.get_text(separator="\n", strip=True)

                salary_el = detail_soup.select_one(".job-detail__salary, .salary")
                if salary_el:
                    salary = salary_el.get_text(strip=True)

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
        logger.warning("Failed to parse GradIreland card: %s", exc)
        return None


def scrape() -> list[dict]:
    """Scrape GradIreland for all configured job titles."""
    session = build_session()
    results: list[dict] = []

    for title in JOB_TITLES:
        logger.info("GradIreland: searching for '%s'", title)
        for page in range(1, 4):
            url = _search_url(title, page)
            resp = safe_get(session, url, BASE_URL)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".job-card, .job-listing, .search-result")
            if not cards:
                break

            for card in cards:
                post = _parse_card(card, session)
                if post and post["job_url"]:
                    results.append(post)

            polite_delay()

    logger.info("GradIreland: found %d listings", len(results))
    return results
