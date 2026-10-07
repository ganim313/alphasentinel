"""
E2E Testing Harness Shared Fixtures & Contract Helpers.
Provides isolated in-memory DuckDB connections, synthetic market data generators,
and mock FYERS client adapters adhering strictly to SEBI and Shariah invariants.
"""

import os
import math
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, NamedTuple
from enum import Enum
import numpy as np
import pandas as pd
import duckdb


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


class RegimeState(NamedTuple):
    regime: str  # "RISK_ON" | "NEUTRAL" | "RISK_OFF"
    score: int   # 3, 2, 1, 0
    risk_per_trade_pct: float  # 1.0, 0.5, 0.0
    allow_new_entries: bool    # True, True, False
    nifty500_close: float
    nifty500_sma50: float
    nifty500_sma200: float
    breadth_pct: float         # % Halal EQ stocks > own SMA50
    details: Dict[str, Any]


def create_in_memory_e2e_db() -> duckdb.DuckDBPyConnection:
    """
    Creates an isolated in-memory DuckDB database initialized with all canonical
    AlphaSentinel tables including M2 settlement tracking and M5 shariah universe tables.
    """
    conn = duckdb.connect(":memory:")

    conn.execute("""
    CREATE SEQUENCE IF NOT EXISTS positions_id_seq START 1;
    CREATE SEQUENCE IF NOT EXISTS guardian_log_id_seq START 1;

    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY DEFAULT nextval('positions_id_seq'),
        symbol VARCHAR NOT NULL,
        exchange VARCHAR DEFAULT 'NSE',
        entry_date DATE NOT NULL,
        entry_price DOUBLE NOT NULL,
        quantity INTEGER NOT NULL,
        current_ltp DOUBLE,
        unrealized_pnl DOUBLE DEFAULT 0.0,
        trailing_stop_loss DOUBLE NOT NULL,
        target_1 DOUBLE,
        target_2 DOUBLE,
        risk_rupees DOUBLE NOT NULL,
        portfolio_allocation_pct DOUBLE,
        status VARCHAR DEFAULT 'OPEN',
        execution_type VARCHAR DEFAULT 'PAPER',
        exit_date DATE,
        exit_price DOUBLE,
        realized_pnl DOUBLE DEFAULT 0.0,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        sector VARCHAR,
        atr DOUBLE,
        peak_high DOUBLE,
        candidate_id INTEGER,
        settlement_status VARCHAR DEFAULT 'SETTLING_T0_T1',
        can_exit BOOLEAN DEFAULT FALSE,
        gtt_placed BOOLEAN DEFAULT FALSE,
        gtt_placed_at TIMESTAMPTZ,
        purification_due_inr DOUBLE DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS guardian_log (
        id INTEGER PRIMARY KEY DEFAULT nextval('guardian_log_id_seq'),
        audit_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        symbol VARCHAR NOT NULL,
        holding_type VARCHAR NOT NULL,
        trading_days_held INTEGER NOT NULL,
        event_type VARCHAR NOT NULL,
        rule_fired VARCHAR,
        old_stop DOUBLE,
        new_stop DOUBLE,
        ltp DOUBLE,
        action_taken VARCHAR NOT NULL,
        telegram_alert_sent BOOLEAN DEFAULT FALSE
    );

    CREATE TABLE IF NOT EXISTS shariah_universe (
        symbol VARCHAR PRIMARY KEY,
        fyers_symbol VARCHAR NOT NULL,
        sector VARCHAR NOT NULL,
        debt_to_assets DOUBLE NOT NULL,
        cash_to_assets DOUBLE NOT NULL,
        interest_income_ratio DOUBLE NOT NULL,
        illiquid_ratio DOUBLE NOT NULL,
        is_compliant BOOLEAN NOT NULL DEFAULT TRUE,
        purification_ratio DOUBLE NOT NULL DEFAULT 0.0,
        sync_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS bhavcopy_daily (
        symbol VARCHAR NOT NULL,
        trade_date DATE NOT NULL,
        series VARCHAR DEFAULT 'EQ',
        open_price DOUBLE,
        high_price DOUBLE,
        low_price DOUBLE,
        close_price DOUBLE,
        prev_close DOUBLE,
        total_traded_qty BIGINT,
        total_traded_val DOUBLE,
        delivery_qty BIGINT DEFAULT 0,
        delivery_pct DOUBLE DEFAULT 0.0,
        split_multiplier DOUBLE DEFAULT 1.0,
        upper_circuit DOUBLE,
        lower_circuit DOUBLE,
        circuit_band_pct INTEGER,
        is_asm BOOLEAN DEFAULT FALSE,
        is_gsm BOOLEAN DEFAULT FALSE,
        PRIMARY KEY (symbol, trade_date)
    );

    CREATE TABLE IF NOT EXISTS fundamentals_cache (
        symbol VARCHAR PRIMARY KEY,
        sector_name VARCHAR,
        total_assets DOUBLE,
        borrowings DOUBLE,
        debt_to_assets DOUBLE,
        cash_to_assets DOUBLE,
        interest_income_ratio DOUBLE,
        illiquid_ratio DOUBLE,
        net_liquid_assets_crores DOUBLE,
        market_cap_crores DOUBLE,
        sales DOUBLE,
        other_income DOUBLE,
        last_updated TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS corporate_actions (
        id INTEGER PRIMARY KEY,
        symbol VARCHAR NOT NULL,
        action_type VARCHAR NOT NULL,
        ex_date DATE NOT NULL,
        ratio_numerator DOUBLE NOT NULL,
        ratio_denominator DOUBLE NOT NULL,
        adjustment_multiplier DOUBLE NOT NULL,
        applied BOOLEAN DEFAULT FALSE,
        recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS quarantined_stocks (
        symbol VARCHAR NOT NULL,
        trade_date DATE NOT NULL,
        pct_jump DOUBLE NOT NULL,
        reason VARCHAR NOT NULL,
        quarantined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (symbol, trade_date)
    );

    CREATE TABLE IF NOT EXISTS screener_candidates (
        id INTEGER PRIMARY KEY,
        scan_date DATE NOT NULL,
        symbol VARCHAR NOT NULL,
        pattern_type VARCHAR,
        current_price DOUBLE,
        trigger_price DOUBLE,
        stop_loss_price DOUBLE,
        status VARCHAR DEFAULT 'PENDING_REVIEW',
        ml_prob DOUBLE,
        conviction_score DOUBLE,
        sector VARCHAR,
        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
    );
    """)

    return conn


