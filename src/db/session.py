"""
DuckDB Session & Connection Manager.
Handles thread-safe read connections, process locks, and schema bootstrap.
"""

import duckdb
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Generator
import portalocker
from src.config.settings import settings

db_rlock = threading.RLock()
_local = threading.local()

def get_db_path() -> str:
    # Ensure it supports memory paths cleanly or resolves absolute paths
    return str(settings.BASE_DIR / settings.DUCKDB_PATH) if not str(settings.DUCKDB_PATH).startswith(":") else str(settings.DUCKDB_PATH)


def init_db() -> None:
    """Initialize DuckDB tables using schema.sql and apply backward-compatible column migrations."""
    db_path = get_db_path()
    schema_file = Path(__file__).resolve().parent / "schema.sql"
    
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    lock_path = db_path + ".lock"
    with db_rlock, portalocker.Lock(lock_path, timeout=120):
        conn = duckdb.connect(db_path)
        try:
            conn.execute("PRAGMA threads=2;")
            conn.execute("PRAGMA memory_limit='2GB';")
            conn.execute("SET TimeZone='Asia/Kolkata';")
            # DuckDB Python API cannot execute multi-statement SQL safely
            for stmt in schema_sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            
            # Non-destructive migrations for debate_transcripts
            cols_info = conn.execute("PRAGMA table_info('debate_transcripts')").fetchall()
            existing_cols = [col[1] for col in cols_info]
            
            if existing_cols:
                if "judge_synthesis" not in existing_cols:
                    conn.execute("ALTER TABLE debate_transcripts ADD COLUMN judge_synthesis TEXT;")
                if "tv_technical_rating" not in existing_cols:
                    conn.execute("ALTER TABLE debate_transcripts ADD COLUMN tv_technical_rating VARCHAR;")
                if "target_1" not in existing_cols:
                    conn.execute("ALTER TABLE debate_transcripts ADD COLUMN target_1 DOUBLE;")
                if "target_2" not in existing_cols:
                    conn.execute("ALTER TABLE debate_transcripts ADD COLUMN target_2 DOUBLE;")
                
            # Non-destructive migrations for agent_memory
            mem_cols_info = conn.execute("PRAGMA table_info('agent_memory')").fetchall()
            mem_existing_cols = [col[1] for col in mem_cols_info]
            if mem_existing_cols:
                if "kronos_score" not in mem_existing_cols:
                    conn.execute("ALTER TABLE agent_memory ADD COLUMN kronos_score DOUBLE;")
                if "conviction_score" not in mem_existing_cols:
                    conn.execute("ALTER TABLE agent_memory ADD COLUMN conviction_score DOUBLE;")
                if "content" not in mem_existing_cols:
                    conn.execute("ALTER TABLE agent_memory ADD COLUMN content TEXT;")
                if "outcome_label" not in mem_existing_cols:
                    conn.execute("ALTER TABLE agent_memory ADD COLUMN outcome_label VARCHAR;")

            pos_cols_info = conn.execute("PRAGMA table_info('positions')").fetchall()
            pos_existing_cols = [col[1] for col in pos_cols_info]
            if pos_existing_cols:
                if "atr" not in pos_existing_cols:
                    conn.execute("ALTER TABLE positions ADD COLUMN atr DOUBLE;")
                if "peak_high" not in pos_existing_cols:
                    conn.execute("ALTER TABLE positions ADD COLUMN peak_high DOUBLE;")
                if "candidate_id" not in pos_existing_cols:
                    conn.execute("ALTER TABLE positions ADD COLUMN candidate_id VARCHAR;")
                
            # Non-destructive migrations for bhavcopy_daily
            bhav_cols_info = conn.execute("PRAGMA table_info('bhavcopy_daily')").fetchall()
            bhav_existing_cols = [col[1] for col in bhav_cols_info]
            if bhav_existing_cols:
                if "split_multiplier" not in bhav_existing_cols:
                    conn.execute("ALTER TABLE bhavcopy_daily ADD COLUMN split_multiplier DOUBLE DEFAULT 1.0;")
                if "upper_circuit" not in bhav_existing_cols:
                    conn.execute("ALTER TABLE bhavcopy_daily ADD COLUMN upper_circuit DOUBLE;")
                if "lower_circuit" not in bhav_existing_cols:
                    conn.execute("ALTER TABLE bhavcopy_daily ADD COLUMN lower_circuit DOUBLE;")
                if "circuit_band_pct" not in bhav_existing_cols:
                    conn.execute("ALTER TABLE bhavcopy_daily ADD COLUMN circuit_band_pct INTEGER;")
                if "is_asm" not in bhav_existing_cols:
                    conn.execute("ALTER TABLE bhavcopy_daily ADD COLUMN is_asm BOOLEAN DEFAULT FALSE;")
                if "is_gsm" not in bhav_existing_cols:
                    conn.execute("ALTER TABLE bhavcopy_daily ADD COLUMN is_gsm BOOLEAN DEFAULT FALSE;")

            # Non-destructive migrations for screener_candidates
            sc_cols_info = conn.execute("PRAGMA table_info('screener_candidates')").fetchall()
            sc_existing_cols = [col[1] for col in sc_cols_info]
            if sc_existing_cols:
                if "market_cap_tier" not in sc_existing_cols:
                    conn.execute("ALTER TABLE screener_candidates ADD COLUMN market_cap_tier VARCHAR;")
                if "sector" not in sc_existing_cols:
                    conn.execute("ALTER TABLE screener_candidates ADD COLUMN sector VARCHAR;")
                if "ab_group" not in sc_existing_cols:
                    conn.execute("ALTER TABLE screener_candidates ADD COLUMN ab_group VARCHAR DEFAULT 'control';")

            # Non-destructive migrations for circuit_breaker_state
            cb_cols_info = conn.execute("PRAGMA table_info('circuit_breaker_state')").fetchall()
            cb_existing_cols = [col[1] for col in cb_cols_info]
            if cb_existing_cols:
                if "high_water_mark" not in cb_existing_cols:
                    conn.execute("ALTER TABLE circuit_breaker_state ADD COLUMN high_water_mark DOUBLE DEFAULT 1000000.0;")
                if "monthly_peak_equity" not in cb_existing_cols:
                    conn.execute("ALTER TABLE circuit_breaker_state ADD COLUMN monthly_peak_equity DOUBLE DEFAULT 1000000.0;")
                conn.execute("UPDATE circuit_breaker_state SET high_water_mark = 1000000.0 WHERE high_water_mark IS NULL;")
                conn.execute("UPDATE circuit_breaker_state SET monthly_peak_equity = 1000000.0 WHERE monthly_peak_equity IS NULL;")

            # P1-2: Non-destructive migration for macro_weather table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS macro_weather (
                    scan_date DATE PRIMARY KEY,
                    us_vix DOUBLE,
                    sp500_pct_change DOUBLE,
                    crude_oil_price DOUBLE,
                    crude_oil_pct_change DOUBLE,
                    usdinr_price DOUBLE,
                    usdinr_pct_change DOUBLE,
                    polymarket_risk_score DOUBLE,
                    market_regime VARCHAR,
                    macro_weather_score DOUBLE,
                    target_cash_exposure_pct DOUBLE,
                    source VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
            mw_cols_info = conn.execute("PRAGMA table_info('macro_weather')").fetchall()
            mw_existing_cols = [col[1] for col in mw_cols_info]
            if mw_existing_cols:
                cols_to_add = [
                    ("crude_oil_price", "DOUBLE"),
                    ("crude_oil_pct_change", "DOUBLE"),
                    ("usdinr_price", "DOUBLE"),
                    ("usdinr_pct_change", "DOUBLE"),
                    ("polymarket_risk_score", "DOUBLE"),
                    ("macro_weather_score", "DOUBLE"),
                    ("source", "VARCHAR"),
                ]
                for c_name, c_type in cols_to_add:
                    if c_name not in mw_existing_cols:
                        conn.execute(f"ALTER TABLE macro_weather ADD COLUMN {c_name} {c_type};")

            # P1-2: Non-destructive migration for equity_curve table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS equity_curve (
                    trade_date DATE PRIMARY KEY,
                    total_equity DOUBLE NOT NULL,
                    core_equity DOUBLE,
                    unrealized_pnl DOUBLE,
                    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Non-destructive migrations for purification_log
            pur_cols_info = conn.execute("PRAGMA table_info('purification_log')").fetchall()
            pur_existing_cols = [col[1] for col in pur_cols_info]
            if pur_existing_cols:
                if "id" not in pur_existing_cols:
                    conn.execute("ALTER TABLE purification_log ADD COLUMN id VARCHAR;")

            # P6-4: Non-destructive migration for strategy_version table
            conn.execute("""
                CREATE SEQUENCE IF NOT EXISTS seq_strategy_version START 1;
                CREATE TABLE IF NOT EXISTS strategy_version (
                    id INTEGER DEFAULT nextval('seq_strategy_version') PRIMARY KEY,
                    strategy_name VARCHAR NOT NULL,
                    parameters_hash VARCHAR UNIQUE NOT NULL,
                    parameters_json TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
            """)
                
        finally:
            conn.close()


