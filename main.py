#!/usr/bin/env python3
"""
Job Search Pipeline — Main Orchestrator

Runs all scrapers, normalises and deduplicates results, applies flags
and scoring, appends new rows to Google Sheets, and sends a daily
summary notification email.
"""

import logging
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import (
    NOTIFICATION_EMAIL,
    SMTP_USER,
    SMTP_PASSWORD,
    SMTP_HOST,
    SMTP_PORT,
    LOG_LEVEL,
)
from core.fetch_jobs import fetch_all_jobs
from core.normalize import normalize_post
from core.dedupe import dedupe
from core.flags import apply_all_flags, should_exclude_by_experience
from core.sheet import append_jobs, setup_sheet_formatting

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Email Notification
# ---------------------------------------------------------------------------

def send_summary_email(
    new_count: int,
    skills_match_count: int,
    top_roles: list[dict],
    total_found: int,
    duplicates_skipped: int,
    failed_scrapers: list[str],
) -> None:
    """Send a daily summary email via Gmail SMTP."""
    if not all([NOTIFICATION_EMAIL, SMTP_USER, SMTP_PASSWORD]):
        logger.warning("Email credentials not configured — skipping notification.")
        return

    today = datetime.now().strftime("%d/%m/%Y")
    subject = f"Job Pipeline Summary — {today}"

    # Build plain-text body
    lines = [
        f"Daily Job Search Summary — {today}",
        f"{'=' * 44}",
        "",
        f"Total listings scraped:   {total_found}",
        f"New jobs added to sheet:  {new_count}",
        f"Duplicates skipped:       {duplicates_skipped}",
        f"Skills Match = YES:       {skills_match_count}",
        "",
    ]

    if failed_scrapers:
        lines.append(f"Failed scrapers: {', '.join(failed_scrapers)}")
        lines.append("")

    if top_roles:
        lines.append("Top 3 Roles by Priority Score:")
        lines.append("-" * 40)
        for i, role in enumerate(top_roles[:3], 1):
            lines.append(
                f"  {i}. {role.get('job_title', 'N/A')} "
                f"@ {role.get('company', 'N/A')}"
            )
            lines.append(f"     {role.get('job_url', '')}")
            lines.append(f"     Score: {role.get('priority_score', 0)}")
            lines.append("")

    body = "\n".join(lines)

    # Build HTML body
    html_rows = ""
    for i, role in enumerate(top_roles[:3], 1):
        html_rows += (
            f"<tr>"
            f"<td>{i}</td>"
            f"<td>{role.get('job_title', 'N/A')}</td>"
            f"<td>{role.get('company', 'N/A')}</td>"
            f"<td><a href=\"{role.get('job_url', '#')}\">"
            f"Apply</a></td>"
            f"<td>{role.get('priority_score', 0)}</td>"
            f"</tr>"
        )

    html = f"""
    <html><body>
    <h2>Daily Job Search Summary — {today}</h2>
    <table border="0" cellpadding="6">
        <tr><td><strong>Total scraped:</strong></td><td>{total_found}</td></tr>
        <tr><td><strong>New jobs added:</strong></td><td>{new_count}</td></tr>
        <tr><td><strong>Duplicates skipped:</strong></td><td>{duplicates_skipped}</td></tr>
        <tr><td><strong>Skills Match YES:</strong></td><td>{skills_match_count}</td></tr>
    </table>
    {"<p style='color:red;'>Failed scrapers: " + ", ".join(failed_scrapers) + "</p>" if failed_scrapers else ""}
    <h3>Top 3 Roles</h3>
    <table border="1" cellpadding="6" cellspacing="0">
        <tr><th>#</th><th>Title</th><th>Company</th><th>Link</th><th>Score</th></tr>
        {html_rows if html_rows else "<tr><td colspan='5'>No new roles today.</td></tr>"}
    </table>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFICATION_EMAIL
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, NOTIFICATION_EMAIL, msg.as_string())
        logger.info("Summary email sent to %s", NOTIFICATION_EMAIL)
    except Exception as exc:
        logger.error("Failed to send summary email: %s", exc)


def send_failure_email(error_msg: str) -> None:
    """Send a failure alert email."""
    if not all([NOTIFICATION_EMAIL, SMTP_USER, SMTP_PASSWORD]):
        return

    today = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEText(
        f"The job search pipeline failed on {today}.\n\n"
        f"Error:\n{error_msg}\n\n"
        f"Check the GitHub Actions log for details."
    )
    msg["Subject"] = f"[ALERT] Job Pipeline Failed — {today}"
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFICATION_EMAIL

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, NOTIFICATION_EMAIL, msg.as_string())
    except Exception:
        pass  # Can't do much if the failure email also fails


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """Execute the full job search pipeline end-to-end."""
    logger.info("=" * 60)
    logger.info("Starting Job Search Pipeline")
    logger.info("=" * 60)

    # ---- Step 1: Fetch from all scrapers ----
    raw_posts, failed_scrapers = fetch_all_jobs()
    total_found = len(raw_posts)
    logger.info("Total raw listings fetched: %d", total_found)

    if failed_scrapers:
        logger.warning("Failed scrapers: %s", ", ".join(failed_scrapers))

    if not raw_posts:
        logger.warning("No posts fetched from any scraper.")
        send_summary_email(0, 0, [], 0, 0, failed_scrapers)
        return

    # ---- Step 2: Normalise ----
    normalised = [normalize_post(p) for p in raw_posts]
    logger.info("Normalised %d posts.", len(normalised))

    # ---- Step 3: Deduplicate ----
    unique = dedupe(normalised)
    duplicates_skipped = total_found - len(unique)
    logger.info("After dedup: %d unique posts.", len(unique))

    # ---- Step 4: Apply flags, scores, and experience filter ----
    enriched = [apply_all_flags(p) for p in unique]

    # Filter out roles requiring too much experience
    before_filter = len(enriched)
    enriched = [p for p in enriched if not should_exclude_by_experience(p)]
    filtered_out = before_filter - len(enriched)
    if filtered_out:
        logger.info("Excluded %d posts requiring 3+ years experience.", filtered_out)

    # ---- Step 5: Sort by priority score descending ----
    enriched.sort(key=lambda p: p.get("priority_score", 0), reverse=True)

    skills_match_count = sum(1 for p in enriched if p.get("skills_match") == "YES")
    top_roles = enriched[:3]

    # ---- Step 6: Append to Google Sheet ----
    new_count = 0
    try:
        new_count = append_jobs(enriched)
        logger.info("Appended %d new rows to Google Sheet.", new_count)
    except Exception as exc:
        logger.error("Google Sheets append failed: %s", exc, exc_info=True)

    # ---- Step 7: Apply formatting (idempotent) ----
    try:
        setup_sheet_formatting()
    except Exception as exc:
        logger.warning("Sheet formatting failed (non-critical): %s", exc)

    # ---- Step 8: Send summary email ----
    send_summary_email(
        new_count=new_count,
        skills_match_count=skills_match_count,
        top_roles=top_roles,
        total_found=total_found,
        duplicates_skipped=duplicates_skipped,
        failed_scrapers=failed_scrapers,
    )

    # ---- Summary log ----
    logger.info("-" * 60)
    logger.info("Pipeline complete.")
    logger.info("  Total scraped:       %d", total_found)
    logger.info("  New jobs added:      %d", new_count)
    logger.info("  Duplicates skipped:  %d", duplicates_skipped)
    logger.info("  Experience-filtered: %d", filtered_out)
    logger.info("  Skills Match YES:    %d", skills_match_count)
    logger.info("  Failed scrapers:     %s", ", ".join(failed_scrapers) or "None")
    logger.info("-" * 60)


if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as exc:
        logger.critical("Pipeline crashed: %s", exc, exc_info=True)
        send_failure_email(str(exc))
        sys.exit(1)
