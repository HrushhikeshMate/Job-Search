# Automated Job Search Pipeline

An automated daily pipeline that scrapes entry-level Data Analyst roles from five Irish job boards (Indeed, LinkedIn, GradIreland, IrishJobs.ie, Jobs.ie), scores and deduplicates them, and pushes structured results into a Google Sheet you can apply from directly. Runs on GitHub Actions at 7 AM Irish time every morning with zero manual effort after setup.

---

## Setup Checklist

Follow every step below. Total time: ~20 minutes.

### 1. Create a Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or use an existing one).
3. Enable the **Google Sheets API** and **Google Drive API** for the project.
4. Go to **IAM & Admin > Service Accounts** and create a new service account.
5. Click the service account, go to **Keys > Add Key > Create new key > JSON**.
6. Download the JSON key file. Keep it safe — you will need it in step 4.

### 2. Create and Share the Google Sheet

1. Create a new Google Sheet in your Google Drive.
2. Copy the **Sheet ID** from the URL — it is the long string between `/d/` and `/edit`:
   ```
   https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit
   ```
3. Share the sheet with the service account email (found in your JSON key file, field `client_email`) and give it **Editor** access.

### 3. Create a Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security).
2. Enable **2-Step Verification** if not already on.
3. Go to **App passwords** and generate one for "Mail" on "Other (Custom name)".
4. Copy the 16-character password — this is your `SMTP_PASSWORD`.

### 4. Push the Code to GitHub

1. Create a new GitHub repository.
2. Push this entire `job-search-pipeline/` directory to the repo.

### 5. Add GitHub Secrets

Go to **Settings > Secrets and variables > Actions** in your repository and add these five secrets:

| Secret Name              | Value                                                        |
|--------------------------|--------------------------------------------------------------|
| `GOOGLE_SHEET_ID`        | The Sheet ID from step 2                                     |
| `GOOGLE_CREDENTIALS_JSON`| Base64-encoded service account JSON (see below)              |
| `NOTIFICATION_EMAIL`     | Your email address for daily summaries                       |
| `SMTP_USER`              | Your Gmail address (the one with the app password)           |
| `SMTP_PASSWORD`          | The 16-character app password from step 3                    |

**To base64-encode your credentials JSON:**

```bash
# macOS / Linux
base64 -w 0 < your-service-account-key.json

# Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("your-service-account-key.json"))
```

Copy the entire output and paste it as the value for `GOOGLE_CREDENTIALS_JSON`.

### 6. First Run

1. Go to the **Actions** tab in your GitHub repo.
2. Click **Daily Job Search Pipeline** in the left sidebar.
3. Click **Run workflow** to trigger manually.
4. Check your Google Sheet — new rows should appear within a few minutes.
5. Check your email for the daily summary.

---

## Environment Variables Reference

| Variable                  | Where to Set      | Description                                |
|---------------------------|-------------------|--------------------------------------------|
| `GOOGLE_SHEET_ID`         | GitHub Secrets    | Target Google Sheet ID                     |
| `GOOGLE_CREDENTIALS_JSON` | GitHub Secrets    | Base64-encoded service account JSON        |
| `NOTIFICATION_EMAIL`      | GitHub Secrets    | Email for daily summary + failure alerts   |
| `SMTP_USER`               | GitHub Secrets    | Gmail address for sending emails           |
| `SMTP_PASSWORD`           | GitHub Secrets    | Gmail app password                         |
| `LOG_LEVEL`               | Optional (env)    | Python log level, default `INFO`           |

---

## How To...

### Add a new job board scraper

1. Create a new file in `scrapers/`, e.g. `scrapers/newboard.py`.
2. Implement a `scrape() -> list[dict]` function that returns dicts with these keys:
   `job_title`, `company`, `location`, `date_posted`, `deadline`, `job_url`, `salary`, `description`, `source`.
3. Use the helpers from `scrapers/_base.py` (`build_session`, `safe_get`, `make_post`, `polite_delay`).
4. Register it in `scrapers/__init__.py` by adding an import and an entry in `ALL_SCRAPERS`.

### Change the job titles being searched

Edit the `JOB_TITLES` list in `config/settings.py`.

### Change the daily run time

Edit the `cron` expression in `.github/workflows/job_search.yml`. The format is `minute hour * * *` in **UTC**. Ireland is UTC+0 in winter (GMT) and UTC+1 in summer (IST), so adjust accordingly.

### Change the skills being flagged

Edit the `SKILLS_TO_FLAG` list in `config/settings.py`.

### Change the experience filter

Edit `SENIORITY_EXCLUDE_YEARS` in `config/settings.py` (default: 3, meaning roles requiring 3+ years are excluded).

---

## Project Structure

```
job-search-pipeline/
├── scrapers/              # One scraper per job board
│   ├── _base.py           # Shared: sessions, delays, robots.txt, retries
│   ├── indeed.py          # Indeed Ireland
│   ├── linkedin.py        # LinkedIn public listings
│   ├── gradiireland.py    # GradIreland
│   ├── irishjobs.py       # IrishJobs.ie
│   └── jobsie.py          # Jobs.ie
├── core/                  # Processing modules
│   ├── fetch_jobs.py      # Runs all scrapers with error isolation
│   ├── normalize.py       # Cleans titles, dates, locations, HTML
│   ├── dedupe.py          # URL + role-level deduplication
│   ├── flags.py           # Skills, GDPR, recency flags + scoring
│   └── sheet.py           # Google Sheets: auth, append, formatting
├── config/
│   └── settings.py        # All configuration in one place
├── .github/workflows/
│   └── job_search.yml     # Daily GitHub Actions workflow
├── main.py                # Pipeline orchestrator + email notifications
├── requirements.txt       # Pinned dependencies
└── README.md              # This file
```
