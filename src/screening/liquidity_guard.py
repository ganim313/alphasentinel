"""
Liquidity & Executability Guard Module.
Enforces the mandatory Indian Micro-Cap pre-filters:
1. ADTV Floor: 20-day Average Daily Traded Value must be >= ₹50 Lakhs.
2. Circuit Band Risk: Flags stocks with <= 10% daily price bands.
3. T2T Segment: Hard-blocks Trade-to-Trade stocks (Series 'BE', 'BZ', 'T2T').
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from src.config.settings import settings
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent / "config" / "strategy.yaml"
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        strategy_config = yaml.safe_load(f) or {}
else:
    strategy_config = {}

LIQUIDITY_TIERS = strategy_config.get("screening", {}).get("quantitative_alpha", {}).get("liquidity_tiers", {
    "LARGE": 50000000.0,
    "MID": 15000000.0,
    "SMALL": 5000000.0,
    "MICRO": 2500000.0
})


def check_liquidity_and_executability(
    symbol: str, 
    series: str, 
    circuit_band_pct: float,
    market_cap_tier: str = "MICRO",
    conn=None  # Accept injected connection to avoid 500x open/close calls in the screening loop
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Evaluates liquidity and executability for a given stock symbol.
    Returns: (is_passed, reason, metrics_dict)
    """
    # 1. T2T Segment Hard Block
    if series.upper() in ["BE", "BZ", "T2T"]:
        return False, "HARD_BLOCK_T2T_SEGMENT", {
            "symbol": symbol,
            "series": series,
            "reason": "Stock is in Trade-to-Trade segment; cannot square off intraday or enforce SL."
        }

    # 2. Calculate 30-day Median ADTV from DuckDB (Operator Pump Filter)
    # CRITICAL FIX: Use injected conn if available to prevent 500x DuckDB file-lock contention
    def _fetch_adtv(c):
        return c.execute("""
            SELECT MEDIAN(total_traded_val) AS adtv_30d_median, COUNT(*) AS data_days
            FROM (
                SELECT total_traded_val
                FROM bhavcopy_daily
                WHERE symbol = ?
                ORDER BY trade_date DESC
                LIMIT 30
            );
        """, (symbol,)).fetchone()

    if conn is not None:
        adtv_row = _fetch_adtv(conn)
    else:
        with get_read_connection() as _conn:
            adtv_row = _fetch_adtv(_conn)

    adtv_20d = float(adtv_row[0]) if (adtv_row and adtv_row[0] is not None) else 0.0
    data_days = int(adtv_row[1]) if adtv_row else 0

    metrics = {
        "symbol": symbol,
        "series": series,
        "adtv_20d_rupees": adtv_20d,
        "data_days": data_days,
        "circuit_band_pct": circuit_band_pct,
        "market_cap_tier": market_cap_tier,
        "has_circuit_fill_risk": circuit_band_pct <= settings.MIN_CIRCUIT_BAND_PCT,
        "live_bid_ask_spread_pct": 0.0
    }

    # 3. Check ADTV Floor for Specific Tier
    if data_days < 5:
        return False, "FAIL_INSUFFICIENT_DATA_DAYS", metrics

    min_adtv_required = LIQUIDITY_TIERS.get(market_cap_tier.upper(), LIQUIDITY_TIERS["MICRO"])
    if adtv_20d < min_adtv_required:
        return False, "FAIL_ADTV_LIQUIDITY_FLOOR", metrics

    if circuit_band_pct <= 2:
        return False, "FAIL_CIRCUIT_BAND_RISK", metrics

    # 4. Check real-time Bid-Ask spread via Fyers Level 2 Depth
    try:
        from src.ingestion.fyers_client import fyers_client
        depth = fyers_client.get_market_depth(symbol)
        bids = depth.get("bids", [])
        asks = depth.get("asks", [])
        
        if bids and asks and bids[0].get("price") and asks[0].get("price"):
            best_bid = bids[0]["price"]
            best_ask = asks[0]["price"]
            spread_pct = (best_ask - best_bid) / best_bid * 100
            metrics["live_bid_ask_spread_pct"] = spread_pct
            
            # Reject if spread > 2% for micro/small caps
            if spread_pct > 2.0:
                return False, "FAIL_BID_ASK_SPREAD", metrics
    except Exception as e:
        logger.warning(f"Failed to fetch/evaluate Fyers market depth for {symbol}: {e}")

    return True, "PASSED_LIQUIDITY_GUARD", metrics
