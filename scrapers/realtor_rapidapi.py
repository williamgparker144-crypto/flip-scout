"""
REALTOR.COM (via RapidAPI) SCRAPER

Direct scraping of Realtor.com violates their TOS and triggers fast IP bans.
RapidAPI offers legitimate, paid wrappers around Realtor.com data
(commonly named "Realty in US" or "Realtor.com" by the publisher).

Sign up: https://rapidapi.com/  → search "realtor"
Add your key to .env as RAPIDAPI_KEY=xxxxx

Free tier typically allows ~100 calls/month, paid tiers go higher.
This scraper looks for keyword-distressed listings and "fixer" inventory.
"""
from typing import Optional
from .base import BaseScraper
import config


class RealtorRapidScraper(BaseScraper):
    SOURCE_NAME = "realtor_rapidapi"
    HOST = "realtor-com4.p.rapidapi.com"          # confirm in your RapidAPI dashboard
    SEARCH_URL = f"https://{HOST}/properties/v3/list"

    def _headers(self, extra=None):
        h = super()._headers(extra)
        if config.RAPIDAPI_KEY:
            h["x-rapidapi-key"]  = config.RAPIDAPI_KEY
            h["x-rapidapi-host"] = self.HOST
        h["Accept"] = "application/json"
        h["Content-Type"] = "application/json"
        return h

    def fetch_leads(self, target: dict) -> list[dict]:
        if not config.RAPIDAPI_KEY:
            print(f"  [{self.SOURCE_NAME}] No RapidAPI key — skipping. Add RAPIDAPI_KEY to .env")
            return []

        payload = {
            "limit": 42,
            "offset": 0,
            "city": target["city"],
            "state_code": target["state"],
            "status": ["for_sale"],
            "sort": {"direction": "desc", "field": "list_date"},
            "price_max": config.MAX_LIST_PRICE,
            "price_min": config.MIN_LIST_PRICE,
        }

        try:
            self._throttle()
            resp = self.session.post(
                self.SEARCH_URL,
                headers=self._headers(),
                json=payload,
                timeout=config.REQUEST_TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"  [{self.SOURCE_NAME}] HTTP {resp.status_code} — verify HOST and endpoint in your RapidAPI dashboard")
                return []
            data = resp.json()
        except Exception as e:
            print(f"  [{self.SOURCE_NAME}] Error: {e}")
            return []

        results = (
            data.get("data", {}).get("home_search", {}).get("results")
            or data.get("properties")
            or []
        )

        leads = []
        for item in results:
            lead = self._normalize(item, target)
            if lead:
                leads.append(lead)

        print(f"  [{self.SOURCE_NAME}] {len(leads)} listings from {target['city']}, {target['state']}")
        return leads

    def _normalize(self, item: dict, target: dict) -> Optional[dict]:
        try:
            loc = item.get("location", {}) or {}
            addr = loc.get("address", {}) or {}
            desc = item.get("description", {}) or {}
            price = item.get("list_price") or item.get("price")

            return {
                "source":        self.SOURCE_NAME,
                "source_url":    item.get("href") or "",
                "address":       addr.get("line") or item.get("address") or "",
                "city":          addr.get("city") or target["city"],
                "state":         addr.get("state_code") or target["state"],
                "zip_code":      str(addr.get("postal_code") or target.get("zip", "")),
                "list_price":    price,
                "est_market_val":item.get("estimate", {}).get("estimate") or price,
                "beds":          desc.get("beds"),
                "baths":         desc.get("baths_consolidated") or desc.get("baths"),
                "sqft":          desc.get("sqft"),
                "year_built":    desc.get("year_built"),
                "lot_size":      desc.get("lot_sqft"),
                "property_type": desc.get("type"),
                "status":        item.get("status", "for_sale"),
                "description":   (item.get("description") or {}).get("text", "") or "",
                "raw_json":      str(item)[:5000],
            }
        except Exception:
            return None
