"""
Google Sheets integration module.

Handles OAuth2 authentication, batch appending of new rows, duplicate
URL checking, conditional formatting, and data validation setup.
"""

import logging

import gspread
from google.oauth2.service_account import Credentials

from config.settings import (
    GOOGLE_CREDENTIALS,
    GOOGLE_SHEET_ID,
    SHEET_NAME,
    SHEET_COLUMNS,
    AUTO_COLUMNS_COUNT,
    DEFAULT_APPLICATION_STATUS,
    APPLICATION_STATUS_OPTIONS,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client() -> gspread.Client:
    """Authenticate and return a gspread client."""
    if not GOOGLE_CREDENTIALS:
        raise RuntimeError(
            "GOOGLE_CREDENTIALS_JSON environment variable is empty or invalid. "
            "Please set it to a base64-encoded service account JSON."
        )
    creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_worksheet(spreadsheet: gspread.Spreadsheet) -> gspread.Worksheet:
    """Get the target worksheet, creating it (with headers) if needed."""
    try:
        ws = spreadsheet.worksheet(SHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(SHEET_COLUMNS))
        ws.append_row(SHEET_COLUMNS, value_input_option="RAW")
        logger.info("Created new worksheet '%s' with headers.", SHEET_NAME)
    return ws


def _get_existing_urls(ws: gspread.Worksheet) -> set[str]:
    """Return all Job URLs already present in the sheet (column F = index 6)."""
    try:
        url_col = ws.col_values(6)  # Column F = Job URL
        return set(url_col[1:])  # Skip header
    except Exception as exc:
        logger.warning("Could not read existing URLs: %s", exc)
        return set()


def _post_to_row(post: dict, row_number: int) -> list:
    """
    Convert an enriched post dict into a row list matching SHEET_COLUMNS.

    Columns 1–13 are auto-populated. Columns 14–22 get defaults or
    formulas for new rows.
    """
    follow_up_formula = f'=IF(O{row_number}<>"", O{row_number}+7, "")'

    return [
        post.get("job_title", ""),           # A  Job Title
        post.get("company", ""),             # B  Company
        post.get("location", ""),            # C  Location
        post.get("date_posted", ""),         # D  Date Posted
        post.get("deadline", ""),            # E  Application Deadline
        post.get("job_url", ""),             # F  Job URL
        post.get("source", ""),              # G  Source Platform
        post.get("required_skills", ""),     # H  Required Skills
        post.get("salary", ""),              # I  Salary
        post.get("skills_match", ""),        # J  Skills Match
        post.get("new_posting", ""),         # K  New Posting
        post.get("gdpr_relevant", ""),       # L  GDPR Relevant
        post.get("priority_score", 0),       # M  Priority Score
        DEFAULT_APPLICATION_STATUS,          # N  Application Status
        "",                                  # O  Date Applied
        "",                                  # P  CV Tailored?
        "",                                  # Q  Cover Letter?
        "",                                  # R  Interview Date
        "",                                  # S  Recruiter Name
        follow_up_formula,                   # T  Follow-up Due
        "",                                  # U  Shortlisted
        "",                                  # V  Notes
    ]


def append_jobs(posts: list[dict]) -> int:
    """
    Append new jobs to the Google Sheet.

    - Skips any post whose Job URL already exists in the sheet.
    - Sorts new posts by priority score descending before appending.
    - Never overwrites existing manual columns (14–22).

    Returns:
        Number of new rows actually appended.
    """
    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    ws = _get_or_create_worksheet(spreadsheet)

    existing_urls = _get_existing_urls(ws)
    logger.info("Sheet already has %d rows (excluding header).", len(existing_urls))

    # Filter out duplicates
    new_posts = [p for p in posts if p.get("job_url", "") not in existing_urls]
    logger.info("New posts to append: %d (skipped %d duplicates).",
                len(new_posts), len(posts) - len(new_posts))

    if not new_posts:
        return 0

    # Sort by priority score descending
    new_posts.sort(key=lambda p: p.get("priority_score", 0), reverse=True)

    # Calculate starting row number (current last row + 1)
    current_rows = len(ws.get_all_values())
    next_row = current_rows + 1

    # Build all rows
    rows = []
    for i, post in enumerate(new_posts):
        row_num = next_row + i
        rows.append(_post_to_row(post, row_num))

    # Batch append using USER_ENTERED so formulas are evaluated
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    logger.info("Appended %d new rows to sheet.", len(rows))

    return len(rows)


def setup_sheet_formatting() -> None:
    """
    Apply conditional formatting rules, freeze header row, and add
    data validation to the Application Status column.

    Call once during initial setup or idempotently on each run.
    """
    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    ws = _get_or_create_worksheet(spreadsheet)

    sheet_id = ws.id

    # ---------------------------------------------------------------
    # Conditional Formatting Rules
    # ---------------------------------------------------------------
    # Google Sheets API uses 0-indexed columns and RGBA floats 0-1.

    requests_batch = []

    # Helper to build a conditional format rule
    def _bool_rule(formula: str, bg_color: dict, bold: bool = False) -> dict:
        fmt = {"backgroundColor": bg_color}
        if bold:
            fmt["textFormat"] = {"bold": True}
        return {
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": sheet_id,
                        "startRowIndex": 1,  # skip header
                        "startColumnIndex": 0,
                        "endColumnIndex": len(SHEET_COLUMNS),
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": formula}],
                        },
                        "format": fmt,
                    },
                },
                "index": 0,
            }
        }

    # Green: Skills Match=YES AND New Posting=YES
    requests_batch.append(_bool_rule(
        '=AND($J2="YES", $K2="YES")',
        {"red": 0.85, "green": 0.93, "blue": 0.83, "alpha": 1},
    ))

    # Yellow: Application Status = Applied
    requests_batch.append(_bool_rule(
        '=$N2="Applied"',
        {"red": 1.0, "green": 0.95, "blue": 0.6, "alpha": 1},
    ))

    # Blue: Application Status = Interview
    requests_batch.append(_bool_rule(
        '=$N2="Interview"',
        {"red": 0.79, "green": 0.85, "blue": 0.97, "alpha": 1},
    ))

    # Orange: Application Status = Offer
    requests_batch.append(_bool_rule(
        '=$N2="Offer"',
        {"red": 1.0, "green": 0.87, "blue": 0.67, "alpha": 1},
    ))

    # Red: Application Status = Rejected
    requests_batch.append(_bool_rule(
        '=$N2="Rejected"',
        {"red": 0.96, "green": 0.80, "blue": 0.80, "alpha": 1},
    ))

    # Bold + yellow fill on Priority Score cell if score >= 7
    requests_batch.append({
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 12,  # Column M (0-indexed = 12)
                    "endColumnIndex": 13,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "NUMBER_GREATER_THAN_EQ",
                        "values": [{"userEnteredValue": "7"}],
                    },
                    "format": {
                        "backgroundColor": {"red": 1.0, "green": 0.95, "blue": 0.6, "alpha": 1},
                        "textFormat": {"bold": True},
                    },
                },
            },
            "index": 0,
        }
    })

    # ---------------------------------------------------------------
    # Data Validation: Application Status dropdown (Column N = index 13)
    # ---------------------------------------------------------------
    requests_batch.append({
        "setDataValidation": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 1,
                "startColumnIndex": 13,  # Column N
                "endColumnIndex": 14,
            },
            "rule": {
                "condition": {
                    "type": "ONE_OF_LIST",
                    "values": [{"userEnteredValue": opt} for opt in APPLICATION_STATUS_OPTIONS],
                },
                "showCustomUi": True,
                "strict": True,
            },
        }
    })

    # ---------------------------------------------------------------
    # Freeze header row + auto-resize
    # ---------------------------------------------------------------
    requests_batch.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    # Bold header row
    requests_batch.append({
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": len(SHEET_COLUMNS),
            },
            "cell": {
                "userEnteredFormat": {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9, "alpha": 1},
                },
            },
            "fields": "userEnteredFormat(textFormat,backgroundColor)",
        }
    })

    # Execute all in one batch
    try:
        spreadsheet.batch_update({"requests": requests_batch})
        logger.info("Sheet formatting applied successfully.")
    except Exception as exc:
        logger.warning("Could not apply sheet formatting: %s", exc)
