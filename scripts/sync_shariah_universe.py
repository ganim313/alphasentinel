"""
AlphaSentinel — Offline Shariah Universe Sync Script.
Standalone monthly/quarterly batch script that screens fundamental data
against the 6 Mufti Taqi Usmani Shariah financial ratio gates and populates
the DuckDB `shariah_universe` table.

Runs completely offline without making live network calls or blocking the EOD pipeline.
"""

import sys
import os
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.db.session import get_read_connection
from src.db.queue_writer import db_write, db_write_many
from src.screening.shariah_filter import check_shariah_compliance

logger = logging.getLogger("sync_shariah_universe")


def init_shariah_universe_table(recreate: bool = False) -> None:
    """
    Creates or ensures the shariah_universe table in DuckDB.
    """
    if recreate:
        logger.warning("Dropping existing shariah_universe table...")
        db_write("DROP TABLE IF EXISTS shariah_universe;", sync=True)

    query = """
    CREATE TABLE IF NOT EXISTS shariah_universe (
        symbol VARCHAR PRIMARY KEY,
        fyers_symbol VARCHAR,
        sector VARCHAR,
        debt_to_assets DOUBLE,
        cash_to_assets DOUBLE,
        interest_income_ratio DOUBLE,
        illiquid_ratio DOUBLE,
        is_compliant BOOLEAN,
        purification_ratio DOUBLE,
        sync_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """
    db_write(query, sync=True)
    logger.info("shariah_universe table initialized successfully.")


def sync_shariah_universe(recreate_table: bool = False) -> Dict[str, Any]:
    """
    Main offline batch sync routine.
    1. Reads all cached fundamental records from fundamentals_cache.
    2. Runs each through check_shariah_compliance() across all 6 Taqi Usmani gates.
    3. Computes purification_ratio = max(0.0, float(data.get("interest_income_ratio") or 0.0)).
    4. Populates shariah_universe table in DuckDB.
    
    Returns:
        Dict summarizing sync metrics.
    """
    init_shariah_universe_table(recreate=recreate_table)

    logger.info("Reading candidates from fundamentals_cache...")
    with get_read_connection() as conn:
        cache_rows = conn.execute("""
            SELECT symbol, fundamentals_json 
            FROM fundamentals_cache 
            ORDER BY symbol ASC
        """).fetchall()

    if not cache_rows:
        logger.warning("fundamentals_cache is empty! No stocks to sync.")
        return {
            "total_candidates": 0,
            "compliant_count": 0,
            "non_compliant_count": 0,
            "inserted_count": 0,
            "records": []
        }

    total_candidates = len(cache_rows)
    logger.info(f"Loaded {total_candidates} candidates from fundamentals_cache.")

    records_to_insert = []
    compliant_symbols = []
    non_compliant_symbols = []
    now_utc = datetime.now(timezone.utc)

    for symbol, fundamentals_json in cache_rows:
        symbol = str(symbol).strip().upper()
        try:
            data = json.loads(fundamentals_json)
        except Exception as e:
            logger.error(f"Failed to parse fundamentals_json for {symbol}: {e}")
            continue

        sector = str(data.get("sector_name") or data.get("sector") or "").strip()
        fyers_symbol = f"NSE:{symbol}-EQ"

        # Evaluate against all 6 Mufti Taqi Usmani gates
        is_compliant, reason = check_shariah_compliance(data, sector_name=sector)

        debt_to_assets = float(data.get("debt_to_assets") or 0.0)
        cash_to_assets = float(data.get("cash_to_assets") or 0.0)
        interest_income_ratio = float(data.get("interest_income_ratio") or 0.0)
        illiquid_ratio = float(data.get("illiquid_ratio") or 0.0)

        # Purification ratio formula per AAOIFI & Justice Mufti Taqi Usmani rulings
        purification_ratio = max(0.0, interest_income_ratio)

        if is_compliant:
            compliant_symbols.append(symbol)
        else:
            non_compliant_symbols.append((symbol, reason))
            logger.warning(f"Stock {symbol} failed Shariah gate: {reason}")

        record = (
            symbol,
            fyers_symbol,
            sector,
            debt_to_assets,
            cash_to_assets,
            interest_income_ratio,
            illiquid_ratio,
            is_compliant,
            purification_ratio,
            now_utc
        )
        records_to_insert.append(record)

    # Bulk upsert into shariah_universe
    upsert_query = """
    INSERT INTO shariah_universe (
        symbol, fyers_symbol, sector, debt_to_assets, cash_to_assets,
        interest_income_ratio, illiquid_ratio, is_compliant,
        purification_ratio, sync_timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT (symbol) DO UPDATE SET
        fyers_symbol = excluded.fyers_symbol,
        sector = excluded.sector,
        debt_to_assets = excluded.debt_to_assets,
        cash_to_assets = excluded.cash_to_assets,
        interest_income_ratio = excluded.interest_income_ratio,
        illiquid_ratio = excluded.illiquid_ratio,
        is_compliant = excluded.is_compliant,
        purification_ratio = excluded.purification_ratio,
        sync_timestamp = excluded.sync_timestamp;
    """

    db_write_many(upsert_query, records_to_insert)

    compliant_count = len(compliant_symbols)
    non_compliant_count = len(non_compliant_symbols)

    logger.info("=" * 60)
    logger.info("OFFLINE SHARIAH UNIVERSE SYNC COMPLETED")
    logger.info(f"Total Scanned:      {total_candidates}")
    logger.info(f"Verified Compliant: {compliant_count}")
    logger.info(f"Non-Compliant:      {non_compliant_count}")
    logger.info(f"Records Upserted:   {len(records_to_insert)}")
    logger.info("=" * 60)

    return {
        "total_candidates": total_candidates,
        "compliant_count": compliant_count,
        "non_compliant_count": non_compliant_count,
        "inserted_count": len(records_to_insert),
        "compliant_symbols": compliant_symbols,
        "non_compliant_symbols": non_compliant_symbols
    }


def main():
    parser = argparse.ArgumentParser(description="AlphaSentinel Offline Shariah Universe Sync Utility")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate shariah_universe table")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    result = sync_shariah_universe(recreate_table=args.recreate)
    print(f"\n[SUCCESS] Synced {result['compliant_count']} compliant stocks to shariah_universe.")


if __name__ == "__main__":
    main()
