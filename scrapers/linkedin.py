"""
Scraper for LinkedIn public job listings.

Uses LinkedIn's guest/public job search endpoint which does not require
authentication. Results are limited compared to a logged-in session but
sufficient for daily monitoring.
"""

import logging
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import JOB_TITLES, LOCATION
from scrapers._base import build_session, safe_get, make_post, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://www.linkedin.com"
SEARCH_BASE = "https://www.linkedin.com/jobs/search"
SOURCE = "LinkedIn"


def _search_url(query: str, start: int = 0) -> str:
    """Build a LinkedIn public job search URL."""
    q = quote_plus(query)
    loc = quote_plus(f"{LOCATION}")
    return (
        f"{SEARCH_BASE}?keywords={q}&location={loc}"
        f"&f_TPR=r86400&f_E=2&sortBy=DD&start={start}"
        # f_TPR=r86400 → past 24 hours; f_E=2 → entry level
    )


def _parse_card(card, session) -> dict | None:
    """Extract fields from a single LinkedIn job card."""
    try:
        # Job title & URL
        title_link = card.select_one("h3.base-search-card__title, .base-card__full-link")
        if not title_link:
            return None
        job_title = title_link.get_text(strip=True)

        link_el = card.select_one("a.base-card__full-link")
        job_url = link_el["href"].split("?")[0] if link_el and link_el.get("href") else ""

        # Company
        company_el = card.select_one("h4.base-search-card__subtitle, .base-search-card__subtitle")
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = card.select_one(".job-search-card__location")
        location = location_el.get_text(strip=True) if location_el else ""

        # Date
        time_el = card.select_one("time")
        date_posted = time_el.get("datetime", "") if time_el else ""

        # Salary (rarely shown on public listings)
        salary_el = card.select_one(".job-search-card__salary-info")
        salary = salary_el.get_text(strip=True) if salary_el else ""

        # Fetch full description
        description = ""
        if job_url:
            detail_resp = safe_get(session, job_url, BASE_URL)
            if detail_resp:
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                desc_el = detail_soup.select_one(
                    ".description__text, .show-more-less-html__markup"
                )
                if desc_el:
                    description = desc_el.get_text(separator="\n", strip=True)

        return make_post(
            job_title=job_title,
            company=company,
            location=location,
            date_posted=date_posted,
            deadline="",
            job_url=job_url,
            salary=salary,
            description=description,
            source=SOURCE,
        )
    except Exception as exc:
        logger.warning("Failed to parse LinkedIn card: %s", exc)
        return None


def scrape() -> list[dict]:
    """Scrape LinkedIn public job listings for all configured titles."""
    session = build_session()
    results: list[dict] = []

    for title in JOB_TITLES:
        logger.info("LinkedIn: searching for '%s'", title)
        for page in range(3):
            start = page * 25
            url = _search_url(title, start)
            resp = safe_get(session, url, BASE_URL)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".base-card, .job-search-card")
            if not cards:
                break

            for card in cards:
                post = _parse_card(card, session)
                if post and post["job_url"]:
                    results.append(post)

            polite_delay()

    logger.info("LinkedIn: found %d listings", len(results))
    return results
