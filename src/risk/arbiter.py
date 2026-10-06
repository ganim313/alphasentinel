"""
Deterministic Python Risk Arbiter & Position Sizer.
Pure mathematical risk allocation without LLM hallucination risk.
Uses ATR-based volatility sizing and Macro Target Cash Exposure caps.
"""

import math
import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Load strategy config
CONFIG_PATH = Path(__file__).parent.parent / "config" / "strategy.yaml"
with open(CONFIG_PATH, "r") as f:
    strategy_config = yaml.safe_load(f)
RISK_CONFIG = strategy_config.get("risk", {})


from src.db.session import get_read_connection

def calculate_deterministic_risk_and_position(
    symbol: str,
    trigger_price: float,
    current_price: Optional[float] = None,
    atr_14: float = 0.0,
    circuit_band: float = 20.0,
    macro_weather: Optional[Dict[str, Any]] = None,
    portfolio_capital_rupees: float = 10_00_000.0, # Standard ₹10 Lakhs paper portfolio
    adtv_20d: float = 0.0,
    sector: str = "",
    market_cap_tier: str = "LARGE"
) -> Dict[str, Any]:
    """
    Calculates exact mathematical position sizing, stop-loss, and profit targets.
    Enforces the Macro Agent's cash exposure limits, ADTV constraints, and Sector caps.
    """
    if trigger_price <= 0:
        return {"symbol": symbol, "verdict": "REJECT", "rejection_reason": "Trigger price <= 0"}

    if current_price is None or current_price <= 0:
        current_price = trigger_price
    if macro_weather is None:
        macro_weather = {}

    # P2-4: Dynamically bind portfolio capital to live core equity
    live_core_equity = None
    default_caps = (10_00_000.0, float(getattr(settings, "ALGO_ALLOCATED_CAPITAL", 10_00_000.0)))
    if portfolio_capital_rupees in default_caps and portfolio_capital_rupees > 0:
        try:
            import src.portfolio.state as portfolio_state
            pstate = portfolio_state.get_portfolio_state()
            if pstate and "core_equity" in pstate and pstate["core_equity"] > 0:
                live_core_equity = pstate["core_equity"]
                portfolio_capital_rupees = live_core_equity
        except Exception as e:
            logger.warning(f"Could not load live core equity for arbiter: {e}")

    core_equity = live_core_equity if (live_core_equity is not None and portfolio_capital_rupees > 0) else portfolio_capital_rupees

    # 0. Sector Cap Check
    if sector:
        with get_read_connection() as conn:
            # Check how many open positions exist in this sector, plus today's pending candidates
            open_count = conn.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM positions WHERE sector = ? AND status IN ('OPEN', 'TARGET_1_TRIMMED')) +
                    (SELECT COUNT(*) FROM screener_candidates WHERE sector = ? AND scan_date = CURRENT_DATE AND status IN ('APPROVED', 'PENDING_REVIEW'))
            """, (sector, sector)).fetchone()[0]
            max_open = RISK_CONFIG.get("sector_exposure", {}).get("max_open_positions", 3)
            if open_count >= max_open:
                return {
                    "symbol": symbol,
                    "verdict": "REJECT",
                    "rejection_reason": f"Sector cap reached: {max_open} open/pending positions in {sector}."
                }

            # Check sector capital concentration cap (25%)
            sector_capital = conn.execute("""
                SELECT COALESCE(SUM(entry_price * quantity), 0.0) 
                FROM positions 
                WHERE sector = ? AND status IN ('OPEN', 'TARGET_1_TRIMMED')
            """, (sector,)).fetchone()[0]
            max_sector_pct = RISK_CONFIG.get("sector_exposure", {}).get("max_portfolio_pct", 25.0) / 100.0
            if (sector_capital + (portfolio_capital_rupees * 0.10)) > (portfolio_capital_rupees * max_sector_pct):
                return {
                    "symbol": symbol,
                    "verdict": "REJECT",
                    "rejection_reason": f"Sector capital cap reached: ₹{sector_capital:.2f} deployed in {sector} (max {max_sector_pct:.0%})."
                }

    # 0.5 Realized Compounding Base & Equity Insolvency Guard
    with get_read_connection() as conn:
        res = conn.execute("SELECT COALESCE(SUM(realized_pnl), 0) FROM positions WHERE status IN ('TARGET_REACHED', 'STOPPED_OUT', 'CLOSED', 'TARGET_1_TRIMMED')").fetchone()
        realized_pnl = res[0] if res and res[0] else 0.0
        
        # Portfolio cash floor check (must retain >= 5% cash buffer)
        open_pos_val = conn.execute("SELECT COALESCE(SUM(current_ltp * quantity), 0.0) FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')").fetchone()[0]

    core_equity = live_core_equity if live_core_equity is not None else (portfolio_capital_rupees + realized_pnl)
    if core_equity <= 0.0:
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": 0.0,
            "target_1_price": 0.0,
            "target_2_price": 0.0,
            "risk_reward_ratio": 0.0,
            "total_capital_deployed": 0.0,
            "portfolio_allocation_pct": 0.0,
            "rejection_reason": f"Portfolio equity exhausted: core equity is ₹{core_equity:.2f}.",
            "reason": f"Portfolio equity exhausted: core equity is ₹{core_equity:.2f}."
        }

    available_cash = core_equity - open_pos_val
    if available_cash < (core_equity * 0.05):
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": 0.0,
            "target_1_price": 0.0,
            "target_2_price": 0.0,
            "risk_reward_ratio": 0.0,
            "total_capital_deployed": 0.0,
            "portfolio_allocation_pct": 0.0,
            "rejection_reason": f"Portfolio cash floor reached: Available cash ₹{available_cash:.2f} is under 5% reserve.",
            "reason": f"Portfolio cash floor reached: Available cash ₹{available_cash:.2f} is under 5% reserve."
        }

    portfolio_capital_rupees = core_equity

    # 1. Stop-Loss Calculation
    if atr_14 is None or math.isnan(atr_14) or atr_14 <= 0:
        atr_14 = trigger_price * 0.03

    atr_mult = RISK_CONFIG.get("stop_loss", {}).get("atr_multiplier", 1.8)
    max_drop = RISK_CONFIG.get("stop_loss", {}).get("max_pct_drop", 5.5) / 100.0
    
    atr_stop = round(trigger_price - (atr_mult * atr_14), 2)
    pct_stop = round(trigger_price * (1.0 - max_drop), 2)
    
    if atr_stop < pct_stop:
        risk_per_share = trigger_price - atr_stop
        t1_rr = RISK_CONFIG.get("profit_targets", {}).get("target_1_rr", 2.0)
        t2_rr = RISK_CONFIG.get("profit_targets", {}).get("target_2_rr", 3.5)
        return {
            "symbol": symbol,
            "verdict": "REJECT",
            "suggested_shares": 0,
            "trigger_price": trigger_price,
            "stop_loss_price": atr_stop,
            "target_1_price": round(trigger_price + (t1_rr * risk_per_share), 2),
            "target_2_price": round(trigger_price + (t2_rr * risk_per_share), 2),
            "risk_reward_ratio": t1_rr,
            "total_capital_deployed": 0.0,
            "portfolio_allocation_pct": 0.0,
            "rejection_reason": f"Stock is too volatile. Required ATR stop ({atr_stop}) exceeds max allowed drop ({pct_stop}).",
            "is_paper_trade": settings.PAPER_TRADING_MODE
        }
        
    stop_loss = max(atr_stop, pct_stop)
    
    risk_per_share = trigger_price - stop_loss
    if risk_per_share <= 0:
        risk_per_share = trigger_price * 0.05 # 5% minimum buffer
        stop_loss = trigger_price - risk_per_share

    # 2. Risk Targets
    t1_rr = RISK_CONFIG.get("profit_targets", {}).get("target_1_rr", 2.0)
    t2_rr = RISK_CONFIG.get("profit_targets", {}).get("target_2_rr", 3.5)
    
    target_1 = round(trigger_price + (t1_rr * risk_per_share), 2)
    target_2 = round(trigger_price + (t2_rr * risk_per_share), 2)
    risk_reward_ratio = round((target_1 - trigger_price) / risk_per_share, 2)

    # 3. Maximum Capital Allocation per Trade
    max_trade_risk_rupees = portfolio_capital_rupees * (settings.MAX_PORTFOLIO_RISK_PER_TRADE_PCT / 100.0)
    
    # Raw shares based on risk budget
    raw_shares = math.floor(max_trade_risk_rupees / risk_per_share)
    
    # Cap total position size at 10% of portfolio
    max_pos_pct = RISK_CONFIG.get("max_position_size_pct", 10.0) / 100.0
    max_position_value = portfolio_capital_rupees * max_pos_pct
    max_shares_by_value = math.floor(max_position_value / trigger_price)
    
    # Cap total position size based on market cap tier ADTV participation
    mcap = market_cap_tier.upper() if market_cap_tier else "LARGE"
    adtv_caps = RISK_CONFIG.get("adtv_participation_caps", {})
    cap_pct = adtv_caps.get(mcap, adtv_caps.get("DEFAULT", RISK_CONFIG.get("max_adtv_participation_pct", 1.5)))
    adtv_pct = cap_pct / 100.0
        
    if adtv_20d > 0:
        max_shares_by_adtv = math.floor((adtv_20d * adtv_pct) / trigger_price)
    else:
        # If adtv_20d is omitted or 0, attempt lookup from bhavcopy_daily
        try:
            with get_read_connection() as conn:
                res = conn.execute("""
                    SELECT MEDIAN(total_traded_val) 
                    FROM (SELECT total_traded_val FROM bhavcopy_daily WHERE symbol = ? ORDER BY trade_date DESC LIMIT 20)
                """, (symbol,)).fetchone()
                if res and res[0] and res[0] > 0:
                    adtv_20d = float(res[0])
                    max_shares_by_adtv = math.floor((adtv_20d * adtv_pct) / trigger_price)
                else:
                    max_shares_by_adtv = max_shares_by_value
        except Exception:
            max_shares_by_adtv = max_shares_by_value
    
    shares = min(raw_shares, max_shares_by_value, max_shares_by_adtv)

    # 4. Apply Macro Weather Cash Exposure Factor
    target_cash_exposure = macro_weather.get("target_cash_exposure_pct", 0.0)
    exposure_multiplier = max(0.0, min(1.0, (100.0 - target_cash_exposure) / 100.0))
    adjusted_shares = math.floor(shares * exposure_multiplier)

    # 4.1 CPPI Drawdown Control (P6-2)
    try:
        from src.risk.cppi import calculate_cppi_exposure
        from src.portfolio.state import get_portfolio_state
        p_state = get_portfolio_state()
        cppi_mult = calculate_cppi_exposure(
            core_equity=p_state.get("core_equity", portfolio_capital_rupees),
            lifetime_hwm=p_state.get("lifetime_hwm", portfolio_capital_rupees)
        )
        if cppi_mult < 1.0:
            logger.info(f"[{symbol}] CPPI Drawdown scalar applied: {cppi_mult:.4f}")
        adjusted_shares = math.floor(adjusted_shares * cppi_mult)
    except Exception as e:
        logger.warning(f"[{symbol}] CPPI evaluation failed: {e}. Keeping current sizing.")

    # 4.2 Portfolio Volatility Targeting (P6-3)
    if adjusted_shares > 0:
        try:
            from src.risk.vol_target import calculate_volatility_scalar
            candidate_val = adjusted_shares * trigger_price
            with get_read_connection() as conn:
                open_pos_rows = conn.execute(
                    "SELECT symbol, current_ltp, quantity FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')"
                ).fetchall()
            open_pos_map = {row[0]: float(row[1] or 0.0) * float(row[2] or 0.0) for row in open_pos_rows}
            vol_scalar = calculate_volatility_scalar(
                open_positions=open_pos_map,
                candidate_symbol=symbol,
                candidate_value=candidate_val,
                core_equity=portfolio_capital_rupees,
                fallback_scalar=0.75,
            )
            if vol_scalar < 1.0:
                logger.info(f"[{symbol}] Volatility target scalar applied: {vol_scalar:.4f}")
            adjusted_shares = math.floor(adjusted_shares * vol_scalar)
        except Exception as e:
            logger.warning(f"[{symbol}] Volatility targeting evaluation failed: {e}. Keeping current sizing.")

    total_capital_deployed = adjusted_shares * trigger_price
    allocation_pct = round((total_capital_deployed / portfolio_capital_rupees) * 100, 2)

    # 5. Circuit Band Warning Check
    if adjusted_shares <= 0:
        verdict = "REJECT"
        adjusted_shares = 0
        total_capital_deployed = 0.0
        allocation_pct = 0.0
        reason = "Calculated position size is 0 due to extreme risk, tight macro cash caps, or ADTV limits."
    elif circuit_band is None or math.isnan(circuit_band):
        verdict = "REJECT"
        adjusted_shares = 0
        total_capital_deployed = 0.0
        allocation_pct = 0.0
        reason = "Missing or NaN circuit band data. Fails closed to protect against unknown liquidity/circuit lock risk."
    elif circuit_band <= 2.0:
        verdict = "REJECT"
        adjusted_shares = 0
        total_capital_deployed = 0.0
        allocation_pct = 0.0
        reason = "2% Circuit Band poses extreme gap-and-lock liquidity risk. Hard Rejection."
    elif circuit_band <= 5.0:
        adjusted_shares = math.floor(adjusted_shares * 0.5)
        if adjusted_shares <= 0:
            verdict = "REJECT"
            adjusted_shares = 0
            total_capital_deployed = 0.0
            allocation_pct = 0.0
            reason = "5% Circuit Band reduction reduced position size to 0 shares. Trade rejected."
        else:
            verdict = "REDUCE_SIZE"
            total_capital_deployed = adjusted_shares * trigger_price
            allocation_pct = round((total_capital_deployed / portfolio_capital_rupees) * 100, 2)
            reason = "5% Circuit Band poses severe gap-and-lock liquidity risk. Halved position size."
    elif circuit_band <= 10.0:
        verdict = "APPROVE_WITH_WARNING"
        reason = f"Passed quantitative gates. WARNING: 10% Circuit Band poses moderate lock limit risk."
    else:
        verdict = "APPROVE"
        reason = f"Passed all quantitative gates. Risk budget ₹{max_trade_risk_rupees:.0f} strictly respected."

    result = {
        "symbol": symbol,
        "verdict": verdict,
        "suggested_shares": adjusted_shares,
        "trigger_price": trigger_price,
        "stop_loss_price": stop_loss,
        "target_1_price": target_1,
        "target_2_price": target_2,
        "risk_reward_ratio": risk_reward_ratio,
        "total_capital_deployed": total_capital_deployed,
        "portfolio_allocation_pct": allocation_pct,
        "rejection_reason": reason,
        "reason": reason
    }

    result["is_paper_trade"] = settings.PAPER_TRADING_MODE
    if settings.PAPER_TRADING_MODE:
        logger.info(
            f"[PAPER TRADE] {symbol} | Verdict: {verdict} | "
            f"Qty: {adjusted_shares} @ ₹{trigger_price} | "
            f"SL: ₹{stop_loss} | T1: ₹{target_1} | T2: ₹{target_2} | "
            f"Capital: ₹{total_capital_deployed:.0f}"
        )

    return result


def evaluate_eod_risk_offload(
    symbol: str,
    current_shares: int,
    current_price: float,
    circuit_band: float,
    macro_weather: Dict[str, Any],
) -> Dict[str, Any]:
    """
    3:00 PM EOD Risk Offloader.
    Evaluates if an open position needs to be scaled down before market close
    due to overnight gap risks (e.g., macro weather turning bearish or
    tight circuit bands increasing gap-and-lock probability).
    """
    offload_reason = ""
    suggested_shares = current_shares
    
    # Check 1: Macro Weather Risk Off
    target_cash_exposure = macro_weather.get("target_cash_exposure_pct", 0.0)
    if target_cash_exposure > 0.0:
        # We need to know how much cash we currently have to determine if we must offload
        # A proper fix requires calculating total portfolio equity. 
        # For now, if macro targets a very high cash position (e.g. >= 50%), we defensively reduce shares
        if target_cash_exposure >= 50.0:
            multiplier = max(0.0, min(1.0, (100.0 - target_cash_exposure) / 100.0))
            new_shares = math.floor(current_shares * multiplier)
            if new_shares < suggested_shares:
                suggested_shares = new_shares
                offload_reason = f"Macro risk high (target cash {target_cash_exposure}%)."
            
    # Check 2: Thin Circuit Bands (Overnight Gap-and-Lock risk)
    if circuit_band is not None and circuit_band <= 5.0:
        new_shares = math.floor(suggested_shares * 0.5)
        if new_shares < suggested_shares:
            suggested_shares = new_shares
            offload_reason += f" Thin circuit band ({circuit_band}%) poses gap risk."
            
    if suggested_shares < current_shares:
        verdict = "REDUCE_POSITION"
    else:
        verdict = "HOLD"
        
    return {
        "symbol": symbol,
        "verdict": verdict,
        "current_shares": current_shares,
        "suggested_shares": suggested_shares,
        "shares_to_sell": current_shares - suggested_shares,
        "offload_reason": offload_reason.strip()
    }
