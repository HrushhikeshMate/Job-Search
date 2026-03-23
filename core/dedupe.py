"""
Deduplication module — removes duplicate job listings.
"""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _normalise_url(url: str) -> str:
    """
    Normalise a URL for dedup comparison.

    Strips query params, trailing slashes, and lowercases the domain
    so that the same listing from different referral links is caught.
    """
    parsed = urlparse(url)
    # Keep scheme + netloc + path, drop query/fragment
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}".lower()


def _role_key(post: dict) -> str:
    """
    Generate a composite key based on job title + company to catch
    the same role posted on multiple platforms.
    """
    title = post.get("job_title", "").lower().strip()
    company = post.get("company", "").lower().strip()
    return f"{title}||{company}"


def dedupe(posts: list[dict]) -> list[dict]:
    """
    Deduplicate a list of normalised posts.

    Rules:
      1. Unique by job URL (after normalisation).
      2. If the same role (title + company) appears from multiple
         platforms, keep the first one encountered and log the
         duplicate source platforms in a hidden field.

    Returns:
        List of unique posts with an added ``duplicate_sources`` field.
    """
    seen_urls: set[str] = set()
    seen_roles: dict[str, int] = {}  # role_key -> index in result list
    result: list[dict] = []
    duplicates_skipped = 0

    for post in posts:
        url_key = _normalise_url(post.get("job_url", ""))

        # --- URL-level dedup ---
        if url_key in seen_urls:
            duplicates_skipped += 1
            continue
        seen_urls.add(url_key)

        # --- Role-level dedup (same title+company across platforms) ---
        rk = _role_key(post)
        if rk in seen_roles:
            idx = seen_roles[rk]
            # Append this platform to the first instance's duplicate list
            existing = result[idx]
            existing.setdefault("duplicate_sources", [])
            existing["duplicate_sources"].append(post.get("source", ""))
            duplicates_skipped += 1
            continue

        # New unique post
        post["duplicate_sources"] = []
        result.append(post)
        seen_roles[rk] = len(result) - 1

    logger.info(
        "Dedup: %d input → %d unique (%d duplicates removed)",
        len(posts), len(result), duplicates_skipped,
    )
    return result
