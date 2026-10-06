import logging
import datetime
import uuid
import json
from typing import Optional, Dict, Any
from src.db.queue_writer import db_write
from src.db.session import get_read_connection
from src.config.settings import settings

logger = logging.getLogger(__name__)

class PaperBroker:
    @staticmethod
    def place_order(symbol: str, price: float, atr: float, quantity: int = 100, sector: Optional[str] = None, execution_type: str = "PAPER", initial_stop: Optional[float] = None, target_1: Optional[float] = None, target_2: Optional[float] = None, candidate_id: Optional[str] = None) -> str:
        """Executes a simulated buy order using a Price-Chaser Limit Order mechanism."""
        from src.notification.telegram_bot import is_system_halted
        if is_system_halted():
            logger.error(f"Execution Aborted: Global Kill Switch is ACTIVE. Refusing to place order for {symbol}.")
            return ""

        import math
        if price is None or atr is None or math.isnan(price) or math.isnan(atr) or price <= 0 or quantity <= 0 or atr <= 0:
            logger.error(f"Invalid order parameters for {symbol}: price={price}, qty={quantity}, atr={atr}")
            return ""

        # Idempotency Guard: Prevent duplicate open orders for the same symbol
        try:
            with get_read_connection() as conn:
                existing = conn.execute(
                    "SELECT id FROM positions WHERE symbol = ? AND status IN ('OPEN', 'TARGET_1_TRIMMED')",
                    (symbol,)
                ).fetchone()
                if existing:
                    logger.warning(f"Duplicate Order Rejected: Position {existing[0]} for {symbol} already active.")
                    return existing[0]
        except Exception as e:
            logger.warning(f"DuckDB error checking existing positions for {symbol}: {e}")

        try:
            with get_read_connection() as conn:
                res = conn.execute(
                    "SELECT AVG(total_traded_val) FROM (SELECT total_traded_val FROM bhavcopy_daily WHERE symbol = ? ORDER BY trade_date DESC LIMIT 20)",
                    (symbol,)
                ).fetchone()
                adtv = res[0] if res and res[0] else 0
        except Exception as e:
            logger.warning(f"DuckDB error fetching ADTV for {symbol}: {e}")
            adtv = 0
            
        if adtv > 500_000_000: # > 50 Cr Large cap
            slippage = 0.001
        elif adtv > 50_000_000: # > 5 Cr Small cap
            slippage = 0.010
        else: # Micro cap
            slippage = 0.015

        try:
            with get_read_connection() as conn:
                res = conn.execute(
                    "SELECT upper_circuit, close_price, circuit_band_pct FROM bhavcopy_daily WHERE symbol = ? ORDER BY trade_date DESC LIMIT 1",
                    (symbol,)
                ).fetchone()
                if res:
                    db_circuit = res[0]
                    prev_close = res[1]
                    band = res[2]
                    if db_circuit and db_circuit > 0:
                        upper_circuit = float(db_circuit)
                    elif prev_close and prev_close > 0 and band and band > 0:
                        upper_circuit = float(prev_close * (1.0 + band / 100.0))
                    else:
                        upper_circuit = float('inf')
                else:
                    upper_circuit = float('inf')
        except Exception as e:
            logger.warning(f"DuckDB error fetching upper_circuit for {symbol}: {e}")
            upper_circuit = float('inf')

        executed_price = price * (1.0 + slippage)
        if executed_price >= upper_circuit:
            logger.error(f"Trade Rejected: Slippage pushes executed price {executed_price:.2f} above Upper Circuit {upper_circuit:.2f} for {symbol}.")
            return ""
        
        # Respect parameters passed by Risk Arbiter; fallback to 1.8 ATR and 2.0R / 3.5R
        final_stop = initial_stop if initial_stop is not None else (executed_price - (atr * 1.8))
        risk_per_share = executed_price - final_stop if (executed_price - final_stop) > 0 else (atr * 1.8)
        final_t1 = target_1 if target_1 is not None else (executed_price + (risk_per_share * 2.0))
        final_t2 = target_2 if target_2 is not None else (executed_price + (risk_per_share * 3.5))
        
        trade_id = f"P_{symbol}_{uuid.uuid4().hex[:8]}"
        
        risk_rupees = risk_per_share * quantity
        try:
            import src.portfolio.state as portfolio_state
            pstate = portfolio_state.get_portfolio_state()
            portfolio_cap = pstate["core_equity"] if pstate and pstate.get("core_equity", 0.0) > 0 else settings.ALGO_ALLOCATED_CAPITAL
        except Exception as e:
            logger.warning(f"Could not load live core equity for allocation pct: {e}")
            portfolio_cap = settings.ALGO_ALLOCATED_CAPITAL
        portfolio_allocation_pct = ((executed_price * quantity) / portfolio_cap) * 100.0 if portfolio_cap > 0 else 0.0

        try:
            db_write("""
                INSERT INTO positions (
                    id, symbol, candidate_id, sector, entry_date, entry_price, quantity, 
                    current_ltp, atr, trailing_stop_loss, peak_high, target_1, target_2,
                    risk_rupees, portfolio_allocation_pct, status, execution_type
                ) VALUES (?, ?, ?, ?, CURRENT_DATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """, (trade_id, symbol, candidate_id, sector, executed_price, quantity, executed_price, atr, final_stop, executed_price, final_t1, final_t2, risk_rupees, portfolio_allocation_pct, execution_type))
            
            logger.info(f"{execution_type} TRADE EXECUTED: Buy {quantity} {symbol} @ {executed_price:.2f}. Stop: {final_stop:.2f}")
            return trade_id
        except Exception as e:
            logger.error(f"Database error while saving position for {symbol}: {e}")
            return ""


