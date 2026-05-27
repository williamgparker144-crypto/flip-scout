"""
FLIP SCRAPER — MAIN ORCHESTRATOR

Runs every registered scraper against every configured city, applies deal
analysis, persists results, and writes ranked CSV/JSON exports.

Usage:
    python main.py                  # Run all scrapers, all cities
    python main.py --hot-only       # Only show hot leads in report
    python main.py --stats          # Print database stats and exit
"""
import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

import config
import database
import analyzer
from scrapers import ALL_SCRAPERS

console = Console()


def banner():
    console.print("[bold cyan]" + "=" * 70 + "[/bold cyan]")
    console.print("[bold cyan]  FLIP SCRAPER — Distressed Property Lead Engine[/bold cyan]")
    console.print("[bold cyan]  TechSpatch Logistics  •  " + datetime.now().strftime("%Y-%m-%d %H:%M") + "[/bold cyan]")
    console.print("[bold cyan]" + "=" * 70 + "[/bold cyan]\n")


def run_all_scrapers() -> tuple[int, int]:
    """Returns (total_processed, new_added)."""
    database.init_db()
    total = 0
    new_count = 0

    for scraper_cls in ALL_SCRAPERS:
        scraper = scraper_cls()
        console.print(f"\n[bold yellow]▶ Running {scraper.SOURCE_NAME}[/bold yellow]")

        for target in config.TARGET_CITIES:
            try:
                leads = scraper.fetch_leads(target)
            except Exception as e:
                console.print(f"  [red]Scraper failed: {e}[/red]")
                continue

            for raw_lead in leads:
                if not analyzer.passes_filters(raw_lead):
                    continue
                enriched = analyzer.analyze(raw_lead)
                is_new = database.upsert_lead(enriched)
                total += 1
                if is_new:
                    new_count += 1

    return total, new_count


def export_results(hot_only: bool = False):
    """Write ranked results to CSV and JSON."""
    config.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    leads = database.get_hot_leads(500) if hot_only else database.get_all_leads(2000)

    if not leads:
        console.print("\n[yellow]No leads to export yet.[/yellow]")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "hot" if hot_only else "all"

    # CSV
    csv_path = config.EXPORTS_DIR / f"flip_leads_{suffix}_{stamp}.csv"
    fields = [
        "deal_score", "is_hot", "discount_pct", "source",
        "address", "city", "state", "zip_code",
        "list_price", "est_market_val", "arv_estimate",
        "repair_estimate", "mao",
        "beds", "baths", "sqft", "year_built",
        "distress_score", "distress_terms",
        "property_type", "status", "source_url", "last_seen",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for lead in leads:
            w.writerow(lead)

    # JSON
    json_path = config.EXPORTS_DIR / f"flip_leads_{suffix}_{stamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)

    console.print(f"\n[green]✓ Exported {len(leads)} leads[/green]")
    console.print(f"  CSV  → {csv_path}")
    console.print(f"  JSON → {json_path}")


def print_top_table(limit: int = 15):
    leads = database.get_hot_leads(limit)
    if not leads:
        console.print("\n[yellow]No hot leads yet. Run scrapers first.[/yellow]")
        return

    table = Table(title=f"\n🔥 TOP {len(leads)} HOT FLIP LEADS", show_lines=True)
    table.add_column("Score", justify="right", style="bold red")
    table.add_column("Disc%", justify="right", style="yellow")
    table.add_column("Address", style="cyan", overflow="fold")
    table.add_column("City/ST", style="cyan")
    table.add_column("Price", justify="right", style="green")
    table.add_column("MAO", justify="right", style="green")
    table.add_column("ARV", justify="right")
    table.add_column("Repair", justify="right")
    table.add_column("Source", style="dim")

    for ld in leads:
        table.add_row(
            str(ld.get("deal_score") or 0),
            f"{ld.get('discount_pct') or 0:.0f}%",
            (ld.get("address") or "")[:40],
            f"{ld.get('city') or ''}/{ld.get('state') or ''}",
            f"${ld.get('list_price') or 0:,.0f}",
            f"${ld.get('mao') or 0:,.0f}",
            f"${ld.get('arv_estimate') or 0:,.0f}",
            f"${ld.get('repair_estimate') or 0:,.0f}",
            ld.get("source", ""),
        )
    console.print(table)


def print_stats():
    s = database.stats()
    console.print(f"\n[bold]Database Statistics[/bold]")
    console.print(f"  Total leads tracked : {s['total']}")
    console.print(f"  Hot leads           : {s['hot']}")
    console.print(f"  By source:")
    for src, count in s["by_source"].items():
        console.print(f"    {src:25s} {count}")


def main():
    parser = argparse.ArgumentParser(description="Flip Scraper — distressed property lead engine")
    parser.add_argument("--hot-only",  action="store_true", help="Export only hot leads")
    parser.add_argument("--stats",     action="store_true", help="Show database stats and exit")
    parser.add_argument("--no-scrape", action="store_true", help="Skip scraping, just export current DB")
    parser.add_argument("--city",  type=str, default=None, help="Scout a single city by name (e.g. 'Fayetteville')")
    args = parser.parse_args()

    banner()

    if args.stats:
        print_stats()
        return

    if not args.no_scrape:
        if args.city:
            # Single-city mode — match by city name (case-insensitive)
            match = [t for t in config.TARGET_CITIES if t["city"].lower() == args.city.lower()]
            if not match:
                console.print(f"[red]City '{args.city}' not in target cities list.[/red]")
                return
            original = config.TARGET_CITIES
            config.TARGET_CITIES = match
            total, new_count = run_all_scrapers()
            config.TARGET_CITIES = original
        else:
            total, new_count = run_all_scrapers()
        console.print(f"\n[bold green]✓ Pass complete[/bold green]  •  processed: {total}  •  new: {new_count}")

    print_top_table(15)
    export_results(hot_only=args.hot_only)
    print_stats()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(0)
