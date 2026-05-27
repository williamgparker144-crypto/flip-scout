# FLIP SCRAPER — OPERATING MANUAL

A multi-source distressed-property lead engine for residential real-estate
flippers. Aggregates listings from legitimate APIs and public-record
sources, applies investor math (70% Rule, MAO, distress scoring), and
outputs a ranked CSV/JSON of qualified flip leads.

---

## 1.0 SYSTEM OVERVIEW

```
┌──────────────────────────────────────────────────────────────────────┐
│                       FLIP SCRAPER ARCHITECTURE                      │
└──────────────────────────────────────────────────────────────────────┘

       SOURCES                ENGINE                  OUTPUT
   ┌─────────────┐       ┌──────────────┐       ┌──────────────┐
   │ RentCast    │──┐    │  analyzer.py │       │  SQLite DB   │
   │ Realtor API │──┤    │  · 70% Rule  │       │  flip_leads  │
   │ Auction.com │──┼──▶ │  · MAO calc  │ ────▶ │              │
   │ HUD Homes   │──┤    │  · Distress  │       │  CSV export  │
   │ NC Courts   │──┘    │  · Filters   │       │  JSON export │
   └─────────────┘       └──────────────┘       │  CLI report  │
                                                └──────────────┘
```

The system is modular: every data source is a self-contained scraper
under `scrapers/`. Add a new source by writing a new file that extends
`BaseScraper` and registering it in `scrapers/__init__.py`.

---

## 2.0 DATA SOURCES — WHAT IS AND IS NOT INCLUDED

| Source           | Type           | Cost                | Legal Status                 |
|------------------|----------------|---------------------|------------------------------|
| RentCast API     | Off-market + listings + valuations | Free 50/mo, then $25+/mo | Public API |
| Realtor.com      | Active listings (via RapidAPI) | Free 100/mo, then $10+/mo | Licensed API |
| Auction.com      | Foreclosure auctions | Free | Public listings |
| HUD Home Store   | Federal foreclosures | Free | Public records |
| NC Foreclosures  | Pre-foreclosure notices | Free | Public records (NCGS §45-21.17) |

### Sources deliberately excluded
- **Zillow direct scraping** — violates TOS, results in fast IP bans, no
  longer offers a public API. Use Realtor.com via RapidAPI instead.
- **MLS direct access** — requires licensed real-estate agent credentials.
  If you have agent access, build a separate MLS connector.
- **Facebook Marketplace** — TOS-restricted and unstable. Use Apify or
  similar paid wrappers if you need this data.

---

## 3.0 INSTALLATION

### 3.1 Prerequisites
- Python 3.10 or higher
- A free RentCast account (recommended, primary data source)
- A free RapidAPI account (recommended for Realtor.com data)

### 3.2 Setup steps

```bash
# 1. Move into project directory
cd flip_scraper

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment template and add your keys
cp .env.example .env
# Edit .env with a text editor and paste your API keys
```

---

## 4.0 CONFIGURATION

All operating parameters live in `config.py`. The four sections that
typically need editing:

### 4.1 Target geography
Modify `TARGET_CITIES` to add or remove cities. Each entry needs city,
state code, and a representative ZIP. Default list covers North Carolina
markets including Whiteville, Lumberton, Fayetteville, Wilmington,
Raleigh, Greensboro, and Charlotte.

### 4.2 Price and property filters
- `MAX_LIST_PRICE` — listings above this are skipped
- `MIN_LIST_PRICE` — listings below this are treated as data noise
- `MIN_BEDROOMS`, `MIN_BATHROOMS`, `MIN_SQFT`, `MAX_SQFT`, `MIN_YEAR_BUILT`

### 4.3 Deal-math constants
- `SEVENTY_PCT_RULE` — flipper's universal multiplier (default 0.70)
- `ESTIMATED_REPAIR_PSF` — conservative repair cost per square foot
- `MIN_DISCOUNT_PCT` — how far below market a listing must be to qualify
- `TARGET_DISCOUNT_PCT` — threshold to flag as a "hot" lead

### 4.4 Distress keywords
`DISTRESS_KEYWORDS` contains 40+ phrases that signal motivated sellers
(fixer-upper, as-is, foreclosure, must sell, etc). Add more as you
notice patterns in your market.

---

## 5.0 EXECUTION

### 5.1 Standard run
```bash
python main.py
```
This runs every scraper against every target city, applies analysis,
saves results to the database, and exports CSV + JSON.

### 5.2 Run flags
```bash
python main.py --hot-only      # Export only the high-priority leads
python main.py --no-scrape     # Re-export existing DB without scraping
python main.py --stats         # Show database statistics and exit
```

### 5.3 Schedule it
Cron entry for a 6 a.m. daily run on Linux/macOS:
```
0 6 * * * cd /path/to/flip_scraper && /path/to/venv/bin/python main.py --hot-only
```
On Windows, use Task Scheduler to invoke `python main.py --hot-only`.

---

## 6.0 OUTPUT — HOW TO READ THE REPORT

### 6.1 Deal Score (0–100)
Composite ranking applied to every lead:
- **40 points** — discount vs. estimated market value
- **30 points** — list price falls at or below the MAO
- **20 points** — number of distress keywords matched
- **10 points** — property fundamentals (beds, sqft, ARV/price ratio)

