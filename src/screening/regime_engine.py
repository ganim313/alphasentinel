"""
Deterministic Market Regime Engine.
Computes institutional 3-point breadth score using End-of-Day Bhavcopy in DuckDB:
  Point 1: Nifty 500 Close > 50-day SMA
  Point 2: Nifty 500 50-day SMA > 200-day SMA
  Point 3: Universe Breadth (% Halal EQ stocks > own 50-day SMA) > 50%

Scoring & Regime Map:
  Score 3 = RISK_ON  (1.0% risk per trade, allow new entries = True)
  Score 2 = NEUTRAL  (0.5% risk per trade, allow new entries = True)
  Score <= 1 = RISK_OFF (0.0% risk per trade, allow new entries = False)

Fails closed to Score 0 (RISK_OFF, allow_new_entries = False) on missing or insufficient data.
"""

import logging
import datetime
from typing import NamedTuple, Dict, Any, Optional, List
import pandas as pd
import duckdb

logger = logging.getLogger(__name__)

BENCHMARK_CANDIDATES = ["MONIFTY500", "NIFTY500", "NIFTY 500", "^CRSLDX", "^NSEI"]


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


def _fail_closed(reason: str) -> RegimeState:
    """Returns fail-closed RISK_OFF state with zero allocation and halted entries."""
    logger.warning("Market regime engine failing closed: %s", reason)
    return RegimeState(
        regime="RISK_OFF",
        score=0,
        risk_per_trade_pct=0.0,
        allow_new_entries=False,
        nifty500_close=0.0,
        nifty500_sma50=0.0,
        nifty500_sma200=0.0,
        breadth_pct=0.0,
        details={"error": reason, "fail_closed": True},
    )


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    """Checks if a table exists in the DuckDB connection."""
    try:
        res = conn.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
            [table_name]
        ).fetchone()
        return bool(res and res[0] > 0)
    except Exception:
        return False


def _get_table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> List[str]:
    """Returns column names for a given table in DuckDB."""
    try:
        rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return [r[1] for r in rows]
    except Exception:
        return []


def _resolve_benchmark_symbol(conn: duckdb.DuckDBPyConnection, as_of_date: Optional[datetime.date] = None) -> Optional[str]:
    """Finds the benchmark symbol present in bhavcopy_daily."""
    placeholders = ",".join(["?"] * len(BENCHMARK_CANDIDATES))
    query = f"""
        SELECT symbol, COUNT(*) as cnt
        FROM bhavcopy_daily
        WHERE symbol IN ({placeholders})
          AND (? IS NULL OR trade_date <= ?)
        GROUP BY symbol
        ORDER BY cnt DESC
        LIMIT 1
    """
    params = list(BENCHMARK_CANDIDATES) + [as_of_date, as_of_date]
    try:
        row = conn.execute(query, params).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception as e:
        logger.debug("Failed querying candidate benchmark symbols: %s", e)

    # Fallback to wildcard search if candidate names not found
    try:
        wildcard_query = """
            SELECT symbol, COUNT(*) as cnt
            FROM bhavcopy_daily
            WHERE (symbol LIKE '%NIFTY500%' OR symbol LIKE '%500%')
              AND (? IS NULL OR trade_date <= ?)
            GROUP BY symbol
            ORDER BY cnt DESC
            LIMIT 1
        """
        row = conn.execute(wildcard_query, [as_of_date, as_of_date]).fetchone()
        if row and row[0]:
            return str(row[0])
    except Exception as e:
        logger.debug("Failed querying wildcard benchmark symbols: %s", e)

    return None


