"""
HUD HOME STORE SCRAPER

HUD Home Store lists FHA-foreclosed properties owned by the U.S. Department
of Housing and Urban Development. All data is publicly published. These
properties are sold at deep discounts and frequently need rehab — prime
flip inventory.

Source: hudhomestore.gov   (search API endpoint returns JSON)
"""
from typing import Optional
from .base import BaseScraper


class HUDHomesScraper(BaseScraper):
    SOURCE_NAME = "hud_homes"
    SEARCH_URL = "https://www.hudhomestore.gov/Listing/PropertySearchAdv.aspx"
    # HUD's public search returns HTML; we POST search criteria.
    # When the HTML form changes, update selectors here.

    def fetch_leads(self, target: dict) -> list[dict]:
        print(f"  [{self.SOURCE_NAME}] Disabled — HUD site under maintenance. Re-enable after site restoration.")
        return []
