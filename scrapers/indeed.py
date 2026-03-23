"""
Scraper for Indeed Ireland (ie.indeed.com).

Indeed's search results page is parsed for job cards. Each card links to
a detail page from which the full description is extracted.
"""

import logging
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from config.settings import JOB_TITLES, LOCATION
from scrapers._base import build_session, safe_get, make_post, polite_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://ie.indeed.com"
SOURCE = "Indeed"


def _search_url(query: str, start: int = 0) -> str:
    """Build an Indeed search URL for Ireland."""
    q = quote_plus(query)
    return f"{BASE_URL}/jobs?q={q}&l={quote_plus(LOCATION)}&sort=date&start={start}"


def _parse_listing(card, session) -> dict | None:
    """Extract fields from a single Indeed job card."""
    try:
        # Job title
        title_el = card.select_one("h2.jobTitle a, h2.jobTitle span")
        if not title_el:
            return None
        job_title = title_el.get_text(strip=True)

        # Job URL
        link_el = card.select_one("h2.jobTitle a")
        job_url = urljoin(BASE_URL, link_el["href"]) if link_el and link_el.get("href") else ""

        # Company
        company_el = card.select_one("[data-testid='company-name'], .companyName")
        company = company_el.get_text(strip=True) if company_el else ""

        # Location
        location_el = card.select_one("[data-testid='text-location'], .companyLocation")
        location = location_el.get_text(strip=True) if location_el else ""

        # Date posted (relative, e.g. "3 days ago")
        date_el = card.select_one(".date, [data-testid='myJobsStateDate']")
        date_posted = date_el.get_text(strip=True) if date_el else ""

        # Salary
        salary_el = card.select_one(".salary-snippet-container, [data-testid='attribute_snippet_testid']")
        salary = salary_el.get_text(strip=True) if salary_el else ""

        # Fetch full description from detail page
        description = ""
        if job_url:
            detail_resp = safe_get(session, job_url, BASE_URL)
            if detail_resp:
                detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                desc_el = detail_soup.select_one("#jobDescriptionText, .jobsearch-jobDescriptionText")
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
        logger.warning("Failed to parse Indeed card: %s", exc)
        return None


def scrape() -> list[dict]:
    """Scrape Indeed Ireland for all configured job titles."""
    session = build_session()
    results: list[dict] = []

    for title in JOB_TITLES:
        logger.info("Indeed: searching for '%s'", title)
        # Paginate through first 3 pages (30 results per page)
        for page in range(3):
            start = page * 10
            url = _search_url(title, start)
            resp = safe_get(session, url, BASE_URL)
            if not resp:
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".job_seen_beacon, .jobsearch-ResultsList > li")
            if not cards:
                break

            for card in cards:
                post = _parse_listing(card, session)
                if post and post["job_url"]:
                    results.append(post)

            polite_delay()

    logger.info("Indeed: found %d listings", len(results))
    return results
