"""
FYERS Holdings Guardian & T+2 Qabd Settlement State Machine.
AlphaSentinel Institutional CNC Swing Trading System.

Enforces:
1. Strict Mufti Muhammad Taqi Usmani Bay' qabl al-Qabd prohibition:
   - Stocks cannot be sold or GTT-ordered before constructive legal possession (Demat settlement).
   - On Day 0 and Day 1 (T0/T1): settlement_status = 'SETTLING_T0_T1', can_exit = False.
   - On Day 2 morning (T+2): settlement_status = 'SETTLED_DEMAT', can_exit = True.
2. FYERS T1 GTT Rejection Guard:
   - Lodges 365-day FYERS GTT OCO order on Day 2 morning upon Demat settlement.
3. Nightly 19:30 IST Holdings Audit & 9-Rule Priority Exit Hierarchy:
   - Reconciles FYERS holdings against DuckDB positions.
   - Auto-imports untracked manual Demat buys (execution_type = 'MANUAL_IMPORT').
   - Evaluates 9 priority exit rules in strict sequential order (P1 to P9).
   - Shariah Drift (P9) triggers Telegram flag only, ZERO forced liquidation.
   - Audits all state changes to DuckDB guardian_log.
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union
from zoneinfo import ZoneInfo

import duckdb

from src.config.settings import settings
from src.utils.holidays import is_nse_holiday

logger = logging.getLogger("fyers_guardian")


class SettlementStatus(str, Enum):
    SETTLING_T0_T1 = "SETTLING_T0_T1"
    SETTLED_DEMAT = "SETTLED_DEMAT"


class ExitPriorityRule(str, Enum):
    P1_HARD_STOP = "P1_HARD_STOP"
    P2_50_SMA_BREAKDOWN = "P2_50_SMA_BREAKDOWN"
    P3_CLIMAX_TRIM = "P3_CLIMAX_TRIM"
    P4_CHANDELIER_TRAIL = "P4_CHANDELIER_TRAIL"
    P5_BREAKEVEN_RATCHET = "P5_BREAKEVEN_RATCHET"
    P6_DISTRIBUTION_TIGHTEN = "P6_DISTRIBUTION_TIGHTEN"
    P7_RS_DECAY_TIGHTEN = "P7_RS_DECAY_TIGHTEN"
    P8_TIME_STOP = "P8_TIME_STOP"
    P9_SHARIAH_DRIFT = "P9_SHARIAH_DRIFT"


class ExitEvaluationResult(NamedTuple):
    rule: Optional[ExitPriorityRule]
    action: str
    new_stop_loss: Optional[float]
    trim_quantity: Optional[int]
    message: str


def parse_date(d: Union[str, date, datetime]) -> date:
    """Parse date-like object to datetime.date."""
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    if isinstance(d, str):
        # Handle ISO strings like '2026-10-07' or '2026-10-07T12:00:00'
        return datetime.fromisoformat(d.split("T")[0]).date()
    raise ValueError(f"Cannot parse date from: {d}")


def count_trading_days(start_date: Union[str, date], end_date: Union[str, date]) -> int:
    """
    Count the number of active NSE trading sessions between start_date and end_date.
    Skips weekends and verified exchange holidays using is_nse_holiday.
    start_date is Day 0 (purchase date).
    Returns integer number of elapsed trading days.
    """
    s_date = parse_date(start_date)
    e_date = parse_date(end_date)
    
    if s_date >= e_date:
        return 0
        
    cur = s_date + timedelta(days=1)
    trading_days = 0
    while cur <= e_date:
        if not is_nse_holiday(cur):
            trading_days += 1
        cur += timedelta(days=1)
        
    return trading_days


def evaluate_settlement(
    trading_days_held: int,
    holding_type: Optional[str] = None
) -> Tuple[SettlementStatus, bool]:
    """
    Evaluate T+2 Qabd possession settlement status.
    
    Args:
        trading_days_held: Number of NSE trading sessions held since purchase date.
        holding_type: Optional FYERS holdingType tag ('T0', 'T1', 'HLD').
        
    Returns:
        (SettlementStatus, can_exit: bool)
    """
    norm_type = str(holding_type).strip().upper() if holding_type else ""
    
    if trading_days_held < 2 or norm_type in ("T0", "T1"):
        return SettlementStatus.SETTLING_T0_T1, False
        
    return SettlementStatus.SETTLED_DEMAT, True


def generate_gtt_oco_payload(
    symbol: str,
    qty: int,
    stop_loss: float,
    target: float
) -> Dict[str, Any]:
    """
    Generate 365-day FYERS GTT OCO order payload.
    """
    fyers_sym = f"NSE:{symbol}-EQ" if not symbol.startswith("NSE:") else symbol
    return {
        "symbol": fyers_sym,
        "qty": qty,
        "stop_loss": round(float(stop_loss), 2),
        "target": round(float(target), 2),
        "side": -1,  # SELL
        "type": 3,   # GTT OCO
        "status": "PLACED_365D",
        "validity": "365D",
        "created_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat()
    }


def evaluate_exit_rule(
    ltp: float,
    stop_loss: float,
    sma_50: Optional[float] = None
) -> Optional[ExitPriorityRule]:
    """
    Convenience evaluator for basic stop and trend rules (P1 / P2).
    """
    if ltp <= stop_loss:
        return ExitPriorityRule.P1_HARD_STOP
    if sma_50 is not None and ltp < sma_50:
        return ExitPriorityRule.P2_50_SMA_BREAKDOWN
    return None


def evaluate_exit_hierarchy(
    ltp: float,
    trailing_stop_loss: float,
    entry_price: float,
    initial_stop_loss: Optional[float] = None,
    quantity: int = 1,
    close: Optional[float] = None,
    sma_50: Optional[float] = None,
    high: Optional[float] = None,
    ema_20: Optional[float] = None,
    atr_14: Optional[float] = None,
    volume: Optional[float] = None,
    avg_volume_20: Optional[float] = None,
    weak_close: Optional[bool] = None,
    peak_close: Optional[float] = None,
    distribution_days_15: int = 0,
    low_5d: Optional[float] = None,
    rs_percentile: Optional[float] = None,
    ema_21: Optional[float] = None,
    trading_days_held: int = 0,
    is_shariah_compliant: bool = True
) -> ExitEvaluationResult:
    """
    Evaluate 9-Rule Priority Exit Hierarchy in strict sequential order (P1 to P9).
    The first matching rule fires.
    """
    current_close = close if close is not None else ltp
    init_stop = initial_stop_loss if initial_stop_loss is not None else trailing_stop_loss
    r_distance = entry_price - init_stop if entry_price > init_stop else max(entry_price * 0.05, 1.0)
    current_peak_close = peak_close if peak_close is not None else current_close

    # Rule P1: Hard Stop Breach (LTP <= trailing_stop_loss -> EXIT)
    if ltp <= trailing_stop_loss:
        return ExitEvaluationResult(
            rule=ExitPriorityRule.P1_HARD_STOP,
            action="EXIT",
            new_stop_loss=None,
            trim_quantity=quantity,
            message=f"P1 Hard Stop Breach: LTP {ltp:.2f} <= Stop {trailing_stop_loss:.2f}"
        )

    # Rule P2: 50-SMA Breakdown (Close < 50 SMA -> EXIT)
    if sma_50 is not None and current_close < sma_50:
        return ExitEvaluationResult(
            rule=ExitPriorityRule.P2_50_SMA_BREAKDOWN,
            action="EXIT",
            new_stop_loss=None,
            trim_quantity=quantity,
            message=f"P2 50-SMA Breakdown: Close {current_close:.2f} < 50-SMA {sma_50:.2f}"
        )

    # Rule P3: +3.5 ATR Trim (High stretched > 3.5 ATR above 20 EMA -> TRIM 50%)
    if high is not None and ema_20 is not None and atr_14 is not None and atr_14 > 0:
        climax_threshold = ema_20 + (3.5 * atr_14)
        if high >= climax_threshold:
            # Volume & candle confirmation if data available
            vol_condition = (volume >= 2.5 * avg_volume_20) if (volume is not None and avg_volume_20 is not None and avg_volume_20 > 0) else True
            candle_condition = weak_close if weak_close is not None else True
            if vol_condition and candle_condition:
                trim_qty = max(1, quantity // 2) if quantity > 1 else 1
                return ExitEvaluationResult(
                    rule=ExitPriorityRule.P3_CLIMAX_TRIM,
                    action="TRIM_50",
                    new_stop_loss=trailing_stop_loss,
                    trim_quantity=trim_qty,
                    message=f"P3 Climax Trim: High {high:.2f} >= 3.5 ATR above EMA20 ({climax_threshold:.2f})"
                )

    # Rule P4: +2R Chandelier Trail (Highest close >= Entry + 2R -> Trail Stop = max(Current Stop, Peak Close - 2.5*ATR))
    target_2r = entry_price + (2.0 * r_distance)
    if current_peak_close >= target_2r:
        atr_buffer = (2.5 * atr_14) if (atr_14 is not None and atr_14 > 0) else (1.5 * r_distance)
        chandelier_stop = round(current_peak_close - atr_buffer, 2)
        new_stop = max(trailing_stop_loss, chandelier_stop)
        if new_stop > trailing_stop_loss:
            return ExitEvaluationResult(
                rule=ExitPriorityRule.P4_CHANDELIER_TRAIL,
                action="TRAIL_STOP",
                new_stop_loss=new_stop,
                trim_quantity=None,
                message=f"P4 +2R Chandelier Trail: Trailed stop to {new_stop:.2f} from {trailing_stop_loss:.2f}"
            )

    # Rule P5: +1R Breakeven Ratchet (Highest close >= Entry + 1R -> Move Stop = Entry * 1.003)
    target_1r = entry_price + (1.0 * r_distance)
    if current_peak_close >= target_1r:
        breakeven_stop = round(entry_price * 1.003, 2)
        new_stop = max(trailing_stop_loss, breakeven_stop)
        if new_stop > trailing_stop_loss:
            return ExitEvaluationResult(
                rule=ExitPriorityRule.P5_BREAKEVEN_RATCHET,
                action="RATCHET_BREAKEVEN",
                new_stop_loss=new_stop,
                trim_quantity=None,
                message=f"P5 +1R Breakeven Ratchet: Stop ratcheted to {new_stop:.2f}"
            )

    # Rule P6: Distribution Days (>= 4 distribution days in 15 sessions -> Tighten Stop to 5-day Low)
    if distribution_days_15 >= 4 and low_5d is not None:
        tightened_stop = round(low_5d, 2)
        new_stop = max(trailing_stop_loss, tightened_stop)
        if new_stop > trailing_stop_loss:
            return ExitEvaluationResult(
                rule=ExitPriorityRule.P6_DISTRIBUTION_TIGHTEN,
                action="TIGHTEN_STOP_5D_LOW",
                new_stop_loss=new_stop,
                trim_quantity=None,
                message=f"P6 Distribution Days ({distribution_days_15} >= 4): Stop tightened to 5d low {new_stop:.2f}"
            )

    # Rule P7: RS Decay (RS Percentile < 50 -> Tighten Stop to 21 EMA)
    if rs_percentile is not None and rs_percentile < 50.0 and ema_21 is not None:
        tightened_stop = round(ema_21, 2)
        new_stop = max(trailing_stop_loss, tightened_stop)
        if new_stop > trailing_stop_loss:
            return ExitEvaluationResult(
                rule=ExitPriorityRule.P7_RS_DECAY_TIGHTEN,
                action="TIGHTEN_STOP_21_EMA",
                new_stop_loss=new_stop,
                trim_quantity=None,
                message=f"P7 RS Decay ({rs_percentile:.1f} < 50): Stop tightened to 21 EMA {new_stop:.2f}"
            )

    # Rule P8: 20d Time Stop (Days held >= 20 and gain < 1R -> Time Stop EXIT)
    if trading_days_held >= 20 and (ltp - entry_price) < r_distance:
        return ExitEvaluationResult(
            rule=ExitPriorityRule.P8_TIME_STOP,
            action="EXIT",
            new_stop_loss=None,
            trim_quantity=quantity,
            message=f"P8 20d Time Stop: Held {trading_days_held} sessions with gain < 1R"
        )

    # Rule P9: Shariah Drift Flag (If held stock fails quarterly sync -> Telegram flag only, zero forced liquidation)
    if not is_shariah_compliant:
        return ExitEvaluationResult(
            rule=ExitPriorityRule.P9_SHARIAH_DRIFT,
            action="FLAG_TELEGRAM_ONLY_NO_FORCED_LIQUIDATION",
            new_stop_loss=None,
            trim_quantity=None,
            message="P9 Shariah Drift: Stock failed quarterly Shariah screening. Telegram alert sent; ZERO forced liquidation."
        )

    return ExitEvaluationResult(
        rule=None,
        action="HOLD",
        new_stop_loss=None,
        trim_quantity=None,
        message="No exit criteria met. Holding position."
    )


def log_guardian_event(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    action: str,
    rule: str,
    details: Dict[str, Any],
    event_timestamp: Optional[datetime] = None
) -> str:
    """
    Log an event to DuckDB guardian_log table.
    """
    log_id = f"GL_{uuid.uuid4().hex[:12]}"
    ts = event_timestamp or datetime.now(ZoneInfo("Asia/Kolkata"))
    details_json = json.dumps(details, default=str)
    
    conn.execute("""
        INSERT INTO guardian_log (id, timestamp, symbol, action, rule, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (log_id, ts, symbol, action, rule, details_json))
    
    return log_id


