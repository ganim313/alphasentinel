"""
Vectorized Minervini Stage 2 & VCP Pattern Screener (High Performance Vectorized).
Implements the institutional Minervini Trend Template, Volatility Contraction Pattern (VCP),
and Relative Strength vs NIFTY 500 benchmark.
"""

import os
import logging
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

# Load strategy config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "strategy.yaml"
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        strategy_config = yaml.safe_load(f) or {}
else:
    strategy_config = {}

SCREENING_CONFIG = strategy_config.get("screening", {})
MINERVINI_CONFIG = SCREENING_CONFIG.get("minervini", {})
VCP_CONFIG = SCREENING_CONFIG.get("vcp", {})
QUANT_ALPHA_CONFIG = SCREENING_CONFIG.get("quantitative_alpha", {})

logger = logging.getLogger(__name__)

def evaluate_minervini_vcp_pattern(symbol: str, conn, live_price: float = None, live_volume: int = None) -> Optional[Dict[str, Any]]:
    res = evaluate_minervini_vcp_batch([symbol], conn, {symbol: live_price} if live_price else {}, {symbol: live_volume} if live_volume else {})
    return res[0] if res else None

def evaluate_minervini_vcp_batch(
    symbols: List[str], 
    conn, 
    live_prices: Dict[str, float] = None, 
    live_volumes: Dict[str, int] = None, 
    batch_size: int = 500
) -> List[Dict[str, Any]]:
    """
    Evaluates multiple stocks in chunks for Minervini Stage 2 and VCP contraction using vectorized rolling calculations.
    Slippage floor is set to 50bps (0.005). Eliminates N+1 DB queries by pulling portfolio equity upfront.
    """
    if not symbols:
        return []
        
    live_prices = live_prices or {}
    live_volumes = live_volumes or {}
    
    # If live_prices are not fully provided, fetch from Fyers
    missing_symbols = [s for s in symbols if s not in live_prices]
    if missing_symbols:
        try:
            from src.ingestion.fyers_client import fyers_client
            fyers_quotes = fyers_client.get_live_quotes(missing_symbols)
            live_prices.update(fyers_quotes)
        except Exception as e:
            logger.error(f"Failed to fetch Fyers quotes in screener: {e}")
    
    # Quantitative Alpha Configurations
    benchmark_symbol = QUANT_ALPHA_CONFIG.get("benchmark_symbol", "^NSEI") # Use NIFTY 50 via yfinance
    regime_dma_period = QUANT_ALPHA_CONFIG.get("regime_dma_period", 50)
    rs_period = QUANT_ALPHA_CONFIG.get("rs_period", 60)
    
    # 1. Evaluate Regime Filter First via canonical BenchmarkProvider
    regime_passed = False
    benchmark_rs_data = None
    try:
        from src.utils.benchmark_provider import get_market_regime, get_benchmark_returns
        regime_passed = (get_market_regime() != 0)
        if not regime_passed:
            logger.info(f"Regime Filter active: {benchmark_symbol} below {regime_dma_period} DMA. Evaluating candidates under RS bypass rule.")
        bm_rets = get_benchmark_returns()
        if len(bm_rets) >= rs_period:
            benchmark_rs_data = float((1 + bm_rets.tail(rs_period)).prod() - 1.0)
    except Exception as e:
        logger.error(f"Failed to fetch canonical benchmark: {e}. Failing closed (regime_passed=False).")
        return []

    # Pre-fetch total portfolio equity ONCE outside the symbol loop (fixes N+1 DB query flaw)
    try:
        from src.ingestion.fyers_client import fyers_client
        from src.config.settings import settings
        base_cap = fyers_client.get_funds() if fyers_client else settings.ALGO_ALLOCATED_CAPITAL
    except Exception:
        base_cap = 1000000.0

    try:
        real_res = conn.execute("SELECT SUM(realized_pnl) FROM positions WHERE status IN ('CLOSED', 'STOPPED_OUT', 'TARGET_REACHED')").fetchone()
        unreal_res = conn.execute("SELECT SUM(unrealized_pnl) FROM positions WHERE status = 'OPEN'").fetchone()
        curr_eq = base_cap + (real_res[0] or 0.0) + (unreal_res[0] or 0.0)
    except Exception:
        curr_eq = base_cap
    assumed_capital = curr_eq * 0.12 # Max position size 12%
            
    results = []
    
    for i in range(0, len(symbols), batch_size):
        chunk_symbols = symbols[i:i + batch_size]
        
        placeholders = ",".join(["?"] * len(chunk_symbols))
        query = f"""
            SELECT symbol, trade_date, close_price, high_price, low_price, total_traded_qty, delivery_pct
            FROM bhavcopy_daily
            WHERE symbol IN ({placeholders}) AND series != 'BE' AND COALESCE(is_asm, FALSE) = FALSE AND COALESCE(is_gsm, FALSE) = FALSE
            ORDER BY trade_date ASC;
        """
        
        df = conn.execute(query, chunk_symbols).df()
        if df.empty:
            continue
            
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # Limit ffill to 5 days to prevent halted/delisted stocks from passing as contractions
        close_df = df.pivot(index='trade_date', columns='symbol', values='close_price').ffill(limit=5)
        high_df = df.pivot(index='trade_date', columns='symbol', values='high_price').ffill(limit=5)
        low_df = df.pivot(index='trade_date', columns='symbol', values='low_price').ffill(limit=5)
        vol_df = df.pivot(index='trade_date', columns='symbol', values='total_traded_qty').fillna(0)
        
        # Vectorized Moving Averages with STRICT min_periods to prevent young listings from passing false trends
        sma_10 = close_df.rolling(10, min_periods=5).mean()
        sma_21 = close_df.rolling(21, min_periods=10).mean()
        sma_50 = close_df.rolling(50, min_periods=50).mean()
        sma_150 = close_df.rolling(150, min_periods=150).mean()
        sma_200 = close_df.rolling(200, min_periods=150).mean()
        sma_200_lookback = close_df.rolling(200, min_periods=130).mean()
        
        trend_period = MINERVINI_CONFIG.get("trend_dma_period", 21)
        
        # 52-Week (252-day) Lookback Max & Min (using true intraday High and Low)
        high_252d = high_df.tail(252).max()
        low_252d = low_df.tail(252).min()
        
        low_mult = MINERVINI_CONFIG.get("60d_low_multiplier", MINERVINI_CONFIG.get("52w_low_multiplier", 1.25))
        high_mult = MINERVINI_CONFIG.get("60d_high_multiplier", MINERVINI_CONFIG.get("52w_high_multiplier", 0.75))
        vol_dryup_mult = VCP_CONFIG.get("volume_dryup_multiplier", 0.85)
        
        vol_20d = vol_df.tail(20).mean()
        vol_5d = vol_df.tail(5).mean()
        
        for sym in chunk_symbols:
            if sym not in close_df.columns:
                continue
                
            sym_close = close_df[sym].dropna()
            if len(sym_close) < 150:
                continue
                
            current_price = live_prices.get(sym)
            if current_price is None:
                current_price = sym_close.iloc[-1]
                
            if current_price < 20.0:
                continue
                
            if len(sma_10[sym].dropna()) == 0 or len(sma_21[sym].dropna()) == 0 or len(sma_50[sym].dropna()) < trend_period:
                continue

            # Core Minervini Moving Average Hierarchy (Strict Stage 2)
            sma_200_valid = sma_200[sym].dropna()
            if len(sma_150[sym].dropna()) == 0 or len(sma_200_valid) == 0:
                continue # Must have sufficient 200-SMA history (min_periods=150)
                
            if len(sma_200_valid) >= 20:
                sma_200_prev = sma_200_valid.iloc[-20]
            else:
                lb_valid = sma_200_lookback[sym].dropna()
                sma_200_prev = lb_valid.iloc[-min(20, len(lb_valid))]
            sma_200_curr = sma_200_valid.iloc[-1]
            if pd.isna(sma_200_prev) or pd.isna(sma_200_curr):
                continue

            c0 = current_price > sma_50[sym].iloc[-1]
            c1 = current_price > sma_150[sym].iloc[-1] and current_price > sma_200_curr
            c2 = (sma_150[sym].iloc[-1] >= sma_200_curr) if len(sym_close) == 150 else (sma_150[sym].iloc[-1] > sma_200_curr)
            c3 = sma_200_curr >= sma_200_prev # 200-day moving average must be trending upward for 1 month
            c4 = sma_50[sym].iloc[-1] > sma_150[sym].iloc[-1] and sma_50[sym].iloc[-1] > sma_200_curr
            
            # 52-Week High & Low Criteria
            if pd.isna(low_252d[sym]) or pd.isna(high_252d[sym]) or low_252d[sym] <= 0 or high_252d[sym] <= 0:
                continue
            c5 = current_price >= (low_252d[sym] * low_mult)
            c6 = current_price >= (high_252d[sym] * high_mult)
            
            if not (c0 and c1 and c2 and c3 and c4 and c5 and c6):
                continue
                
            # Disqualify halted / suspended stocks (must have active trading volume)
            if vol_20d[sym] <= 0 or vol_5d[sym] <= 0:
                continue

            # ADTV Calculation
            adtv_20d = float(np.nan_to_num((close_df[sym].tail(20) * vol_df[sym].tail(20)).mean()))
                
            # VCP Volatility Contraction & Volume Dry-up
            volume_dryup = vol_5d[sym] < (vol_20d[sym] * vol_dryup_mult)
            if not volume_dryup:
                continue
            
            returns = sym_close.pct_change().dropna()
            if len(returns) < 30:
                continue
            volatility_10d = returns.tail(10).std()
            volatility_30d = returns.tail(30).std()
            if volatility_30d <= 0:
                continue
            volatility_contraction = volatility_10d < (volatility_30d * 0.75)

            # High-Low Contraction Depth Check (c1..c4 using true intraday high_df and low_df, including c2)
            sym_high = high_df[sym].dropna()
            sym_low = low_df[sym].dropna()
            if len(sym_high) < 40 or len(sym_low) < 40:
                continue

            def _hl_depth(h_slice: pd.Series, l_slice: pd.Series) -> float:
                if len(h_slice) == 0 or len(l_slice) == 0:
                    return 0.0
                h_max = float(h_slice.max())
                l_min = float(l_slice.min())
                return (h_max - l_min) / h_max if h_max > 0 else 0.0

            c1_depth = _hl_depth(sym_high.iloc[-40:-20], sym_low.iloc[-40:-20])
            c2_depth = _hl_depth(sym_high.iloc[-20:-10], sym_low.iloc[-20:-10])
            c3_depth = _hl_depth(sym_high.iloc[-10:-5], sym_low.iloc[-10:-5])
            c4_depth = _hl_depth(sym_high.iloc[-5:], sym_low.iloc[-5:])
            hl_contraction = (
                c2_depth <= c1_depth * 1.05
                and c3_depth <= c2_depth * 1.05
                and c4_depth <= c3_depth * 1.05
                and c4_depth <= c1_depth
            )

            if not (volatility_contraction and hl_contraction):
                continue
            
            # Relative Strength Calculation vs Benchmark
            rs_score = 0.0
            if len(sym_close) >= rs_period and benchmark_rs_data is not None:
                stock_return = (current_price - sym_close.iloc[-rs_period]) / sym_close.iloc[-rs_period]
                rs_score = round((stock_return - benchmark_rs_data) * 100, 2)
            
            if not regime_passed:
                RS_BYPASS_THRESHOLD = 15.0
                if rs_score > RS_BYPASS_THRESHOLD and volume_dryup:
                    logger.info(f"[{sym}] Regime BYPASS: RS={rs_score:.1f} > {RS_BYPASS_THRESHOLD} + vol dryup confirmed. Allowing at 50% size.")
                    regime_bypass_size_reduction = 0.5
                else:
                    continue
            else:
                regime_bypass_size_reduction = 1.0
            
            # Calculate Slippage Impact Cost
            impact_cost = (assumed_capital / adtv_20d) * 0.1 if adtv_20d > 0 else 0.05
            expected_slippage_pct = min(max(0.005, impact_cost), 0.05)
            sim_portfolio_val = assumed_capital * (1 - expected_slippage_pct)
            
            sym_df = df[df['symbol'] == sym]
            delivery_latest = float(sym_df["delivery_pct"].iloc[-1]) if not sym_df.empty and "delivery_pct" in sym_df.columns and pd.notna(sym_df["delivery_pct"].iloc[-1]) else 0.0
            
            # Authentic Minervini Consolidation Base Pivot High (from intraday high_df, not close_df)
            pivot_price = float(high_df[sym].tail(20).max())
            trigger_price = round(pivot_price, 2)
            
            results.append({
                "symbol": sym,
                "pattern_type": "MINERVINI_VCP_STAGE2",
                "current_price": float(current_price),
                "trigger_price": trigger_price,
                "sma_10": round(sma_10[sym].iloc[-1], 2),
                "sma_21": round(sma_21[sym].iloc[-1], 2),
                "sma_50": round(sma_50[sym].iloc[-1], 2),
                "sma_150": round(float(sma_150[sym].iloc[-1]), 2),
                "sma_200": round(float(sma_200_curr), 2),
                "pct_above_52w_low": round((current_price - low_252d[sym]) / low_252d[sym] * 100, 1) if low_252d[sym] > 0 else 0.0,
                "pct_from_52w_high": round((high_252d[sym] - current_price) / high_252d[sym] * 100, 1) if high_252d[sym] > 0 else 0.0,
                "volume_dryup": bool(volume_dryup),
                "delivery_pct": delivery_latest,
                "regime_bypass_size_reduction": regime_bypass_size_reduction,
                "sim_slippage_portfolio_val": round(sim_portfolio_val, 2),
                "adtv_crores": round(adtv_20d / 10000000, 2) if adtv_20d > 0 else 0.0,
                "rs_score": rs_score
            })
            
    results.sort(key=lambda x: x.get("rs_score", 0), reverse=True)
    return results


# Aliases for Stage 2 VCP evaluators
evaluate_vcp_stage2 = evaluate_minervini_vcp_pattern
evaluate_vcp_stage2_batch = evaluate_minervini_vcp_batch
