"""
RENTCAST API SCRAPER  (PRIMARY DATA SOURCE)

RentCast offers a legitimate API with a free tier (50 requests/month) and
affordable paid tiers. It is the workhorse of this system because it returns:
  - Active listings + price history
  - AVM (automated valuation) — the "est_market_val" used to score discounts
  - Rental estimates (flip-or-hold analysis)
  - Property records, owner info, last sale date

Sign up: https://developers.rentcast.io
Add your key to .env as RENTCAST_API_KEY=xxxxx
"""
from typing import Optional
from .base import BaseScraper
import config
from market_cache import estimate_market_value


class RentCastScraper(BaseScraper):
    SOURCE_NAME = "rentcast"
    BASE = "https://api.rentcast.io/v1"

    def _headers(self, extra=None):
        h = super()._headers(extra)
        if config.RENTCAST_API_KEY:
            h["X-Api-Key"] = config.RENTCAST_API_KEY
        h["Accept"] = "application/json"
        return h

    def fetch_leads(self, target: dict) -> list[dict]:
        if not config.RENTCAST_API_KEY:
            print(f"  [{self.SOURCE_NAME}] No API key — skipping. Add RENTCAST_API_KEY to .env")
            return []

        url = f"{self.BASE}/listings/sale"
        params = {
            "city": target["city"],
            "state": target["state"],
            "status": "Active",
            "limit": 50,
        }

        try:
            resp = self.get(url, params=params)
            if not resp:
                return []
            data = resp.json()
        except Exception as e:
            print(f"  [{self.SOURCE_NAME}] Error: {e}")
            return []

        listings = data if isinstance(data, list) else data.get("listings", [])
        leads: list[dict] = []

        for item in listings:
            lead = self._normalize(item, target)
            if lead:
                leads.append(lead)

        print(f"  [{self.SOURCE_NAME}] {len(leads)} listings from {target['city']}, {target['state']}")
        return leads

    def _normalize(self, item: dict, target: dict) -> Optional[dict]:
        try:
            address = item.get("formattedAddress") or item.get("addressLine1") or ""
            return {
                "source":        self.SOURCE_NAME,
                "source_url":    item.get("url") or "",
                "address":       address,
                "city":          item.get("city") or target["city"],
                "state":         item.get("state") or target["state"],
                "zip_code":      str(item.get("zipCode") or target.get("zip", "")),
                "list_price":    item.get("price"),
                "est_market_val": (
                    item.get("estimatedValue")
                    or estimate_market_value(
                        str(item.get("zipCode") or target.get("zip", "")),
                        item.get("squareFootage"),
                    )
                ),
                "est_rent":      item.get("estimatedRent"),
                "beds":          item.get("bedrooms"),
                "baths":         item.get("bathrooms"),
                "sqft":          item.get("squareFootage"),
                "year_built":    item.get("yearBuilt"),
                "lot_size":      item.get("lotSize"),
                "property_type": item.get("propertyType"),
                "status":        item.get("status", "Active"),
                "description":   item.get("description") or "",
                "raw_json":      str(item)[:5000],
            }
        except Exception:
            return None
