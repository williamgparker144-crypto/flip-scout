"""
AUCTION.COM SCRAPER

Auction.com is the largest online marketplace for distressed property
auctions in the U.S. — bank-owned (REO), foreclosure, and short-sale
properties. Listings are publicly viewable.

Auction.com uses a JSON XHR endpoint that returns paginated search results
in structured form. This scraper hits that endpoint with city/state filters.

NOTE: Auction.com periodically changes their API. If the payload structure
shifts, update `_normalize` below.
"""
from typing import Optional
from .base import BaseScraper


class AuctionComScraper(BaseScraper):
    SOURCE_NAME = "auction_com"
    SEARCH_URL = "https://www.auction.com/residential/all-asset-types"

    def fetch_leads(self, target: dict) -> list[dict]:
        # Auction.com is JavaScript-heavy. The HTML index page lists
        # property cards we can parse. For production-grade reliability,
        # use a paid wrapper like Apify's auction.com scraper or
        # ScrapingBee, but the free path is below.
        try:
            params = {
                "state": target["state"],
                "city": target["city"],
                "asset_types": "RES",
            }
            resp = self.get(self.SEARCH_URL, params=params)
            if not resp:
                return []
        except Exception as e:
            print(f"  [{self.SOURCE_NAME}] Error: {e}")
            return []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            return []

        leads: list[dict] = []

        # Property cards
        for card in soup.select('[data-elm-id*="property-card"]'):
            try:
                addr_el  = card.select_one('[data-elm-id*="address"]')
                price_el = card.select_one('[data-elm-id*="opening-bid"], [data-elm-id*="starting-bid"], [class*="price"]')
                beds_el  = card.select_one('[data-elm-id*="beds"], [class*="beds"]')
                baths_el = card.select_one('[data-elm-id*="baths"], [class*="baths"]')
                sqft_el  = card.select_one('[data-elm-id*="sqft"], [class*="sqft"]')
                link_el  = card.find("a", href=True)

                price_text = (price_el.get_text() if price_el else "")
                price = self._parse_price(price_text)

                if not price:
                    continue

                lead = {
                    "source":      self.SOURCE_NAME,
                    "source_url":  "https://www.auction.com" + link_el["href"] if link_el else "",
                    "address":     addr_el.get_text(strip=True) if addr_el else "",
                    "city":        target["city"],
                    "state":       target["state"],
                    "zip_code":    target.get("zip", ""),
                    "list_price":  price,
                    "beds":        self._parse_num(beds_el.get_text() if beds_el else ""),
                    "baths":       self._parse_num(baths_el.get_text() if baths_el else ""),
                    "sqft":        self._parse_num(sqft_el.get_text() if sqft_el else ""),
                    "property_type": "Auction",
                    "status":      "Auction",
                    "description": "Auction.com listing — foreclosure or bank-owned, cash-only typical",
                }
                leads.append(lead)
            except Exception:
                continue

        print(f"  [{self.SOURCE_NAME}] {len(leads)} auction properties in {target['city']}, {target['state']}")
        return leads

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        import re
        m = re.search(r"\$?([\d,]+)", text or "")
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _parse_num(text: str) -> Optional[float]:
        import re
        m = re.search(r"(\d+\.?\d*)", text or "")
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None
