"""
Normalisation module — cleans and standardises raw scraper output.
"""

import re
import logging
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from config.settings import LOCATION_KEYWORDS_REMOTE, LOCATION_KEYWORDS_HYBRID

logger = logging.getLogger(__name__)

# Regex for "N days ago" style relative dates
_RELATIVE_DATE_RE = re.compile(
    r"(\d+)\s*(day|days|hour|hours|minute|minutes|week|weeks)\s*ago",
    re.IGNORECASE,
)

# Common date formats found on Irish job boards
_DATE_FORMATS = [
    "%Y-%m-%d",          # 2026-03-20
    "%d/%m/%Y",          # 20/03/2026
    "%d-%m-%Y",          # 20-03-2026
    "%d %b %Y",          # 20 Mar 2026
    "%d %B %Y",          # 20 March 2026
    "%B %d, %Y",         # March 20, 2026
    "%b %d, %Y",         # Mar 20, 2026
    "%Y-%m-%dT%H:%M:%S", # ISO with time
]


def _strip_html(text: str) -> str:
    """Remove any residual HTML tags and collapse whitespace."""
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "html.parser").get_text(separator="\n")
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _standardise_title(title: str) -> str:
    """Apply title-case capitalisation, cleaning common quirks."""
    # Remove extra whitespace
    title = " ".join(title.split())
    # Title-case but preserve known acronyms
    words = title.title().split()
    acronyms = {"Bi", "Sql", "Dpc", "Gdpr", "It", "Hr", "Uk", "Eu"}
    words = [w.upper() if w in acronyms else w for w in words]
    return " ".join(words)


def _parse_date(raw_date: str) -> str:
    """
    Convert a raw date string to DD/MM/YYYY.

    Handles:
      - ISO / common date formats
      - Relative dates ("3 days ago", "1 week ago")
      - Returns empty string if unparseable
    """
    if not raw_date:
        return ""

    raw = raw_date.strip()

    # Check relative dates first
    match = _RELATIVE_DATE_RE.search(raw)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        now = datetime.now()
        if "hour" in unit or "minute" in unit:
            target = now  # Posted today
        elif "week" in unit:
            target = now - timedelta(weeks=amount)
        else:
            target = now - timedelta(days=amount)
        return target.strftime("%d/%m/%Y")

    # "today" / "just posted"
    if any(kw in raw.lower() for kw in ["today", "just posted", "just now"]):
        return datetime.now().strftime("%d/%m/%Y")

    # "yesterday"
    if "yesterday" in raw.lower():
        return (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")

    # Try known formats
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw[:len(datetime.now().strftime(fmt))], fmt)
            return dt.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            continue

    logger.debug("Could not parse date: '%s'", raw_date)
    return raw  # Return as-is if unparseable


def _classify_location(location: str, description: str) -> str:
    """
    Return 'Remote', 'Hybrid', or 'Onsite' based on location field
    and description keywords.
    """
    combined = f"{location} {description}".lower()

    if any(kw in combined for kw in LOCATION_KEYWORDS_REMOTE):
        return "Remote"
    if any(kw in combined for kw in LOCATION_KEYWORDS_HYBRID):
        return "Hybrid"
    return "Onsite"


def normalize_post(raw: dict) -> dict:
    """
    Take a raw post dict from a scraper and return a cleaned version.

    Standardises title, location type, date format, and strips HTML
    from description text.
    """
    description_clean = _strip_html(raw.get("description", ""))

    return {
        "job_title": _standardise_title(raw.get("job_title", "")),
        "company": raw.get("company", "").strip(),
        "location": _classify_location(
            raw.get("location", ""), description_clean
        ),
        "date_posted": _parse_date(raw.get("date_posted", "")),
        "deadline": _parse_date(raw.get("deadline", "")),
        "job_url": raw.get("job_url", "").strip(),
        "salary": raw.get("salary", "").strip(),
        "description": description_clean,
        "source": raw.get("source", ""),
    }