@contextmanager
def get_read_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """
    Thread-safe and Process-safe read connection.
    If current thread already holds a write connection, reuses it directly.
    Otherwise acquires shared file lock, opens DuckDB in read-only mode, yields connection, and closes.
    If WAL exists, safely checkpoints under exclusive write lock and retries read.
    """
    if getattr(_local, "write_conn", None) is not None:
        yield _local.write_conn
        return

    db_path = get_db_path()
    if not db_path.startswith(":") and not Path(db_path).exists():
        init_db()

    lock_path = db_path + ".lock"
    conn = None
    wal_detected = False
    with db_rlock, portalocker.Lock(lock_path, timeout=120, flags=portalocker.LOCK_SH | portalocker.LOCK_NB, fail_when_locked=False):
        try:
            conn = duckdb.connect(db_path, read_only=True)
        except Exception as e:
            if "WAL file exists" in str(e) or "Cannot open in read-only mode" in str(e):
                wal_detected = True
            else:
                raise

        if not wal_detected and conn is not None:
            try:
                conn.execute("PRAGMA threads=2;")
                conn.execute("PRAGMA memory_limit='2GB';")
                conn.execute("SET TimeZone='Asia/Kolkata';")
                yield conn
                return
            finally:
                conn.close()

    if wal_detected:
        with get_write_connection() as write_conn:
            write_conn.execute("CHECKPOINT;")
            
        with db_rlock, portalocker.Lock(lock_path, timeout=120, flags=portalocker.LOCK_SH | portalocker.LOCK_NB, fail_when_locked=False):
            conn = duckdb.connect(db_path, read_only=True)
            try:
                conn.execute("PRAGMA threads=2;")
                conn.execute("PRAGMA memory_limit='2GB';")
                conn.execute("SET TimeZone='Asia/Kolkata';")
                yield conn
            finally:
                conn.close()


@contextmanager
def get_write_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """
    Thread-safe and Process-safe write connection with thread-local re-entrancy.
    Acquires exclusive file lock, opens DuckDB in read-write mode, yields connection, checkpoints, and closes.
    """
    if getattr(_local, "write_conn", None) is not None:
        _local.write_depth += 1
        try:
            yield _local.write_conn
        finally:
            _local.write_depth -= 1
        return

    db_path = get_db_path()
    if not db_path.startswith(":") and not Path(db_path).exists():
        init_db()

    lock_path = db_path + ".lock"
    with db_rlock, portalocker.Lock(lock_path, timeout=120, flags=portalocker.LOCK_EX | portalocker.LOCK_NB, fail_when_locked=False):
        conn = duckdb.connect(db_path)
        try:
            conn.execute("PRAGMA threads=2;")
            conn.execute("PRAGMA memory_limit='2GB';")
            conn.execute("SET TimeZone='Asia/Kolkata';")
            _local.write_conn = conn
            _local.write_depth = 1
            yield conn
        finally:
            _local.write_conn = None
            _local.write_depth = 0
            try:
                conn.execute("CHECKPOINT;")
            except Exception:
                pass
            conn.close()


