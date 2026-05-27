"""
NORTH CAROLINA FORECLOSURE PUBLIC RECORDS SCRAPER

Every NC county Clerk of Superior Court publishes Notice of Sale records
under NCGS §45-21.17. These are 100% public records — no API key, no TOS,
fully legal to access and aggregate.

Approach: hit each county's foreclosure notice page (where available) and
fall back to the statewide aggregator at NCcourts.gov.

This is the highest-signal source for pre-foreclosure flip leads because
the property is about to be auctioned and many owners will negotiate to
avoid the sale.
"""
from typing import Optional
from .base import BaseScraper


class NCForeclosuresScraper(BaseScraper):
    SOURCE_NAME = "nc_foreclosures"

    # County-specific URLs (extend as you build relationships per county)
    COUNTY_URLS = {
        "Columbus":     "https://www.nccourts.gov/locations/columbus-county",
        "Robeson":      "https://www.nccourts.gov/locations/robeson-county",
        "Cumberland":   "https://www.nccourts.gov/locations/cumberland-county",
        "New Hanover":  "https://www.nccourts.gov/locations/new-hanover-county",
        "Wake":         "https://www.nccourts.gov/locations/wake-county",
        "Mecklenburg":  "https://www.nccourts.gov/locations/mecklenburg-county",
    }

    def fetch_leads(self, target: dict) -> list[dict]:
        print(f"  [{self.SOURCE_NAME}] Disabled — requires per-county handlers. See README §10 roadmap.")
        return []
