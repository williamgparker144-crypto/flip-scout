"""
DATABASE MODULE
SQLite-backed lead storage with deduplication and tracking.
"""
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import config


def fingerprint(address: str, zip_code: str) -> str:
    """Generate stable hash for deduplication across sources."""
    normalized = f"{(address or '').lower().strip()}|{(zip_code or '').strip()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize schema. Safe to run repeatedly."""
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fingerprint     TEXT UNIQUE NOT NULL,
            source          TEXT NOT NULL,
            source_url      TEXT,
            address         TEXT,
            city            TEXT,
            state           TEXT,
            zip_code        TEXT,
            list_price      REAL,
            est_market_val  REAL,
            est_rent        REAL,
            beds            REAL,
            baths           REAL,
            sqft            REAL,
            year_built      INTEGER,
            lot_size        REAL,
            property_type   TEXT,
            status          TEXT,
            description     TEXT,
            distress_score  INTEGER DEFAULT 0,
            distress_terms  TEXT,
            discount_pct    REAL,
            arv_estimate    REAL,
            repair_estimate REAL,
            mao             REAL,
            max_loan_amount REAL,
            cash_to_close   REAL,
            fully_fundable  INTEGER DEFAULT 0,
            deal_score      INTEGER,
            is_hot          INTEGER DEFAULT 0,
            first_seen      TEXT NOT NULL,
            last_seen       TEXT NOT NULL,
            raw_json        TEXT
        );

        CREATE TABLE IF NOT EXISTS zip_market_stats (
            zip_code              TEXT PRIMARY KEY,
            median_price          REAL,
            median_price_per_sqft REAL,
            average_price         REAL,
            average_price_per_sqft REAL,
            total_listings        INTEGER,
            last_updated          TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_leads_state    ON leads(state);
        CREATE INDEX IF NOT EXISTS idx_leads_city     ON leads(city);
        CREATE INDEX IF NOT EXISTS idx_leads_hot      ON leads(is_hot);
        CREATE INDEX IF NOT EXISTS idx_leads_score    ON leads(deal_score DESC);
        CREATE INDEX IF NOT EXISTS idx_leads_seen     ON leads(last_seen DESC);
        """)
        # Migrate existing DB: add columns added after initial release
        for col, definition in [
            ("max_loan_amount", "REAL"),
            ("cash_to_close",   "REAL"),
            ("fully_fundable",  "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists


def upsert_lead(lead: dict) -> bool:
    """
    Insert or update a lead. Returns True if NEW, False if existing.
    """
    fp = fingerprint(lead.get("address", ""), lead.get("zip_code", ""))
    now = datetime.utcnow().isoformat()

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM leads WHERE fingerprint = ?", (fp,)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE leads SET
                    last_seen = ?, list_price = ?, status = ?,
                    distress_score = ?, deal_score = ?, is_hot = ?
                WHERE fingerprint = ?
            """, (
                now, lead.get("list_price"), lead.get("status"),
                lead.get("distress_score", 0), lead.get("deal_score", 0),
                lead.get("is_hot", 0), fp
            ))
            return False

        conn.execute("""
            INSERT INTO leads (
                fingerprint, source, source_url, address, city, state, zip_code,
                list_price, est_market_val, est_rent, beds, baths, sqft,
                year_built, lot_size, property_type, status, description,
                distress_score, distress_terms, discount_pct, arv_estimate,
                repair_estimate, mao, deal_score, is_hot,
                first_seen, last_seen, raw_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            fp, lead.get("source"), lead.get("source_url"),
            lead.get("address"), lead.get("city"), lead.get("state"),
            lead.get("zip_code"), lead.get("list_price"),
            lead.get("est_market_val"), lead.get("est_rent"),
            lead.get("beds"), lead.get("baths"), lead.get("sqft"),
            lead.get("year_built"), lead.get("lot_size"),
            lead.get("property_type"), lead.get("status"),
            lead.get("description"), lead.get("distress_score", 0),
            lead.get("distress_terms", ""), lead.get("discount_pct"),
            lead.get("arv_estimate"), lead.get("repair_estimate"),
            lead.get("mao"), lead.get("deal_score", 0),
            lead.get("is_hot", 0), now, now, lead.get("raw_json", "")
        ))
        return True


def get_hot_leads(limit: int = 100):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM leads
            WHERE is_hot = 1
            ORDER BY deal_score DESC, last_seen DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_all_leads(limit: int = 1000):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM leads
            ORDER BY deal_score DESC, last_seen DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        hot   = conn.execute("SELECT COUNT(*) FROM leads WHERE is_hot = 1").fetchone()[0]
        by_src = conn.execute(
            "SELECT source, COUNT(*) c FROM leads GROUP BY source"
        ).fetchall()
        return {
            "total": total,
            "hot": hot,
            "by_source": {r["source"]: r["c"] for r in by_src},
        }
