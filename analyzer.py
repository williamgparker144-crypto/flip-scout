"""
DEAL ANALYZER MODULE
Applies investor math (70% Rule, MAO, distress scoring) to raw listings
and produces a single deal_score that ranks leads from 0-100.
"""
import config


def calc_repair_estimate(sqft: float | None, year_built: int | None,
                         distress_score: int) -> float:
    """
    Conservative repair estimate.
    Heuristic: $25/sqft base, +25% if pre-1960, +50% if heavy distress.
    Replace with your own walkthrough numbers once you have boots-on-ground.
    """
    if not sqft or sqft <= 0:
        return 0.0
    base = float(sqft) * config.ESTIMATED_REPAIR_PSF
    if year_built and year_built < 1960:
        base *= 1.25
    if distress_score >= 3:
        base *= 1.50
    elif distress_score >= 1:
        base *= 1.20
    return round(base, 0)


def calc_arv(est_market_val: float | None, sqft: float | None) -> float:
    """
    After-Repair Value estimate.
    Default to RentCast/comp estimate. If missing, fall back to sqft × $150.
    """
    if est_market_val and est_market_val > 0:
        return float(est_market_val)
    if sqft and sqft > 0:
        return float(sqft) * 150.0
    return 0.0


def calc_mao(arv: float, repair: float) -> float:
    """
    Maximum Allowable Offer = (ARV × 0.70) − repairs.
    The most a flipper can pay and still hit a 30% margin after costs.
    """
    if arv <= 0:
        return 0.0
    return round((arv * config.SEVENTY_PCT_RULE) - repair, 0)


def calc_discount_pct(list_price: float, est_market_val: float) -> float:
    """How far below market the listing is, as a percentage."""
    if not est_market_val or est_market_val <= 0 or not list_price:
        return 0.0
    return round(((est_market_val - list_price) / est_market_val) * 100, 1)


def score_distress(description: str) -> tuple[int, list[str]]:
    """
    Count distress keywords in the listing description.
    Returns (count, matched_terms).
    """
    if not description:
        return 0, []
    desc_lower = description.lower()
    matches = [kw for kw in config.DISTRESS_KEYWORDS if kw in desc_lower]
    return len(matches), matches


def deal_score(lead: dict) -> int:
    """
    Composite score from 0–100 ranking each lead.

    Weights:
      - Discount to market value : 40 pts
      - List price ≤ MAO         : 30 pts
      - Distress signals         : 20 pts
      - Property fundamentals    : 10 pts
    """
    score = 0
    list_price = lead.get("list_price") or 0
    arv = lead.get("arv_estimate") or 0
    mao = lead.get("mao") or 0
    discount = lead.get("discount_pct") or 0
    distress = lead.get("distress_score") or 0
    beds = lead.get("beds") or 0
    sqft = lead.get("sqft") or 0

    # 1. Discount to market (0-40 pts)
    if discount >= 40:    score += 40
    elif discount >= 30:  score += 32
    elif discount >= 20:  score += 22
    elif discount >= 15:  score += 14
    elif discount >= 10:  score += 8

    # 2. Hits the 70% Rule (0-30 pts)
    if mao > 0 and list_price > 0:
        if list_price <= mao:
            score += 30
        elif list_price <= mao * 1.10:
            score += 20
        elif list_price <= mao * 1.20:
            score += 10

    # 3. Distress signals (0-20 pts)
    if distress >= 5:   score += 20
    elif distress >= 3: score += 15
    elif distress >= 2: score += 10
    elif distress >= 1: score += 5

    # 4. Fundamentals (0-10 pts)
    if beds >= 3:    score += 4
    if sqft >= 1200: score += 3
    if arv >= 100_000 and list_price <= 150_000: score += 3

    return min(score, 100)


def analyze(lead: dict) -> dict:
    """
    Run all calculations against a raw lead and enrich it in place.
    Returns the enriched lead dict.
    """
    # Distress scoring from description
    d_score, d_terms = score_distress(lead.get("description", ""))
    lead["distress_score"] = d_score
    lead["distress_terms"] = ",".join(d_terms)

    # ARV
    lead["arv_estimate"] = calc_arv(
        lead.get("est_market_val"),
        lead.get("sqft"),
    )

    # Repair estimate
    lead["repair_estimate"] = calc_repair_estimate(
        lead.get("sqft"),
        lead.get("year_built"),
        d_score,
    )

    # MAO
    lead["mao"] = calc_mao(lead["arv_estimate"], lead["repair_estimate"])

    # Discount %
    lead["discount_pct"] = calc_discount_pct(
        lead.get("list_price") or 0,
        lead["arv_estimate"],
    )

    # Composite score
    lead["deal_score"] = deal_score(lead)

    # Hot flag
    lead["is_hot"] = 1 if (
        lead["deal_score"] >= 60 or
        lead["discount_pct"] >= config.TARGET_DISCOUNT_PCT or
        (lead.get("list_price") or 0) <= lead["mao"] > 0
    ) else 0

    return lead


def passes_filters(lead: dict) -> bool:
    """Hard filters before scoring — skip junk listings."""
    lp = lead.get("list_price") or 0
    if lp < config.MIN_LIST_PRICE or lp > config.MAX_LIST_PRICE:
        return False
    beds = lead.get("beds") or 0
    if beds and beds < config.MIN_BEDROOMS:
        return False
    sqft = lead.get("sqft") or 0
    if sqft and (sqft < config.MIN_SQFT or sqft > config.MAX_SQFT):
        return False
    yb = lead.get("year_built") or 0
    if yb and yb < config.MIN_YEAR_BUILT:
        return False
    return True
