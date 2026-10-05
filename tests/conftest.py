"""
Global pytest configuration and isolation fixtures.
Ensures that running pytest on local or production VMs:
1. Never dispatches real HTTP messages to the live Telegram chat.
2. Isolates default paper capital (₹10,00,000) from custom dashboard paper_capital_config values.
3. Preserves and restores circuit_breaker_state, strategy_version, and today's equity_curve row
   when tests interact with the primary DuckDB file.
"""

import pytest
from src.config.settings import settings
from src.db.session import get_db_path, get_read_connection, get_write_connection, init_db


@pytest.fixture(autouse=True)
def isolate_telegram_and_db_state(monkeypatch):
    """
    Global autouse fixture:
    - Clears TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID so send_telegram_* functions operate in
      simulated mode unless a test explicitly sets dummy credentials and mocks requests.
    - Standardizes get_paper_capital to 1_000_000.0 so custom VM capital configs (e.g. ₹1L)
      do not cause false 90% drawdown halts or break ₹10L baseline assertions.
    - Snapshots and restores circuit_breaker_state, strategy_version, and today's equity_curve
      on the primary database.
    """
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_ID", "")
    monkeypatch.setattr("src.portfolio.paper_capital.get_paper_capital", lambda conn=None: 1_000_000.0)

    primary_db_path = get_db_path()
    saved_cb_df = None
    saved_sv_df = None
    saved_eq_df = None

    try:
        init_db()
        with get_read_connection() as conn:
            saved_cb_df = conn.execute("SELECT * FROM circuit_breaker_state WHERE id = 1").df()
            saved_sv_df = conn.execute("SELECT * FROM strategy_version").df()
            saved_eq_df = conn.execute(
                "SELECT * FROM equity_curve WHERE trade_date >= CURRENT_DATE - INTERVAL 1 DAY"
            ).df()
    except Exception:
        pass

    yield

    # Only restore if get_db_path() still points to the primary DB
    try:
        if get_db_path() == primary_db_path:
            with get_write_connection() as conn:
                if saved_cb_df is not None and not saved_cb_df.empty:
                    conn.execute("DELETE FROM circuit_breaker_state WHERE id = 1")
                    conn.register("saved_cb_df", saved_cb_df)
                    conn.execute("INSERT INTO circuit_breaker_state SELECT * FROM saved_cb_df")
                    conn.unregister("saved_cb_df")

                if saved_sv_df is not None:
                    conn.execute("DELETE FROM strategy_version")
                    if not saved_sv_df.empty:
                        conn.register("saved_sv_df", saved_sv_df)
                        conn.execute("INSERT INTO strategy_version SELECT * FROM saved_sv_df")
                        conn.unregister("saved_sv_df")

                if saved_eq_df is not None:
                    conn.execute(
                        "DELETE FROM equity_curve WHERE trade_date >= CURRENT_DATE - INTERVAL 1 DAY"
                    )
                    if not saved_eq_df.empty:
                        conn.register("saved_eq_df", saved_eq_df)
                        conn.execute("INSERT OR REPLACE INTO equity_curve SELECT * FROM saved_eq_df")
                        conn.unregister("saved_eq_df")
    except Exception:
        pass
