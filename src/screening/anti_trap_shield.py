"""
6-Layer Pre-Flight Anti-Trap Shield Module.
Blocks over-extended, climaxed, or distribution setups BEFORE the LLMs are invoked.
"""

import logging
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)


def compute_sector_median_pe_map(conn=None) -> Dict[str, float]:
    """
    Computes cross-sectional median P/E per sector from fundamentals_cache.
    """
    import json
    sector_pes: Dict[str, list] = {}

    def _collect(c):
        rows = c.execute("SELECT fundamentals_json FROM fundamentals_cache").fetchall()
        for (f_json,) in rows:
            try:
                data = json.loads(f_json) if isinstance(f_json, str) else (f_json or {})
                sec = str(data.get("sector_name") or "").strip()
                pe = float(data.get("pe_ratio") or 0.0)
                if sec and pe > 0.0:
                    sector_pes.setdefault(sec, []).append(pe)
            except Exception:
                continue

    try:
        if conn is not None:
            _collect(conn)
        else:
            with get_read_connection() as read_conn:
                _collect(read_conn)
    except Exception as e:
        logger.warning(f"Failed to compute sector median P/E map: {e}")

    return {sec: round(float(np.median(vals)), 2) for sec, vals in sector_pes.items() if vals}


def evaluate_anti_trap_shield(
    symbol: str, 
    candidate: Dict[str, Any], 
    fundamentals: Dict[str, Any],
    live_price: float = None,
    live_volume: int = None,
    sector_median_pe: float = None
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Executes the 6-layer pre-flight anti-trap checks.
    Returns: (is_passed, reason_code, trap_metrics)
    """
    with get_read_connection() as conn:
        df = conn.execute("""
            SELECT trade_date, open_price, high_price, low_price, close_price, total_traded_qty, delivery_pct
            FROM bhavcopy_daily
            WHERE symbol = ?
            ORDER BY trade_date ASC;
        """, (symbol,)).df()

    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
    if len(df) < 50:
        return False, "INSUFFICIENT_HISTORY_DATA", {}

    close = df["close_price"].values
    volume = df["total_traded_qty"].values
    delivery = df["delivery_pct"].values if "delivery_pct" in df else np.zeros(len(df))

    current_price = live_price if live_price is not None else close[-1]
    sma_50 = candidate.get("sma_50") or np.mean(close[-50:])
    
    if "trigger_price" not in candidate:
        return False, "TRAP_L1_MISSING_TRIGGER_PRICE", {"rule": "Missing trigger_price, failing closed (defensive)."}
    pivot_price = candidate["trigger_price"]

    # -------------------------------------------------------------
    # Layer 1: Pivot Extension Trap (Max 5% above pivot)
    # -------------------------------------------------------------
    if pivot_price <= 0:
        return False, "TRAP_L1_INVALID_PIVOT", {"rule": "Pivot price is zero or negative."}

    pivot_extension_pct = ((current_price - pivot_price) / pivot_price) * 100
    if pivot_extension_pct > 5.0:
        return False, "TRAP_L1_PIVOT_EXTENDED", {
            "pivot_extension_pct": pivot_extension_pct,
            "rule": "Cannot buy more than 5% above base breakout pivot."
        }

    # -------------------------------------------------------------
    # Layer 2: Climax Run Trap (3 simultaneous conditions: advance, vol climax, upper wick)
    # -------------------------------------------------------------
    price_10d_ago = close[-10] if len(close) >= 10 else close[0]
    run_10d_pct = ((current_price - price_10d_ago) / price_10d_ago) * 100
    
    vol_10d_avg = np.mean(volume[-10:]) if len(volume) >= 10 else np.mean(volume)
    recent_volume = live_volume if live_volume is not None else volume[-1]
    is_vol_climax = recent_volume > (vol_10d_avg * 3.0)
    
    high_price = df["high_price"].iloc[-1]
    low_price = df["low_price"].iloc[-1]
    if live_price is not None:
        high_price = max(high_price, live_price)
        low_price = min(low_price, live_price)
        
    candle_range = high_price - low_price
    is_upper_wick = (high_price - current_price) > (candle_range * 0.5) if candle_range > 0 else False
    
    if run_10d_pct > 40.0 and is_vol_climax and is_upper_wick:
        return False, "TRAP_L2_CLIMAX_REJECTION", {
            "run_10d_pct": run_10d_pct,
            "rule": "Climax parabolic move with volume climax and upper wick rejection."
        }
        
    # Layer 2B: Intraday Churning Trap (High volume but low delivery)
    recent_delivery = delivery[-1] if len(delivery) > 0 and pd.notna(delivery[-1]) else 0.0
    if recent_volume > (vol_10d_avg * 2.0) and recent_delivery > 0 and recent_delivery < 15.0:
        return False, "TRAP_L2B_INTRADAY_CHURNING", {
            "delivery_pct": recent_delivery,
            "rule": "High volume breakout but extreme low delivery indicates intraday operator churning."
        }

    # -------------------------------------------------------------
    # Layer 3: Moving Average Distance Guard (20/50 DMA checks)
    # -------------------------------------------------------------
    sma_20 = np.mean(close[-20:]) if len(close) >= 20 else current_price
    
    dist_from_20sma_pct = ((current_price - sma_20) / sma_20) * 100
    dist_from_50sma_pct = ((current_price - sma_50) / sma_50) * 100
    
    if dist_from_20sma_pct > 15.0 or dist_from_50sma_pct > 30.0:
        return False, "TRAP_L3_EXTENDED_FROM_MA", {
            "dist_20": dist_from_20sma_pct,
            "dist_50": dist_from_50sma_pct,
            "rule": "Price over-extended from short-term moving averages (15% from 20, 30% from 50)."
        }

    # -------------------------------------------------------------
    # Layer 4: Promoter Pledge Trend Guard
    # -------------------------------------------------------------
    pledge_trend_3m = fundamentals.get("pledge_trend_3m") or 0.0
    if float(pledge_trend_3m) > 0.0:
        return False, "TRAP_L4_PLEDGE_INCREASE", {
            "pledge_trend_3m": pledge_trend_3m,
            "rule": "Any increase in promoter pledging over the last 3 months is an instant rejection."
        }
        
    pledged_pct = fundamentals.get("promoter_pledged_pct") or 0.0
    if float(pledged_pct) > 15.0:
        return False, "TRAP_L4B_HIGH_PLEDGE", {
            "promoter_pledged_pct": pledged_pct,
            "rule": "Promoter pledging exceeds absolute ceiling of 15%."
        }

    # -------------------------------------------------------------
    # Layer 5: P/E Overvaluation Filter (Cross-Sectional Sector Median P/E)
    # -------------------------------------------------------------
    eff_sector_median_pe = sector_median_pe
    if eff_sector_median_pe is None:
        eff_sector_median_pe = fundamentals.get("sector_median_pe")
    if eff_sector_median_pe is None:
        sec = str(fundamentals.get("sector_name") or fundamentals.get("sector") or "").strip()
        if sec:
            try:
                pe_map = compute_sector_median_pe_map()
                eff_sector_median_pe = pe_map.get(sec)
            except Exception:
                pass
    pe_ratio = fundamentals.get("pe_ratio")
    if (
        eff_sector_median_pe is not None
        and float(eff_sector_median_pe) > 0.0
        and pe_ratio is not None
        and float(pe_ratio) > 0.0
    ):
        if float(pe_ratio) > 2.5 * float(eff_sector_median_pe):
            return False, "TRAP_L5_PE_OVERVALUATION", {
                "pe_ratio": float(pe_ratio),
                "sector_median_pe": float(eff_sector_median_pe),
                "rule": "Stock P/E exceeds 2.5x cross-sectional sector median P/E."
            }

    # -------------------------------------------------------------
    # Layer 6: FOMO Saturation (News Headline Volume + Price Confirmation)
    # -------------------------------------------------------------
    raw_news_count = fundamentals.get("recent_news_count")
    price_3d_ago = close[-3] if len(close) >= 3 else close[0]
    run_3d_pct = ((current_price - price_3d_ago) / price_3d_ago) * 100
    
    if raw_news_count is None:
        # Scraper failed / rate limited (HTTP 429) — conservatively reject if price has surged
        if run_3d_pct > 15.0:
            return False, "TRAP_L6_DEGRADED_MODE_FOMO_SUSPECTED", {
                "recent_news_count": "SCRAPE_FAILED_OR_429",
                "run_3d_pct": round(run_3d_pct, 2),
                "rule": "Scraper unavailable + 3-day price run > 15% — conservative rejection."
            }
    elif int(raw_news_count) >= 3 and run_3d_pct > 15.0:
        return False, "TRAP_L6_FOMO_NEWS_SATURATION", {
            "recent_news_count": raw_news_count,
            "run_3d_pct": round(run_3d_pct, 2),
            "rule": "FOMO spike driven by multiple recent news headlines (retail trap)."
        }

    return True, "PASSED_ALL_ANTI_TRAP_LAYERS", {
        "pivot_extension_pct": round(pivot_extension_pct, 2),
        "run_10d_pct": round(run_10d_pct, 2),
        "dist_from_50sma_pct": round(dist_from_50sma_pct, 2)
    }
