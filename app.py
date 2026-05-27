"""
FLIP SCOUT — WEB DASHBOARD
TechSpatch Logistics

Manual-only scouting. No auto-runs, no scheduled calls.
Press Scout Now to trigger a scrape on demand.

Run locally:  python app.py
Deploy:       gunicorn app:app --bind 0.0.0.0:$PORT
"""
import os
import sys
import json
import threading
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify, request

BASE_DIR   = Path(__file__).parent
CITIES_FILE = BASE_DIR / "data" / "cities.json"

_DEFAULT_CITIES = [
    {"city": "Whiteville",   "state": "NC", "zip": "28472"},
    {"city": "Lumberton",    "state": "NC", "zip": "28358"},
    {"city": "Fayetteville", "state": "NC", "zip": "28301"},
    {"city": "Wilmington",   "state": "NC", "zip": "28401"},
    {"city": "Jacksonville", "state": "NC", "zip": "28540"},
    {"city": "Raleigh",      "state": "NC", "zip": "27601"},
]

def _read_cities():
    try:
        if CITIES_FILE.exists():
            return json.loads(CITIES_FILE.read_text())
    except Exception:
        pass
    return list(_DEFAULT_CITIES)

def _write_cities(cities):
    CITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    CITIES_FILE.write_text(json.dumps(cities, indent=2))

app = Flask(__name__)

# ── Scout state (in-memory, reset on restart) ──────────────────────────────
_lock = threading.Lock()
_state = {
    "running":  False,
    "log":      [],
    "started":  None,
    "finished": None,
    "exit_code": None,
}


def _run_scout(city_name=None):
    with _lock:
        _state["running"]   = True
        _state["log"]       = []
        _state["started"]   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _state["finished"]  = None
        _state["exit_code"] = None

    try:
        cmd = [sys.executable, "main.py", "--hot-only"]
        if city_name:
            cmd += ["--city", city_name]
        proc = subprocess.Popen(
            cmd,
            cwd=str(BASE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in proc.stdout:
            _state["log"].append(line.rstrip())
        proc.wait()
        _state["exit_code"] = proc.returncode
    except Exception as e:
        _state["log"].append(f"ERROR: {e}")
        _state["exit_code"] = 1
    finally:
        _state["finished"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _state["running"]  = False


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/scout", methods=["POST"])
def scout():
    if _state["running"]:
        return jsonify({"ok": False, "msg": "Scout already running"}), 409
    city_name = (request.get_json() or {}).get("city")
    threading.Thread(target=_run_scout, kwargs={"city_name": city_name}, daemon=True).start()
    return jsonify({"ok": True, "mode": "single" if city_name else "all"})


@app.route("/status")
def status():
    return jsonify({
        "running":   _state["running"],
        "log":       _state["log"][-200:],
        "started":   _state["started"],
        "finished":  _state["finished"],
        "exit_code": _state["exit_code"],
    })


@app.route("/leads")
def leads():
    db_path = BASE_DIR / "data" / "flip_leads.db"
    if not db_path.exists():
        return jsonify([])
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT deal_score, discount_pct, fully_fundable,
                   address, city, state, zip_code,
                   list_price, est_market_val, mao,
                   repair_estimate, arv_estimate,
                   beds, baths, sqft, year_built,
                   source, source_url, last_seen
            FROM leads
            WHERE is_hot = 1
            ORDER BY fully_fundable DESC, deal_score DESC, discount_pct DESC
            LIMIT 50
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/geocode")
def geocode():
    address = request.args.get("address", "")
    if not address:
        return jsonify({"error": "no address"}), 400
    import config as _cfg
    if not _cfg.GOOGLE_GEOCODING_KEY:
        return jsonify({"error": "no geocoding key"}), 500
    try:
        r = __import__("requests").get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={"address": address, "key": _cfg.GOOGLE_GEOCODING_KEY},
            timeout=10,
        ).json()
        if r.get("results"):
            loc = r["results"][0]["geometry"]["location"]
            return jsonify({"lat": loc["lat"], "lng": loc["lng"],
                            "formatted": r["results"][0]["formatted_address"]})
        return jsonify({"error": "not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/maps_key")
def maps_key():
    import config as _cfg
    return jsonify({"key": _cfg.GOOGLE_MAPS_EMBED_KEY})

@app.route("/cities", methods=["GET"])
def get_cities():
    return jsonify(_read_cities())

@app.route("/cities", methods=["POST"])
def add_city():
    data = request.get_json()
    city  = (data.get("city")  or "").strip().title()
    state = (data.get("state") or "").strip().upper()
    zip_  = (data.get("zip")   or "").strip()
    if not city or not state or not zip_:
        return jsonify({"ok": False, "msg": "city, state, and zip are required"}), 400
    if len(zip_) != 5 or not zip_.isdigit():
        return jsonify({"ok": False, "msg": "ZIP must be 5 digits"}), 400
    cities = _read_cities()
    if any(c["zip"] == zip_ for c in cities):
        return jsonify({"ok": False, "msg": f"{city} ({zip_}) is already in the list"}), 409
    cities.append({"city": city, "state": state, "zip": zip_})
    _write_cities(cities)
    return jsonify({"ok": True, "cities": cities})

@app.route("/cities/<zip_code>", methods=["DELETE"])
def remove_city(zip_code):
    cities = _read_cities()
    updated = [c for c in cities if c["zip"] != zip_code]
    if len(updated) == len(cities):
        return jsonify({"ok": False, "msg": "ZIP not found"}), 404
    if not updated:
        return jsonify({"ok": False, "msg": "Must keep at least one city"}), 400
    _write_cities(updated)
    return jsonify({"ok": True, "cities": updated})

@app.route("/stats")
def stats():
    db_path = BASE_DIR / "data" / "flip_leads.db"
    if not db_path.exists():
        return jsonify({"total": 0, "hot": 0, "last_seen": None, "cached_zips": 0})
    try:
        conn = sqlite3.connect(str(db_path))
        total      = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        hot        = conn.execute("SELECT COUNT(*) FROM leads WHERE is_hot=1").fetchone()[0]
        last       = conn.execute("SELECT MAX(last_seen) FROM leads").fetchone()[0]
        cached_zips = conn.execute("SELECT COUNT(*) FROM zip_market_stats").fetchone()[0]
        conn.close()
        return jsonify({"total": total, "hot": hot, "last_seen": last, "cached_zips": cached_zips})
    except Exception:
        return jsonify({"total": 0, "hot": 0, "last_seen": None, "cached_zips": 0})


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
