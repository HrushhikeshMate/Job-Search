"""
Orchestrates fetching from all scrapers with per-scraper error isolation.
"""

import logging
from scrapers import ALL_SCRAPERS

logger = logging.getLogger(__name__)


def fetch_all_jobs() -> tuple[list[dict], list[str]]:
    """
    Run every registered scraper. If one fails, log the error and
    continue with the others.

    Returns:
        (all_posts, failed_scrapers)
    """
    all_posts: list[dict] = []
    failed_scrapers: list[str] = []

    for name, scrape_fn in ALL_SCRAPERS.items():
        try:
            logger.info("Running scraper: %s", name)
            posts = scrape_fn()
            logger.info("  → %s returned %d posts", name, len(posts))
            all_posts.extend(posts)
        except Exception as exc:
            logger.error("Scraper '%s' failed: %s", name, exc, exc_info=True)
            failed_scrapers.append(name)

    return all_posts, failed_scrapers
