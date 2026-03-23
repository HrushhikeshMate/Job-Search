"""
Configuration settings for the Job Search Pipeline.
All search parameters, filters, and environment variables are defined here.
"""

import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Job Search Parameters
# ---------------------------------------------------------------------------

JOB_TITLES = [
    "Data Analyst",
    "Junior Data Analyst",
    "Business Analyst",
    "Reporting Analyst",
    "BI Analyst",
    "Data Operations Analyst",
]

LOCATION = "Ireland"
LOCATION_PRIORITY = "Dublin"
LOCATION_KEYWORDS_REMOTE = ["remote", "work from home", "wfh", "fully remote"]
LOCATION_KEYWORDS_HYBRID = ["hybrid", "flexible working", "partial remote"]

SENIORITY_INCLUDE = ["entry level", "entry-level", "graduate", "junior", "0-2 years",
                      "0–2 years", "no experience required", "new grad", "intern"]
SENIORITY_EXCLUDE_YEARS = 3  # Exclude roles explicitly requiring 3+ years

# ---------------------------------------------------------------------------
# Skill & Flag Keywords
# ---------------------------------------------------------------------------

SKILLS_TO_FLAG = ["SQL", "Python", "Power BI", "Tableau"]

GDPR_KEYWORDS = ["GDPR", "Data Protection", "DPC", "DSAR", "data privacy"]

# ---------------------------------------------------------------------------
# Time Windows
# ---------------------------------------------------------------------------

NEW_POSTING_WINDOW_DAYS = 3
FOLLOW_UP_WINDOW_DAYS = 7

# ---------------------------------------------------------------------------
# Priority Score Weights (total max = 10)
# ---------------------------------------------------------------------------

SCORE_SKILLS_MATCH = 4
SCORE_NEW_POSTING = 3
SCORE_SALARY_LISTED = 2
SCORE_GDPR_FLAG = 1

# ---------------------------------------------------------------------------
# Scraper Settings
# ---------------------------------------------------------------------------

REQUEST_DELAY_MIN = 2  # seconds
REQUEST_DELAY_MAX = 4  # seconds
MAX_RETRIES = 3
BACKOFF_FACTOR = 2  # exponential backoff multiplier

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-IE,en;q=0.9",
}

# ---------------------------------------------------------------------------
# Google Sheets
# ---------------------------------------------------------------------------

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# Service account credentials (base64-encoded JSON)
_creds_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
GOOGLE_CREDENTIALS = {}
if _creds_b64:
    try:
        GOOGLE_CREDENTIALS = json.loads(base64.b64decode(_creds_b64))
    except Exception:
        pass  # Will be caught at runtime when sheet module initialises

SHEET_NAME = "Job Tracker"  # Worksheet / tab name inside the spreadsheet

# Column order (1-indexed) — DO NOT change without updating sheet.py
SHEET_COLUMNS = [
    "Job Title",            # A  (1)
    "Company",              # B  (2)
    "Location",             # C  (3)
    "Date Posted",          # D  (4)
    "Application Deadline", # E  (5)
    "Job URL",              # F  (6)
    "Source Platform",      # G  (7)
    "Required Skills",      # H  (8)
    "Salary",               # I  (9)
    "Skills Match",         # J  (10)
    "New Posting",          # K  (11)
    "GDPR Relevant",        # L  (12)
    "Priority Score",       # M  (13)
    "Application Status",   # N  (14)  — manual
    "Date Applied",         # O  (15)  — manual
    "CV Tailored?",         # P  (16)  — manual
    "Cover Letter?",        # Q  (17)  — manual
    "Interview Date",       # R  (18)  — manual
    "Recruiter Name",       # S  (19)  — manual
    "Follow-up Due",        # T  (20)  — auto formula
    "Shortlisted",          # U  (21)  — manual
    "Notes",                # V  (22)  — manual
]

AUTO_COLUMNS_COUNT = 13   # Columns 1–13 are auto-populated
MANUAL_COLUMNS_START = 14  # Columns 14–22 are manual / formula

# Default values for new rows
DEFAULT_APPLICATION_STATUS = "Not Applied"

# Application Status dropdown options
APPLICATION_STATUS_OPTIONS = [
    "Not Applied",
    "Applied",
    "Interview",
    "Offer",
    "Rejected",
]

# ---------------------------------------------------------------------------
# Email Notifications
# ---------------------------------------------------------------------------

NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
