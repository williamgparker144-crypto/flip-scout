"""
DISCORD NOTIFIER

Posts each newly-qualified hot lead to a Discord channel via webhook.
Uses Discord's embed format for clean, scannable cards with all deal math.

Webhook setup (one-time, per Discord server):
  1. In Discord, right-click your target channel → Edit Channel
  2. Integrations → Webhooks → New Webhook
  3. Copy the Webhook URL
  4. Paste into .env as DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

Discord rate limits: 30 messages/minute per webhook. This module enforces
a 1.5-second delay between sends and caps batches at MAX_ALERTS_PER_RUN.
"""
import time
import requests
import config

# Embed color codes (Discord uses decimal RGB)
COLOR_FIRE      = 0xFF4500   # Hot deal, fully fundable, score >= 75
COLOR_HOT       = 0xFFA500   # Hot deal
COLOR_WARM      = 0xFFD700   # Score 60-74
COLOR_INFO      = 0x5865F2   # Daily summary

MAX_ALERTS_PER_RUN = 15      # Hard cap to avoid spam on first run
DELAY_BETWEEN_MSG  = 1.5     # seconds (Discord rate limit guard)


def _color_for(lead: dict) -> int:
    if lead.get("fully_fundable") and (lead.get("deal_score") or 0) >= 75:
        return COLOR_FIRE
    if (lead.get("deal_score") or 0) >= 60:
        return COLOR_HOT
    return COLOR_WARM


def _money(value) -> str:
    if value is None or value == 0:
        return "—"
    try:
        return f"${float(value):,.0f}"
    except (ValueError, TypeError):
        return "—"


def _build_embed(lead: dict) -> dict:
    """Build a Discord embed payload for a single lead."""
    addr = lead.get("address") or "Address unknown"
    city = lead.get("city") or ""
    state = lead.get("state") or ""
    zip_code = lead.get("zip_code") or ""
    fundable = "✅ YES — zero down on purchase" if lead.get("fully_fundable") else "❌ Cash gap required"

    fields = [
        {"name": "📍 Location",
         "value": f"{city}, {state} {zip_code}",
         "inline": True},
        {"name": "🎯 Deal Score",
         "value": f"**{lead.get('deal_score') or 0}/100**",
         "inline": True},
        {"name": "📉 Discount",
         "value": f"**{lead.get('discount_pct') or 0:.0f}%** below market",
         "inline": True},
        {"name": "💰 List Price",
         "value": _money(lead.get("list_price")),
         "inline": True},
        {"name": "🏷️ Market Value",
         "value": _money(lead.get("est_market_val")),
         "inline": True},
        {"name": "🏚️ ARV",
         "value": _money(lead.get("arv_estimate")),
         "inline": True},
        {"name": "🏦 Loan @ 70% FMV",
         "value": _money(lead.get("max_loan_amount")),
         "inline": True},
        {"name": "💵 Cash to Close",
         "value": _money(lead.get("cash_to_close")),
         "inline": True},
        {"name": "🛠️ Repair Est.",
         "value": _money(lead.get("repair_estimate")),
         "inline": True},
        {"name": "🎯 MAO (70% Rule)",
         "value": _money(lead.get("mao")),
         "inline": True},
        {"name": "🏠 Beds/Baths/SqFt",
         "value": f"{lead.get('beds') or '?'} / {lead.get('baths') or '?'} / {lead.get('sqft') or '?'}",
         "inline": True},
        {"name": "📅 Year Built",
         "value": str(lead.get("year_built") or "—"),
         "inline": True},
        {"name": "✨ Lender Verdict",
         "value": fundable,
         "inline": False},
    ]

    # Distress signals (optional, only if present)
    if lead.get("distress_score", 0) > 0:
        terms = lead.get("distress_terms") or ""
        terms_display = ", ".join(terms.split(",")[:5]) if terms else "—"
        fields.append({
            "name": f"🚩 Distress Signals ({lead['distress_score']} matched)",
            "value": f"`{terms_display}`",
            "inline": False,
        })

    embed = {
        "title": f"🔥 {addr}",
        "description": f"**New hot flip lead** from `{lead.get('source', 'unknown')}`",
        "color": _color_for(lead),
        "fields": fields,
        "footer": {"text": "Flip Scraper • TechSpatch Logistics"},
        "timestamp": lead.get("last_seen"),
    }
    if lead.get("source_url"):
        embed["url"] = lead["source_url"]

    return embed


def send_lead_alert(lead: dict) -> bool:
    """Post a single lead to Discord. Returns True on success."""
    if not config.DISCORD_WEBHOOK_URL:
        return False

    payload = {
        "username": "Flip Scout",
        "embeds": [_build_embed(lead)],
    }
    try:
        resp = requests.post(
            config.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 204):
            return True
        # Handle rate limit
        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 2)
            time.sleep(float(retry_after) + 0.5)
            resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            return resp.status_code in (200, 204)
        print(f"  [discord] HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"  [discord] Error: {e}")
        return False


def send_summary(stats: dict, hot_count: int) -> bool:
    """Post a run-summary message after the alert batch."""
    if not config.DISCORD_WEBHOOK_URL:
        return False

    by_source = "\n".join(f"  • `{k}`: {v}" for k, v in stats.get("by_source", {}).items()) or "  (none)"

    embed = {
        "title": "📊 Flip Scraper — Run Complete",
        "color": COLOR_INFO,
        "fields": [
            {"name": "Total leads tracked", "value": str(stats.get("total", 0)), "inline": True},
            {"name": "Hot leads in DB",    "value": str(stats.get("hot", 0)),   "inline": True},
            {"name": "New alerts sent",    "value": str(hot_count),             "inline": True},
            {"name": "Sources",            "value": by_source,                  "inline": False},
        ],
        "footer": {"text": "Flip Scraper • TechSpatch Logistics"},
    }
    try:
        requests.post(
            config.DISCORD_WEBHOOK_URL,
            json={"username": "Flip Scout", "embeds": [embed]},
            timeout=10,
        )
        return True
    except Exception:
        return False


def broadcast_new_hot_leads(leads: list[dict]) -> int:
    """
    Send Discord alerts for a batch of leads.
    Returns count successfully sent.
    """
    if not config.DISCORD_WEBHOOK_URL:
        print("  [discord] No webhook configured — skipping. Add DISCORD_WEBHOOK_URL to .env")
        return 0

    if not leads:
        return 0

    # Sort by deal score so most important deals arrive first
    leads = sorted(leads, key=lambda x: x.get("deal_score") or 0, reverse=True)
    batch = leads[:MAX_ALERTS_PER_RUN]

    sent = 0
    for lead in batch:
        if send_lead_alert(lead):
            sent += 1
        time.sleep(DELAY_BETWEEN_MSG)

    if len(leads) > MAX_ALERTS_PER_RUN:
        overflow = len(leads) - MAX_ALERTS_PER_RUN
        print(f"  [discord] {overflow} additional hot leads queued for next run (rate-limited)")

    return sent
