"""
Global pytest configuration and isolation fixtures.
Ensures that running pytest on local or production VMs:
1. Never dispatches real HTTP messages to the live Telegram chat.
2. Isolates default paper capital (₹10,00,000) from custom dashboard paper_capital_config values.
3. Preserves and restores circuit_breaker_state, strategy_version, and today's equity_curve row
   when tests interact with the primary DuckDB file.
"""

from pathlib import Path
import pytest
from src.config.settings import settings
from src.db.session import get_db_path, get_read_connection, get_write_connection, init_db

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_METRICS_PATH = _PROJECT_ROOT / "dashboard" / "portfolio_metrics.json"
_SNAPSHOT_TABLES = (
    "circuit_breaker_state",
    "strategy_version",
    "equity_curve",
    "macro_weather",
    "agent_memory",
    "positions",
    "screener_candidates",
    "purification_log",
    "corporate_actions",
    "debate_transcripts",
    "paper_capital_config",
    "delisted_stocks",
)


@pytest.fixture(autouse=True)
def isolate_telegram_and_db_state(monkeypatch):
    """
    Global autouse fixture:
    - Clears TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID so send_telegram_* functions operate in
      simulated mode unless a test explicitly sets dummy credentials and mocks requests.
    - Standardizes get_paper_capital to 1_000_000.0 (including direct imports in run_trigger_watcher)
      so custom VM capital configs (e.g. ₹1L) do not cause false 90% drawdown halts or break ₹10L
      baseline assertions.
    - Snapshots and restores all operational DuckDB tables (including full equity_curve with
      recorded_at timestamps) and dashboard/portfolio_metrics.json on the primary database.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr("src.portfolio.paper_capital.get_paper_capital", lambda conn=None: 1_000_000.0)
    monkeypatch.setattr(
        "scripts.run_trigger_watcher.get_paper_capital",
        lambda conn=None: 1_000_000.0,
        raising=False,
    )

    primary_db_path = get_db_path()
    saved_tables = {}
    metrics_existed = _METRICS_PATH.exists()
    saved_metrics_bytes = _METRICS_PATH.read_bytes() if metrics_existed else None

    try:
        init_db()
        with get_read_connection() as conn:
            for tbl in _SNAPSHOT_TABLES:
                try:
                    saved_tables[tbl] = conn.execute(f"SELECT * FROM {tbl}").df()
                except Exception:
                    pass
    except Exception:
        pass

    yield

    # Restore dashboard/portfolio_metrics.json
    try:
        if metrics_existed and saved_metrics_bytes is not None:
            _METRICS_PATH.write_bytes(saved_metrics_bytes)
        elif not metrics_existed and _METRICS_PATH.exists():
            _METRICS_PATH.unlink()
    except Exception:
        pass

    # Only restore if get_db_path() still points to the primary DB
    try:
        if get_db_path() == primary_db_path:
            with get_write_connection() as conn:
                for tbl, df in saved_tables.items():
                    try:
                        conn.execute(f"DELETE FROM {tbl}")
                        if not df.empty:
                            view_name = f"_saved_{tbl}"
                            conn.register(view_name, df)
                            conn.execute(f"INSERT INTO {tbl} SELECT * FROM {view_name}")
                            conn.unregister(view_name)
                    except Exception:
                        pass

                conn.execute(
                    "DELETE FROM bhavcopy_daily WHERE symbol LIKE 'TEST_%' "
                    "OR symbol LIKE 'UV_TEST_%' OR symbol LIKE 'UV_NULL_%'"
                )
                conn.execute("DELETE FROM fundamentals_cache WHERE symbol LIKE 'TEST_%'")
                conn.execute("DELETE FROM promoter_pledge_history WHERE symbol LIKE 'TEST_%'")
    except Exception:
        pass

