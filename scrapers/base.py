"""
BASE SCRAPER
Shared HTTP behavior: retries, throttling, rotating user-agents.
Every source-specific scraper inherits from this class.
"""
import time
import random
from typing import Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from fake_useragent import UserAgent
import config


class BaseScraper:
    SOURCE_NAME = "base"

    def __init__(self):
        self.session = requests.Session()
        try:
            self.ua = UserAgent()
        except Exception:
            self.ua = None
        self._last_request = 0.0

    def _headers(self, extra: dict | None = None) -> dict:
        headers = {
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }
        if config.USER_AGENT_ROTATION and self.ua:
            try:
                headers["User-Agent"] = self.ua.random
            except Exception:
                headers["User-Agent"] = "Mozilla/5.0 (compatible; FlipScraper/1.0)"
        else:
            headers["User-Agent"] = "Mozilla/5.0 (compatible; FlipScraper/1.0)"
        if extra:
            headers.update(extra)
        return headers

    def _throttle(self):
        elapsed = time.time() - self._last_request
        if elapsed < config.REQUEST_DELAY_SECONDS:
            time.sleep(config.REQUEST_DELAY_SECONDS - elapsed + random.uniform(0, 0.5))
        self._last_request = time.time()

    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((requests.RequestException,)),
    )
    def get(self, url: str, params: Optional[dict] = None,
            headers: Optional[dict] = None) -> Optional[requests.Response]:
        self._throttle()
        try:
            resp = self.session.get(
                url,
                params=params,
                headers=self._headers(headers),
                timeout=config.REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                time.sleep(10)
                raise requests.RequestException("Rate limited")
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            print(f"  [{self.SOURCE_NAME}] Request failed: {e}")
            raise

    def fetch_leads(self, target: dict) -> list[dict]:
        """Override in subclasses. `target` = {city, state, zip}."""
        raise NotImplementedError
