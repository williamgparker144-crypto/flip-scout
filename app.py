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
import threading
import subprocess
import sqlite3
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify

BASE_DIR = Path(__file__).parent

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


def _run_scout():
    with _lock:
        _state["running"]   = True
        _state["log"]       = []
        _state["started"]   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _state["finished"]  = None
        _state["exit_code"] = None

    try:
        proc = subprocess.Popen(
            [sys.executable, "main.py", "--hot-only"],
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
    threading.Thread(target=_run_scout, daemon=True).start()
    return jsonify({"ok": True})


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