from src.execution.dhan_broker import DhanBroker



def execute_trade(symbol: str, price: float, atr: float, quantity: int = 100, sector: Optional[str] = None, initial_stop: Optional[float] = None, target_1: Optional[float] = None, target_2: Optional[float] = None, candidate_id: Optional[str] = None) -> str:
    """Router for executing trades based on EXECUTION_ENV."""
    from src.notification.telegram_bot import is_system_halted
    if is_system_halted():
        logger.error(f"Execution Aborted: Global Kill Switch is ACTIVE. Refusing to route trade for {symbol}.")
        return ""

    if settings.EXECUTION_ENV == "DHAN":
        return DhanBroker.place_order(symbol, price, atr, quantity, sector, initial_stop=initial_stop, target_1=target_1, target_2=target_2, candidate_id=candidate_id)
    else:
        return PaperBroker.place_order(symbol, price, atr, quantity, sector, execution_type="PAPER", initial_stop=initial_stop, target_1=target_1, target_2=target_2, candidate_id=candidate_id)

# Backwards compatibility
execute_paper_trade = execute_trade


def check_lower_circuit_trap(symbol: str, current_price: Optional[float] = None) -> Dict[str, Any]:
    """
    Checks if a stock is trapped at or below its exchange Lower Circuit.
    If trapped, market sell orders cannot execute in live markets.
    """
    try:
        with get_read_connection() as conn:
            row = conn.execute("""
                SELECT close_price, lower_circuit, circuit_band_pct
                FROM bhavcopy_daily
                WHERE symbol = ?
                ORDER BY trade_date DESC LIMIT 1
            """, (symbol,)).fetchone()
            
            if row:
                close_p, db_lc, band = row[0], row[1], row[2]
                if db_lc and db_lc > 0:
                    lc_price = float(db_lc)
                elif close_p and close_p > 0 and band and band > 0:
                    lc_price = float(close_p * (1.0 - band / 100.0))
                else:
                    lc_price = 0.0

                eval_price = current_price if current_price is not None else close_p
                if lc_price > 0 and eval_price is not None and eval_price <= (lc_price * 1.002):
                    return {"is_trapped": True, "lower_circuit": lc_price, "eval_price": eval_price}
    except Exception as e:
        logger.warning(f"Error checking lower circuit trap for {symbol}: {e}")
        
    return {"is_trapped": False, "lower_circuit": None, "eval_price": current_price}