class MockFyersClient:
    """Deterministic Mock FYERS Client for testing order states and holdings."""

    def __init__(self, token_path: str = ".fyers_token"):
        self.token_path = token_path
        self._cached_token = "MOCK_TOKEN_INITIAL"
        self._token_mtime = 0.0
        self.holdings_data: List[Dict[str, Any]] = []
        self.positions_data: List[Dict[str, Any]] = []
        self.placed_gtt_orders: List[Dict[str, Any]] = []

    def reload_token(self) -> str:
        """Reload token dynamically if token file exists and mtime changed."""
        if os.path.exists(self.token_path):
            current_mtime = os.path.getmtime(self.token_path)
            if current_mtime > self._token_mtime:
                with open(self.token_path, "r", encoding="utf-8") as f:
                    self._cached_token = f.read().strip()
                self._token_mtime = current_mtime
        return self._cached_token

    def get_holdings(self) -> List[Dict[str, Any]]:
        return list(self.holdings_data)

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.positions_data)

    def place_gtt_oco_order(self, symbol: str, qty: int, stop_loss: float, target: float) -> Dict[str, Any]:
        order = {
            "symbol": symbol,
            "qty": qty,
            "stop_loss": stop_loss,
            "target": target,
            "status": "PLACED_365D",
            "placed_at": datetime.now().isoformat()
        }
        self.placed_gtt_orders.append(order)
        return order


def compute_vectorized_residual_momentum(
    stock_returns: np.ndarray,      # shape: (T, N)
    benchmark_returns: np.ndarray    # shape: (T,)
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes vectorized 60-day OLS beta and 30-day cumulative standardized idiosyncratic residual.
    Returns: (betas, scores, percentile_ranks)
    """
    x = benchmark_returns
    Y = stock_returns
    xc = x - x.mean()
    Yc = Y - Y.mean(axis=0)
    var_x = np.sum(xc ** 2)
    if var_x < 1e-12:
        var_x = 1e-6
    betas = (xc @ Yc) / var_x
    alphas = Y.mean(axis=0) - betas * x.mean()
    residuals = Y - (np.outer(x, betas) + alphas)
    cum_res = np.sum(residuals[-30:, :], axis=0)
    res_std = np.maximum(np.std(residuals, axis=0, ddof=2), 1e-6)
    scores = cum_res / res_std
    ranks = pd.Series(scores).rank(pct=True).to_numpy() * 100.0
    return betas, scores, ranks


def check_price_jump_tripwire_logic(
    prev_close: Optional[float],
    close_price: float,
    has_approved_corp_action: bool = False
) -> Tuple[bool, float, str]:
    """
    Evaluates the >25% price jump quarantine tripwire.
    Returns: (is_quarantined, pct_jump, reason)
    """
    if prev_close is None or prev_close <= 0:
        return False, 0.0, "VALID_FIRST_RECORD_OR_NO_PREV_CLOSE"

    pct_jump = (close_price - prev_close) / prev_close
    if abs(pct_jump) > 0.25:
        if has_approved_corp_action:
            return False, pct_jump, f"EXPLAINED_BY_CORPORATE_ACTION_{pct_jump:+.2%}"
        else:
            return True, pct_jump, f"UNEXPLAINED_PRICE_JUMP_{pct_jump:+.2%}"

    return False, pct_jump, "NORMAL_PRICE_CONTINUITY"