### 6.2 Hot lead definition
A lead is flagged hot when ANY of:
- `deal_score ≥ 60`, OR
- `discount_pct ≥ TARGET_DISCOUNT_PCT` (default 30%), OR
- `list_price ≤ MAO` (the 70% Rule passes)

### 6.3 The MAO column
**Maximum Allowable Offer** = (ARV × 0.70) − Repair Estimate

This is the most you can pay and still hit a 30% target margin after
holding, closing, and selling costs. If the list price is at or below
MAO, the deal is viable at face value — verify in person.

### 6.4 Output files
- `data/flip_leads.db` — SQLite database (full history, deduplicated)
- `exports/flip_leads_all_YYYYMMDD_HHMMSS.csv`
- `exports/flip_leads_hot_YYYYMMDD_HHMMSS.csv`
- JSON versions of both

---

## 7.0 LEGAL AND ETHICAL OPERATING GUIDELINES

### 7.1 What this system DOES respect
- Robots.txt and rate limits (built-in throttling at 2 s between calls)
- API providers' Terms of Service (paid where required)
- Public-records doctrine (foreclosure and tax notices)

### 7.2 What you must NOT do with this system
- Repurpose the scrapers to bypass paywalls or login walls
- Aggregate data and republish as a competing listing site without
  proper licensing (Realtor.com, RentCast, and similar APIs forbid this)
- Use any of this output to contact homeowners through methods that
  violate the TCPA (auto-dialers, mass texting without consent)

### 7.3 Personal compliance recommendations
- Skip-trace and outreach must comply with state-level wholesaling laws
  (North Carolina specifically regulates real-estate wholesaling — read
  NC Real Estate Commission guidance before contacting any owner)
- Treat all data as confidential — do not share lead lists publicly

---

## 8.0 EXTENDING THE SYSTEM

### 8.1 Add a new data source
1. Create `scrapers/your_source.py`
2. Subclass `BaseScraper`
3. Set `SOURCE_NAME = "your_source"`
4. Implement `fetch_leads(target: dict) -> list[dict]`
5. Return dicts matching the schema in `database.py::upsert_lead`
6. Register the class in `scrapers/__init__.py::ALL_SCRAPERS`

### 8.2 Tune the deal scorer
Edit `analyzer.py::deal_score`. Adjust the weight distribution to match
your local market. For example, if you operate in markets where most
flips need cosmetic work only, lower `ESTIMATED_REPAIR_PSF` in config.

### 8.3 Add notifications
Implement an email or SMS alert when `is_hot = 1` and `deal_score >= 75`.
Recommended free options: Resend (email, 100/day free), Twilio (SMS),
or a Slack webhook for a private alerts channel.

---

## 9.0 TROUBLESHOOTING

| Symptom                                  | Likely Cause                       | Fix |
|------------------------------------------|------------------------------------|-----|
| `rentcast: No API key — skipping`        | `.env` missing RENTCAST_API_KEY    | Add key to `.env` |
| HTTP 401 from RentCast                   | Key invalid or expired             | Regenerate at developers.rentcast.io |
| HTTP 429 from any source                 | Rate limit hit                     | Increase `REQUEST_DELAY_SECONDS` |
| HUD or Auction.com returns 0 listings    | HTML structure changed             | Update CSS selectors in scraper |
| `realtor_rapidapi: HTTP 403`             | Wrong HOST or unsubscribed         | Check RapidAPI dashboard, update `HOST` |
| Empty CSV exports                        | All filters too strict             | Loosen `MIN_DISCOUNT_PCT` in config |

---

## 10.0 ROADMAP — WHAT TO BUILD NEXT

Once the base system is producing leads, layer on:

1. **County-specific NC foreclosure parsers** — every NC Clerk of Court
   page is slightly different; build per-county handlers for the
   counties where you actively buy.
2. **Skip-tracing integration** — pipe hot leads to BatchSkipTracing or
   USPhoneBook to find owner contact info.
3. **Comps engine** — query RentCast comparables endpoint for recent
   sold listings within 0.5 miles to validate ARV.
4. **Direct-mail trigger** — auto-generate yellow-letter postcards via
   Lob.com API for the top 10 hot leads each week.
5. **Buyer's list integration** — when a lead is acquired, push to a
   private buyers list with photos, ARV, and assignment fee.

---

## APPENDIX A — THE 70% RULE IN PLAIN ENGLISH

The 70% Rule is the flipper's universal sanity check:

> Pay no more than 70% of the After-Repair Value, minus repairs.

Example:
- House will sell for **$200,000** fully rehabbed (ARV)
- Repairs will cost **$30,000**
- Maximum Allowable Offer = ($200,000 × 0.70) − $30,000 = **$110,000**

If you pay $110,000 and the deal performs as expected:
- $200,000 sale price
- −$110,000 purchase
- −$30,000 repairs
- −$12,000 closing/holding costs (6% rough average)
- **= ~$48,000 profit** (24% margin)

The 30% gap absorbs cost overruns, market shifts, and time on market.
Listings that come in at or below MAO are the only ones worth pursuing
without aggressive negotiation.

---

*Last updated for the current build. Maintain this manual as the system
evolves — outdated documentation kills more side businesses than bad code.*
