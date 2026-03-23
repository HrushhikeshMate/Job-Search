"""
Flagging and scoring module.

Adds boolean flags (Skills Match, New Posting, GDPR Relevant) and
computes a priority score for each post.
"""

import re
import logging
from datetime import datetime, timedelta

from config.settings import (
    SKILLS_TO_FLAG,
    GDPR_KEYWORDS,
    NEW_POSTING_WINDOW_DAYS,
    SCORE_SKILLS_MATCH,
    SCORE_NEW_POSTING,
    SCORE_SALARY_LISTED,
    SCORE_GDPR_FLAG,
    SENIORITY_EXCLUDE_YEARS,
)

logger = logging.getLogger(__name__)

# Pre-compiled regex for experience filtering
_EXPERIENCE_RE = re.compile(
    r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
    re.IGNORECASE,
)


def _text_for_matching(post: dict) -> str:
    """Combine description + title for keyword matching."""
    return f"{post.get('description', '')} {post.get('job_title', '')}".lower()


def flag_skills_match(post: dict) -> str:
    """Return 'YES' if any target skill appears in the description."""
    text = _text_for_matching(post)
    for skill in SKILLS_TO_FLAG:
        if skill.lower() in text:
            return "YES"
    return "NO"


def extract_matched_skills(post: dict) -> str:
    """Return comma-separated list of matched skills."""
    text = _text_for_matching(post)
    matched = [s for s in SKILLS_TO_FLAG if s.lower() in text]
    return ", ".join(matched) if matched else ""


def flag_new_posting(post: dict) -> str:
    """Return 'YES' if the post date is within the new-posting window."""
    date_str = post.get("date_posted", "")
    if not date_str:
        return "NO"

    try:
        posted = datetime.strptime(date_str, "%d/%m/%Y")
        cutoff = datetime.now() - timedelta(days=NEW_POSTING_WINDOW_DAYS)
        return "YES" if posted >= cutoff else "NO"
    except ValueError:
        return "NO"


def flag_gdpr(post: dict) -> str:
    """Return 'YES' if any GDPR keyword appears in the description."""
    text = _text_for_matching(post)
    for keyword in GDPR_KEYWORDS:
        if keyword.lower() in text:
            return "YES"
    return "NO"


def calculate_priority_score(post: dict) -> int:
    """
    Score a post out of 10:
        Skills Match YES = +4
        New Posting YES  = +3
        Salary listed    = +2
        GDPR flag YES    = +1
    """
    score = 0

    if post.get("skills_match") == "YES":
        score += SCORE_SKILLS_MATCH
    if post.get("new_posting") == "YES":
        score += SCORE_NEW_POSTING
    if post.get("salary", "").strip():
        score += SCORE_SALARY_LISTED
    if post.get("gdpr_relevant") == "YES":
        score += SCORE_GDPR_FLAG

    return min(score, 10)


def should_exclude_by_experience(post: dict) -> bool:
    """
    Return True if the posting explicitly requires more years of
    experience than the seniority threshold.
    """
    text = post.get("description", "")
    for match in _EXPERIENCE_RE.finditer(text):
        years = int(match.group(1))
        if years >= SENIORITY_EXCLUDE_YEARS:
            return True
    return False


def apply_all_flags(post: dict) -> dict:
    """
    Enrich a normalised post with all flags, matched skills, and
    priority score.  Returns a new dict (original is not mutated).
    """
    enriched = dict(post)
    enriched["required_skills"] = extract_matched_skills(post)
    enriched["skills_match"] = flag_skills_match(post)
    enriched["new_posting"] = flag_new_posting(post)
    enriched["gdpr_relevant"] = flag_gdpr(post)
    enriched["priority_score"] = calculate_priority_score(enriched)
    return enriched
