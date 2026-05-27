"""
ZIP MARKET STATISTICS CACHE

Fetches and caches RentCast /markets data per ZIP code.
Cache survives 60 days by default — refresh manually if needed.
This is the engine that makes free-tier discount calculation possible.
"""
import time
import sqlite3
from datetime import datetime, timedelta
import requests
import config
import database

CACHE_DAYS = 60
RENTCAST_MARKETS_URL = "https://api.rentcast.io/v1/markets"


def _cache_fresh(last_updated_iso: str) -> bool:
    if not last_updated_iso:
        return False
    try:
        last = datetime.fromisoformat(last_updated_iso)
        return (datetime.utcnow() - last) < timedelta(days=CACHE_DAYS)
    except ValueError:
        return False


def get_cached(zip_code: str) -> dict | None:
    with database.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM zip_market_stats WHERE zip_code = ?",
            (zip_code,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    if _cache_fresh(d.get("last_updated", "")):
        return d
    return d  # return stale rather than nothing — better than no data


def fetch_and_cache(zip_code: str) -> dict | None:
    """Fetch fresh market stats for a ZIP and cache. Returns the stats."""
    if not config.RENTCAST_API_KEY:
        print(f"  [market_cache] No RENTCAST_API_KEY — cannot fetch {zip_code}")
        return None

    headers = {
        "X-Api-Key": config.RENTCAST_API_KEY,
        "Accept": "application/json",
    }
    params = {"zipCode": zip_code, "dataType": "Sale"}

    try:
        resp = requests.get(RENTCAST_MARKETS_URL, headers=headers,
                            params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  [market_cache] HTTP {resp.status_code} for {zip_code}")
            return get_cached(zip_code)  # fall back to stale cache
        data = resp.json()
    except Exception as e:
        print(f"  [market_cache] Error fetching {zip_code}: {e}")
        return get_cached(zip_code)

    sale = data.get("saleData", {}) or {}
    stats = {
        "zip_code":               zip_code,
        "median_price":           sale.get("medianPrice"),
        "median_price_per_sqft":  sale.get("medianPricePerSquareFoot"),
        "average_price":          sale.get("averagePrice"),
        "average_price_per_sqft": sale.get("averagePricePerSquareFoot"),
        "total_listings":         sale.get("totalListings"),
        "last_updated":           datetime.utcnow().isoformat(),
    }

    with database.get_conn() as conn:
        conn.execute("""
            INSERT INTO zip_market_stats
            (zip_code, median_price, median_price_per_sqft, average_price,
             average_price_per_sqft, total_listings, last_updated)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(zip_code) DO UPDATE SET
                median_price           = excluded.median_price,
                median_price_per_sqft  = excluded.median_price_per_sqft,
                average_price          = excluded.average_price,
                average_price_per_sqft = excluded.average_price_per_sqft,
                total_listings         = excluded.total_listings,
                last_updated           = excluded.last_updated
        """, (
            stats["zip_code"], stats["median_price"], stats["median_price_per_sqft"],
            stats["average_price"], stats["average_price_per_sqft"],
            stats["total_listings"], stats["last_updated"],
        ))

    print(f"  [market_cache] Fetched {zip_code}: median ${stats['median_price'] or 0:,.0f}, "
          f"median $/sqft ${stats['median_price_per_sqft'] or 0:.2f}")
    return stats


def get_or_fetch(zip_code: str) -> dict | None:
    """Return cached stats if fresh, otherwise fetch and cache."""
    cached = get_cached(zip_code)
    if cached and _cache_fresh(cached.get("last_updated", "")):
        return cached
    return fetch_and_cache(zip_code)


def estimate_market_value(zip_code: str, sqft: float | None) -> float | None:
    """
    Given a property's ZIP and sqft, return the estimated market value
    using ZIP median price-per-sqft.
    """
    stats = get_or_fetch(zip_code)
    if not stats:
        return None
    median_psf = stats.get("median_price_per_sqft")
    if sqft and sqft > 0 and median_psf and median_psf > 0:
        return round(float(sqft) * float(median_psf), 0)
    # Fallback to flat median price if sqft missing
    return stats.get("median_price")
