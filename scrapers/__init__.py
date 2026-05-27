"""Source-specific scrapers. Add new sources here and register in main.py."""
from .rentcast import RentCastScraper
from .hud_homes import HUDHomesScraper
from .auction_com import AuctionComScraper
from .realtor_rapidapi import RealtorRapidScraper
from .nc_foreclosures import NCForeclosuresScraper

ALL_SCRAPERS = [
    RentCastScraper,
    RealtorRapidScraper,
    AuctionComScraper,
    HUDHomesScraper,
    NCForeclosuresScraper,
]
