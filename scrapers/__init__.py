"""
Scrapers package — one module per job board.

Every scraper exposes a single public function:

    scrape() -> list[dict]

Each dict has the keys:
    job_title, company, location, date_posted, deadline,
    job_url, salary, description, source
"""

from scrapers.indeed import scrape as scrape_indeed
from scrapers.linkedin import scrape as scrape_linkedin
from scrapers.gradiireland import scrape as scrape_gradiireland
from scrapers.irishjobs import scrape as scrape_irishjobs
from scrapers.jobsie import scrape as scrape_jobsie

ALL_SCRAPERS = {
    "Indeed": scrape_indeed,
    "LinkedIn": scrape_linkedin,
    "GradIreland": scrape_gradiireland,
    "IrishJobs": scrape_irishjobs,
    "Jobs.ie": scrape_jobsie,
}
