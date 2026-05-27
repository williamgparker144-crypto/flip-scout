"""
FLIP SCRAPER — CONFIGURATION MODULE
Centralized control of all search parameters and API keys.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# DIRECTORY PATHS
# ============================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
EXPORTS_DIR = BASE_DIR / "exports"
DB_PATH = DATA_DIR / "flip_leads.db"

# ============================================================
# API KEYS (loaded from .env file)
# ============================================================
RENTCAST_API_KEY      = os.getenv("RENTCAST_API_KEY", "")
RAPIDAPI_KEY          = os.getenv("RAPIDAPI_KEY", "")
DISCORD_WEBHOOK_URL   = os.getenv("DISCORD_WEBHOOK_URL", "")
GOOGLE_GEOCODING_KEY  = os.getenv("GOOGLE_GEOCODING_KEY", "")
GOOGLE_MAPS_EMBED_KEY = os.getenv("GOOGLE_MAPS_EMBED_KEY", "")

# ============================================================
# SEARCH TARGETS
# Managed via dashboard — stored in data/cities.json.
# Falls back to defaults below if the file doesn't exist yet.
# ============================================================
import json as _json

TARGET_STATES = ["NC"]

_CITIES_FILE = DATA_DIR / "cities.json"
_DEFAULT_CITIES = [
    {"city": "Whiteville",   "state": "NC", "zip": "28472"},
    {"city": "Lumberton",    "state": "NC", "zip": "28358"},
    {"city": "Fayetteville", "state": "NC", "zip": "28301"},
    {"city": "Wilmington",   "state": "NC", "zip": "28401"},
    {"city": "Jacksonville", "state": "NC", "zip": "28540"},
    {"city": "Raleigh",      "state": "NC", "zip": "27601"},
]

def _load_cities():
    try:
        if _CITIES_FILE.exists():
            return _json.loads(_CITIES_FILE.read_text())
    except Exception:
        pass
    return _DEFAULT_CITIES

TARGET_CITIES = _load_cities()

# ============================================================
# DEAL FILTERS — what qualifies as "cheap"
# ============================================================
MAX_LIST_PRICE      = 250_000     # Skip anything above this
MIN_LIST_PRICE      = 20_000      # Skip anything below (likely junk)
MIN_BEDROOMS        = 2
MIN_BATHROOMS       = 1
MIN_SQFT            = 700
MAX_SQFT            = 3500
MIN_YEAR_BUILT      = 1900

# Discount-to-market thresholds (the core flip metrics)
MIN_DISCOUNT_PCT    = 15.0        # List price must be ≥15% under est. market value
TARGET_DISCOUNT_PCT = 30.0        # Hot lead threshold

# 70% Rule constants (flipper's universal formula)
SEVENTY_PCT_RULE        = 0.70
ESTIMATED_REPAIR_PSF    = 25      # $/sqft conservative repair estimate
CLOSING_COSTS_PCT       = 0.03    # 3% buying + 3% selling typically

# ============================================================
# DISTRESS KEYWORDS — signals motivated sellers
# ============================================================
DISTRESS_KEYWORDS = [
    "fixer", "fixer upper", "handyman", "handyman special",
    "needs work", "needs tlc", "tlc", "as-is", "as is",
    "cash only", "cash buyers only", "investor special",
    "investment opportunity", "estate sale", "probate",
    "foreclosure", "pre-foreclosure", "short sale",
    "bank owned", "reo", "auction", "must sell",
    "motivated", "must go", "below market", "below appraisal",
    "distressed", "rehab", "tear down", "teardown",
    "structural", "fire damage", "water damage", "mold",
    "vacant", "abandoned", "boarded up", "uninhabitable",
    "no inspection", "no contingencies", "no financing",
    "make offer", "bring offers", "owner financing",
    "trustee sale", "sheriff sale", "tax sale", "tax lien",
]

# ============================================================
# REQUEST BEHAVIOR — be a good citizen
# ============================================================
REQUEST_DELAY_SECONDS   = 2.0     # Sleep between requests per source
REQUEST_TIMEOUT         = 30
MAX_RETRIES             = 3
USER_AGENT_ROTATION     = True

# ============================================================
# OUTPUT
# ============================================================
EXPORT_CSV          = True
EXPORT_JSON         = True
HOT_LEAD_EMAIL      = ""          # Optional: email for daily digest