def compute_market_regime(
    conn: duckdb.DuckDBPyConnection,
    as_of_date: Optional[Any] = None
) -> RegimeState:
    """
    Computes deterministic 3-point breadth market regime.
    Point 1: Nifty 500 Close > SMA50
    Point 2: Nifty 500 SMA50 > SMA200
    Point 3: Universe Breadth (% Halal EQ stocks > own SMA50) > 50%

    Returns RegimeState with regime, score, risk_per_trade_pct, allow_new_entries, and metrics.
    Fails closed to RISK_OFF (Score 0) on missing or insufficient data.
    """
    if conn is None:
        return _fail_closed("DuckDB connection is None")

    try:
        if not _table_exists(conn, "bhavcopy_daily"):
            return _fail_closed("Table 'bhavcopy_daily' does not exist")
    except Exception as e:
        return _fail_closed(f"Database query error checking bhavcopy_daily: {e}")

    # Standardize as_of_date
    parsed_date: Optional[datetime.date] = None
    if as_of_date is not None:
        try:
            if isinstance(as_of_date, datetime.date) and not isinstance(as_of_date, datetime.datetime):
                parsed_date = as_of_date
            elif isinstance(as_of_date, (datetime.datetime, pd.Timestamp)):
                parsed_date = as_of_date.date()
            elif isinstance(as_of_date, str):
                parsed_date = pd.to_datetime(as_of_date).date()
        except Exception as e:
            return _fail_closed(f"Invalid as_of_date parameter: {e}")

    # 1. Resolve Benchmark Symbol
    bm_symbol = _resolve_benchmark_symbol(conn, parsed_date)
    if not bm_symbol:
        return _fail_closed("No benchmark symbol (MONIFTY500 / Nifty 500) found in bhavcopy_daily")

    # 2. Fetch Benchmark Series
    try:
        bm_query = """
            SELECT trade_date, close_price
            FROM bhavcopy_daily
            WHERE symbol = ?
              AND (? IS NULL OR trade_date <= ?)
            ORDER BY trade_date ASC
        """
        bm_df = conn.execute(bm_query, [bm_symbol, parsed_date, parsed_date]).df()
    except Exception as e:
        return _fail_closed(f"Failed to query benchmark prices: {e}")

    if bm_df.empty or len(bm_df) < 50:
        return _fail_closed(
            f"Insufficient benchmark history for {bm_symbol}: {len(bm_df)} bars (minimum 50 required)"
        )

    bm_close = bm_df["close_price"].astype(float)
    nifty500_close = float(bm_close.iloc[-1])
    nifty500_sma50 = float(bm_close.rolling(50, min_periods=50).mean().iloc[-1])

    # 200-SMA: full 200 days if available; if between 50 and 199, compute available rolling mean
    sma200_min_periods = min(len(bm_close), 200)
    nifty500_sma200 = float(bm_close.rolling(200, min_periods=sma200_min_periods).mean().iloc[-1])

    point_1 = bool(nifty500_close > nifty500_sma50)
    point_2 = bool(nifty500_sma50 > nifty500_sma200)

    # 3. Universe Breadth (% Halal EQ stocks > own SMA50)
    # Determine universe filter
    shariah_exists = _table_exists(conn, "shariah_universe")
    fundamentals_exists = _table_exists(conn, "fundamentals_cache")
    bhav_cols = _get_table_columns(conn, "bhavcopy_daily")

    series_clause = "series = 'EQ'" if "series" in bhav_cols else "1 = 1"

    universe_source = "all_eq"
    if shariah_exists:
        try:
            count_res = conn.execute("SELECT COUNT(*) FROM shariah_universe").fetchone()
            if count_res and count_res[0] > 0:
                symbol_filter = "symbol IN (SELECT symbol FROM shariah_universe WHERE COALESCE(is_compliant, TRUE) = TRUE)"
                universe_source = "shariah_universe"
            else:
                shariah_exists = False
        except Exception:
            shariah_exists = False

    if not shariah_exists and fundamentals_exists:
        try:
            count_res = conn.execute("SELECT COUNT(*) FROM fundamentals_cache").fetchone()
            if count_res and count_res[0] > 0:
                symbol_filter = "symbol IN (SELECT symbol FROM fundamentals_cache)"
                universe_source = "fundamentals_cache"
            else:
                fundamentals_exists = False
        except Exception:
            fundamentals_exists = False

    if not shariah_exists and not fundamentals_exists:
        # Fallback to EQ symbols excluding benchmark
        symbol_filter = f"symbol NOT IN ('{bm_symbol}', 'MONIFTY500', 'NIFTY500', 'NIFTY 500', '^CRSLDX', '^NSEI')"
        universe_source = "bhavcopy_equity"

    try:
        breadth_query = f"""
            WITH ranked_prices AS (
                SELECT
                    symbol,
                    trade_date,
                    close_price,
                    AVG(close_price) OVER (
                        PARTITION BY symbol
                        ORDER BY trade_date
                        ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
                    ) AS sma_50,
                    ROW_NUMBER() OVER (
                        PARTITION BY symbol
                        ORDER BY trade_date DESC
                    ) AS rn,
                    COUNT(*) OVER (
                        PARTITION BY symbol
                    ) AS cnt
                FROM bhavcopy_daily
                WHERE {symbol_filter}
                  AND {series_clause}
                  AND (? IS NULL OR trade_date <= ?)
            )
            SELECT
                COUNT(*) AS total_eligible,
                COALESCE(SUM(CASE WHEN close_price > sma_50 THEN 1 ELSE 0 END), 0) AS above_sma50
            FROM ranked_prices
            WHERE rn = 1 AND cnt >= 50
        """
        breadth_res = conn.execute(breadth_query, [parsed_date, parsed_date]).fetchone()
        total_eligible = int(breadth_res[0]) if breadth_res else 0
        above_sma50 = int(breadth_res[1]) if breadth_res else 0
    except Exception as e:
        logger.warning("Error calculating universe breadth: %s. Defaulting breadth to 0.0.", e)
        total_eligible = 0
        above_sma50 = 0

    breadth_pct = (above_sma50 / total_eligible * 100.0) if total_eligible > 0 else 0.0
    point_3 = bool(breadth_pct > 50.0)

    # 4. Total Score & Regime Mapping
    score = int(point_1) + int(point_2) + int(point_3)

    if score == 3:
        regime = "RISK_ON"
        risk_per_trade_pct = 1.0
        allow_new_entries = True
    elif score == 2:
        regime = "NEUTRAL"
        risk_per_trade_pct = 0.5
        allow_new_entries = True
    else:  # score <= 1
        regime = "RISK_OFF"
        risk_per_trade_pct = 0.0
        allow_new_entries = False

    details = {
        "benchmark_symbol": bm_symbol,
        "as_of_date": str(parsed_date) if parsed_date else str(bm_df["trade_date"].iloc[-1]),
        "point_1_close_gt_sma50": point_1,
        "point_2_sma50_gt_sma200": point_2,
        "point_3_breadth_gt_50": point_3,
        "eligible_universe_count": total_eligible,
        "stocks_above_sma50_count": above_sma50,
        "universe_source": universe_source,
        "fail_closed": False,
    }

    return RegimeState(
        regime=regime,
        score=score,
        risk_per_trade_pct=risk_per_trade_pct,
        allow_new_entries=allow_new_entries,
        nifty500_close=round(nifty500_close, 2),
        nifty500_sma50=round(nifty500_sma50, 2),
        nifty500_sma200=round(nifty500_sma200, 2),
        breadth_pct=round(breadth_pct, 2),
        details=details,
    )


def get_current_regime(
    conn: Optional[duckdb.DuckDBPyConnection] = None,
    as_of_date: Optional[Any] = None
) -> RegimeState:
    """
    Helper function to get current market regime.
    If conn is None, manages a thread-safe read connection automatically.
    """
    if conn is not None:
        return compute_market_regime(conn, as_of_date=as_of_date)

    try:
        from src.db.session import get_read_connection
        with get_read_connection() as r_conn:
            return compute_market_regime(r_conn, as_of_date=as_of_date)
    except Exception as e:
        logger.debug("Could not use get_read_connection: %s. Trying standalone connect.", e)
        try:
            import duckdb
            from src.db.session import get_db_path
            db_path = get_db_path()
            with duckdb.connect(db_path, read_only=True) as direct_conn:
                return compute_market_regime(direct_conn, as_of_date=as_of_date)
        except Exception as e2:
            return _fail_closed(f"Failed to open database connection: {e2}")
