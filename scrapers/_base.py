"""
Shared utilities used by every scraper: polite delays, retries, robots.txt
checking, and a common requests session.
"""

import time
import random
import logging
import urllib.robotparser
from functools import lru_cache

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (
    HEADERS,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
    MAX_RETRIES,
    BACKOFF_FACTOR,
)

logger = logging.getLogger(__name__)


def build_session() -> requests.Session:
    """Return a requests.Session with automatic retry + backoff."""
    session = requests.Session()
    session.headers.update(HEADERS)

    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def polite_delay() -> None:
    """Sleep for a random interval between configured min/max seconds."""
    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
    time.sleep(delay)


@lru_cache(maxsize=32)
def _fetch_robots(base_url: str) -> urllib.robotparser.RobotFileParser:
    """Download and cache the robots.txt for a given base URL."""
    rp = urllib.robotparser.RobotFileParser()
    robots_url = f"{base_url.rstrip('/')}/robots.txt"
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        logger.warning("Could not fetch robots.txt from %s: %s", robots_url, exc)
    return rp


def is_allowed(url: str, base_url: str) -> bool:
    """Check whether our user-agent is allowed to fetch *url* per robots.txt."""
    rp = _fetch_robots(base_url)
    allowed = rp.can_fetch(HEADERS["User-Agent"], url)
    if not allowed:
        logger.info("Blocked by robots.txt: %s", url)
    return allowed


def safe_get(session: requests.Session, url: str, base_url: str,
             timeout: int = 30) -> requests.Response | None:
    """GET a URL with robots.txt check, polite delay, and error handling."""
    if not is_allowed(url, base_url):
        return None
    polite_delay()
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        logger.warning("Request failed for %s: %s", url, exc)
        return None


def make_post(*, job_title: str, company: str, location: str,
              date_posted: str, deadline: str, job_url: str,
              salary: str, description: str, source: str) -> dict:
    """Build a standardised raw-post dict."""
    return {
        "job_title": job_title.strip() if job_title else "",
        "company": company.strip() if company else "",
        "location": location.strip() if location else "",
        "date_posted": date_posted.strip() if date_posted else "",
        "deadline": deadline.strip() if deadline else "",
        "job_url": job_url.strip() if job_url else "",
        "salary": salary.strip() if salary else "",
        "description": description.strip() if description else "",
        "source": source,
    }