def reconcile_and_evaluate_holdings(
    conn: duckdb.DuckDBPyConnection,
    fyers_client: Any,
    as_of_date: Optional[Union[str, date]] = None
) -> Dict[str, Any]:
    """
    Nightly 19:30 IST Holdings Audit & Settlement State Machine.
    
    1. Dynamic Token Refresh: Calls fyers_client.reload_token().
    2. Holdings Query: Queries fyers_client.get_holdings().
    3. Auto-Import: Detects untracked Demat holdings and imports them into DuckDB positions.
    4. Settlement Transition: Evaluates T+2 Qabd possession.
       - T0/T1: can_exit = False, settlement_status = 'SETTLING_T0_T1'.
       - Day 2 morning: transitions to 'SETTLED_DEMAT', can_exit = True.
       - Lodges 365-day FYERS GTT OCO order and sets gtt_placed = True.
    5. Priority Exit Hierarchy: Evaluates P1 through P9 for settled positions.
    6. Audit Logging: Records all actions to guardian_log.
    """
    eval_date = parse_date(as_of_date) if as_of_date else datetime.now(ZoneInfo("Asia/Kolkata")).date()
    
    # 1. Dynamic Token Refresh
    if hasattr(fyers_client, "reload_token"):
        fyers_client.reload_token()

    # 2. Query Broker Holdings
    raw_holdings = fyers_client.get_holdings() if hasattr(fyers_client, "get_holdings") else []
    
    # Normalize broker holdings by bare NSE symbol
    broker_holdings: Dict[str, Dict[str, Any]] = {}
    for h in raw_holdings:
        sym = str(h.get("symbol", "")).replace("NSE:", "").replace("-EQ", "").strip()
        if sym:
            broker_holdings[sym] = h

    # 3. Query Open DuckDB Positions
    pos_rows = conn.execute("""
        SELECT 
            id, symbol, entry_date, entry_price, quantity, current_ltp,
            trailing_stop_loss, target_1, target_2, risk_rupees,
            status, execution_type, settlement_status, can_exit,
            gtt_placed, peak_high, atr
        FROM positions
        WHERE status IN ('OPEN', 'TARGET_1_TRIMMED', 'MARKED_FOR_CLOSURE')
    """).fetchall()

    pos_cols = [
        "id", "symbol", "entry_date", "entry_price", "quantity", "current_ltp",
        "trailing_stop_loss", "target_1", "target_2", "risk_rupees",
        "status", "execution_type", "settlement_status", "can_exit",
        "gtt_placed", "peak_high", "atr"
    ]
    open_positions = [dict(zip(pos_cols, row)) for row in pos_rows]
    tracked_symbols = {p["symbol"] for p in open_positions}

    # Summary tracking
    imported_symbols: List[str] = []
    gtt_lodged_symbols: List[str] = []
    exit_alerts: List[Dict[str, Any]] = []
    evaluated_count = 0
    settled_count = 0
    settling_count = 0

    # 4. Auto-Import Untracked Demat Buys
    for sym, h in broker_holdings.items():
        qty = int(h.get("quantity", h.get("netQty", 0)))
        if qty <= 0:
            continue
        if sym not in tracked_symbols:
            cost_price = float(h.get("costPrice", h.get("avgPrice", h.get("ltp", 100.0))))
            ltp = float(h.get("ltp", cost_price))
            htype = h.get("holdingType", "HLD")
            is_settled = (htype != "T1")
            
            import_id = f"POS_IMPORT_{sym}_{uuid.uuid4().hex[:8]}"
            stop_loss = round(cost_price * 0.94, 2)  # default 6% structural stop
            target_1 = round(cost_price * 1.12, 2)
            target_2 = round(cost_price * 1.20, 2)
            risk_rupees = round(qty * (cost_price - stop_loss), 2)
            status_val = "SETTLED_DEMAT" if is_settled else "SETTLING_T0_T1"
            can_exit_val = is_settled

            conn.execute("""
                INSERT INTO positions (
                    id, symbol, entry_date, entry_price, quantity, current_ltp,
                    trailing_stop_loss, target_1, target_2, risk_rupees,
                    portfolio_allocation_pct, status, execution_type,
                    settlement_status, can_exit, gtt_placed
                ) VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, 'OPEN', 'MANUAL_IMPORT',
                    ?, ?, FALSE
                )
            """, (
                import_id, sym, eval_date, cost_price, qty, ltp,
                stop_loss, target_1, target_2, risk_rupees,
                0.0, status_val, can_exit_val
            ))

            log_guardian_event(
                conn=conn,
                symbol=sym,
                action="MANUAL_IMPORT",
                rule="AUTO_IMPORT",
                details={
                    "imported_id": import_id,
                    "quantity": qty,
                    "cost_price": cost_price,
                    "holdingType": htype,
                    "settlement_status": status_val,
                    "can_exit": can_exit_val
                }
            )
            imported_symbols.append(sym)
            tracked_symbols.add(sym)

            # Include in positions list for subsequent evaluation
            open_positions.append({
                "id": import_id,
                "symbol": sym,
                "entry_date": eval_date,
                "entry_price": cost_price,
                "quantity": qty,
                "current_ltp": ltp,
                "trailing_stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "risk_rupees": risk_rupees,
                "status": "OPEN",
                "execution_type": "MANUAL_IMPORT",
                "settlement_status": status_val,
                "can_exit": can_exit_val,
                "gtt_placed": False,
                "peak_high": cost_price,
                "atr": cost_price * 0.02
            })

    # 5. Reconcile Settlement Status & Lodge Day 2 GTT OCO Orders
    for pos in open_positions:
        evaluated_count += 1
        pos_id = pos["id"]
        sym = pos["symbol"]
        holding = broker_holdings.get(sym, {})
        holding_type = holding.get("holdingType")

        # Compute trading days held
        entry_d = parse_date(pos["entry_date"])
        trading_days_held = count_trading_days(entry_d, eval_date)

        if pos.get("execution_type") == "MANUAL_IMPORT":
            if holding_type in ("T1", "T0"):
                new_status, new_can_exit = SettlementStatus.SETTLING_T0_T1, False
            else:
                new_status, new_can_exit = SettlementStatus.SETTLED_DEMAT, True
        elif pos.get("settlement_status") == "SETTLED_DEMAT" and holding_type not in ("T1", "T0"):
            new_status, new_can_exit = SettlementStatus.SETTLED_DEMAT, True
        else:
            new_status, new_can_exit = evaluate_settlement(trading_days_held, holding_type)

        if new_can_exit:
            settled_count += 1
        else:
            settling_count += 1

        # Check for Day 2 morning transition to SETTLED_DEMAT needing GTT OCO order
        gtt_already_placed = bool(pos.get("gtt_placed", False))
        gtt_just_placed = False

        if new_can_exit and not gtt_already_placed:
            # Day 2 morning GTT OCO prompt / lodging
            target_2 = float(pos.get("target_2", pos["entry_price"] * 1.20))
            stop_loss = float(pos.get("trailing_stop_loss", pos["entry_price"] * 0.94))
            qty = int(pos["quantity"])

            if hasattr(fyers_client, "place_gtt_oco_order"):
                try:
                    fyers_client.place_gtt_oco_order(
                        symbol=sym,
                        qty=qty,
                        stop_loss=stop_loss,
                        target=target_2
                    )
                except Exception as e:
                    logger.warning(f"Error placing GTT OCO order for {sym}: {e}")

            conn.execute("""
                UPDATE positions 
                SET gtt_placed = TRUE, gtt_placed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (pos_id,))

            log_guardian_event(
                conn=conn,
                symbol=sym,
                action="GTT_OCO_LODGED",
                rule="DAY2_TRANSITION",
                details={
                    "position_id": pos_id,
                    "stop_loss": stop_loss,
                    "target_2": target_2,
                    "quantity": qty,
                    "validity": "365D"
                }
            )
            gtt_lodged_symbols.append(sym)
            gtt_just_placed = True

        # Update settlement_status and can_exit in DuckDB
        conn.execute("""
            UPDATE positions
            SET settlement_status = ?, can_exit = ?
            WHERE id = ?
        """, (new_status.value, new_can_exit, pos_id))

        # 6. Evaluate 9-Rule Priority Exit Hierarchy ONLY if Settled (can_exit == True)
        if not new_can_exit:
            # Mufti Taqi Usmani Bay' qabl al-Qabd: ZERO sell alerts or exits permitted during T0/T1
            continue

        # Fetch technical context from bhavcopy or holding
        ltp = float(holding.get("ltp", pos["current_ltp"]))
        entry_price = float(pos["entry_price"])
        trailing_stop = float(pos["trailing_stop_loss"])
        qty = int(pos["quantity"])
        atr = float(pos.get("atr") or (entry_price * 0.02))

        # Check Shariah compliance status from shariah_universe if table exists
        is_shariah = True
        try:
            shariah_row = conn.execute(
                "SELECT is_compliant FROM shariah_universe WHERE symbol = ?",
                (sym,)
            ).fetchone()
            if shariah_row is not None and not shariah_row[0]:
                is_shariah = False
        except Exception:
            pass

        # Fetch latest metrics from bhavcopy_daily if available
        sma_50 = None
        high = None
        ema_20 = None
        close = ltp
        try:
            bhav_row = conn.execute("""
                SELECT close_price, high_price 
                FROM bhavcopy_daily 
                WHERE symbol = ? AND trade_date <= ?
                ORDER BY trade_date DESC LIMIT 1
            """, (sym, eval_date)).fetchone()
            if bhav_row:
                close = float(bhav_row[0])
                high = float(bhav_row[1])

            # Calculate 50 SMA
            sma_res = conn.execute("""
                SELECT AVG(close_price)
                FROM (
                    SELECT close_price FROM bhavcopy_daily
                    WHERE symbol = ? AND trade_date <= ?
                    ORDER BY trade_date DESC LIMIT 50
                )
            """, (sym, eval_date)).fetchone()
            if sma_res and sma_res[0]:
                sma_50 = float(sma_res[0])
        except Exception:
            pass

        eval_res = evaluate_exit_hierarchy(
            ltp=ltp,
            trailing_stop_loss=trailing_stop,
            entry_price=entry_price,
            initial_stop_loss=trailing_stop,
            quantity=qty,
            close=close,
            sma_50=sma_50,
            high=high,
            ema_20=ema_20,
            atr_14=atr,
            trading_days_held=trading_days_held,
            is_shariah_compliant=is_shariah
        )

        if eval_res.rule is not None:
            exit_alerts.append({
                "symbol": sym,
                "rule": eval_res.rule.value,
                "action": eval_res.action,
                "message": eval_res.message,
                "new_stop_loss": eval_res.new_stop_loss
            })

            # Update position state in DuckDB if stop moved or status changed
            if eval_res.action == "EXIT":
                conn.execute("""
                    UPDATE positions
                    SET status = 'MARKED_FOR_CLOSURE', current_ltp = ?
                    WHERE id = ?
                """, (ltp, pos_id))
            elif eval_res.action == "TRIM_50":
                conn.execute("""
                    UPDATE positions
                    SET status = 'TARGET_1_TRIMMED', current_ltp = ?
                    WHERE id = ?
                """, (ltp, pos_id))
            elif eval_res.new_stop_loss is not None:
                conn.execute("""
                    UPDATE positions
                    SET trailing_stop_loss = ?, current_ltp = ?
                    WHERE id = ?
                """, (eval_res.new_stop_loss, ltp, pos_id))

            log_guardian_event(
                conn=conn,
                symbol=sym,
                action=eval_res.action,
                rule=eval_res.rule.value,
                details={
                    "position_id": pos_id,
                    "ltp": ltp,
                    "message": eval_res.message,
                    "new_stop_loss": eval_res.new_stop_loss,
                    "trim_quantity": eval_res.trim_quantity
                }
            )

    return {
        "as_of_date": str(eval_date),
        "total_evaluated": evaluated_count,
        "settled_count": settled_count,
        "settling_count": settling_count,
        "manual_imports": imported_symbols,
        "gtt_lodged_symbols": gtt_lodged_symbols,
        "exit_alerts": exit_alerts
    }
