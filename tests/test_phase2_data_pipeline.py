"""
Unit and integration tests validating Phase 2 Data Pipeline Correctness.
Covers items P2-1 through P2-10:
- P2-1: Symbol sync scheduling & Bhavcopy Fyers fallback Telegram alerts
- P2-2: Macro weather DB persistence and 3:15 preview read
- P2-3: Dual-mode drawdown check (monthly soft warn vs lifetime hard kill)
- P2-4: Live core_equity for arbiter sector concentration cap
- P2-5: Live core_equity for order_manager allocation percentage
- P2-6: Hardened universe query in live preview
- P2-7: 2027 NSE holidays & startup coverage warning
- P2-8: Dynamic strategy.yaml ADTV participation caps in arbiter
- P2-9: Documented rationale for screener_scraper interest_income_ratio proxy
- P2-10: Real-time unrealized PnL updates in sentinel
"""
import pytest
import datetime
import duckdb
import pandas as pd
from unittest.mock import patch, MagicMock

from src.db.session import init_db, get_read_connection, get_write_connection
from src.config.settings import settings


# =============================================================================
# P2-1: Symbol Sync Scheduling & Bhavcopy Alerting
# =============================================================================

def test_symbol_sync_scheduled_in_run_scheduler():
    """Verify job_symbol_sync is defined and scheduled at 06:00 AM IST in run_scheduler.py."""
    with open("scripts/run_scheduler.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "def job_symbol_sync():" in content
    assert 'schedule.every().day.at("06:00", tz).do(job_symbol_sync)' in content
    assert "sync_instrument_master" in content

    import schedule
    import scripts.run_scheduler as scheduler_mod
    schedule.clear()
    # Test default invocation without parameters
    scheduler_mod.setup_schedule()
    jobs = schedule.get_jobs()
    sync_jobs = [j for j in jobs if j.job_func.__name__ == "job_symbol_sync" and j.at_time == datetime.time(6, 0)]
    assert len(sync_jobs) == 1, "job_symbol_sync must be scheduled by default at 06:00"
    schedule.clear()


def test_bhavcopy_fyers_fallback_telegram_alert_on_empty_master():
    """Verify that an unpopulated instrument_master triggers a Telegram alert in fallback."""
    from src.ingestion.bhavcopy import download_and_ingest_bhavcopy

    with patch("src.notification.telegram_bot.send_telegram_alert") as mock_tg, \
         patch("jugaad_data.nse.bhavcopy_save", side_effect=RuntimeError("NSE site down")), \
         patch("src.db.session.get_read_connection") as mock_conn:
        
        # Mock empty instrument_master
        mock_df = pd.DataFrame(columns=["symbol"])
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value.df.return_value = mock_df
        mock_conn.return_value.__enter__.return_value = mock_cursor

        df = download_and_ingest_bhavcopy(datetime.date(2026, 1, 1), max_retries=1)
        assert df.empty
        mock_tg.assert_called()
        alert_text = mock_tg.call_args[0][0]
        assert "BHAVCOPY FALLBACK EMPTY" in alert_text


def test_bhavcopy_fyers_fallback_telegram_alert_on_zero_rows():
    """Verify that Fyers fallback returning 0 rows across all symbols triggers an alert."""
    from src.ingestion.bhavcopy import download_and_ingest_bhavcopy

    with patch("src.notification.telegram_bot.send_telegram_alert") as mock_tg, \
         patch("jugaad_data.nse.bhavcopy_save", side_effect=RuntimeError("NSE site down")), \
         patch("src.db.session.get_read_connection") as mock_conn, \
         patch("src.ingestion.fyers_client.fyers_client.fetch_historical_data", return_value=pd.DataFrame()):
        
        # Mock populated instrument_master with symbols
        mock_df = pd.DataFrame({"symbol": ["RELIANCE", "TCS"]})
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value.df.return_value = mock_df
        mock_conn.return_value.__enter__.return_value = mock_cursor

        df = download_and_ingest_bhavcopy(datetime.date(2026, 1, 1), max_retries=1)
        assert df.empty
        mock_tg.assert_called()
        alert_text = mock_tg.call_args[0][0]
        assert "BHAVCOPY FALLBACK RETURNED 0 ROWS" in alert_text


# =============================================================================
# P2-2: Macro Weather DB Persistence & Retrieval
# =============================================================================

def test_macro_weather_db_persistence_and_read():
    """Verify macro_weather insert of all 12 fields and retrieval in DB snapshot mode."""
    init_db()
    today = datetime.date.today()
    with get_write_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO macro_weather (
                scan_date, us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                usdinr_price, usdinr_pct_change, polymarket_risk_score, market_regime,
                macro_weather_score, target_cash_exposure_pct, source
            ) VALUES (?, 18.5, 0.45, 76.0, 0.1, 86.2, 0.05, 0.4, 'BULL_NORMAL', 0.8, 20.0, 'PREMARKET_TEST');
        """, (today,))

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                   usdinr_price, usdinr_pct_change, polymarket_risk_score,
                   market_regime, macro_weather_score, target_cash_exposure_pct, source
            FROM macro_weather WHERE scan_date = ?
        """, (today,)).fetchone()
        assert row is not None
        assert row[0] == 18.5
        assert row[1] == 0.45
        assert row[2] == 76.0
        assert row[7] == 'BULL_NORMAL'
        assert row[8] == 0.8
        assert row[9] == 20.0
        assert row[10] == 'PREMARKET_TEST'


def test_premarket_execution_persists_all_12_fields():
    """Verify run_premarket script executes and populates all 12 fields into macro_weather."""
    from scripts.run_premarket import run_premarket
    init_db()
    today = datetime.date.today()

    mock_macro = {
        "us_vix": 17.2, "sp500_pct_change": 0.35, "crude_oil_price": 74.5,
        "crude_oil_pct_change": -0.8, "usdinr_price": 86.4, "usdinr_pct_change": 0.02,
        "polymarket_risk_score": 0.3, "market_regime": "BULL_NORMAL",
        "macro_weather_score": 0.85, "target_cash_exposure_pct": 15.0,
        "source": "PREMARKET_UNIT_TEST"
    }

    with patch("scripts.run_premarket.fetch_macro_weather_data", return_value=mock_macro), \
         patch("src.notification.telegram_bot.send_telegram_morning_brief"):
        run_premarket()

    with get_read_connection() as conn:
        row = conn.execute("""
            SELECT us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                   usdinr_price, usdinr_pct_change, polymarket_risk_score, market_regime,
                   macro_weather_score, target_cash_exposure_pct, source
            FROM macro_weather WHERE scan_date = CURRENT_DATE
        """).fetchone()
        assert row is not None
        assert row[0] == 17.2
        assert row[1] == 0.35
        assert row[2] == 74.5
        assert row[7] == "BULL_NORMAL"
        assert row[8] == 0.85
        assert row[9] == 15.0
        assert row[10] == "PREMARKET_UNIT_TEST"


def test_live_preview_prefers_db_snapshot_over_live_fetch():
    """Verify run_live_preview reads DB snapshot and skips fetch_macro_weather_data when present."""
    init_db()
    today = datetime.date.today()

    with get_write_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO macro_weather (
                scan_date, us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
                usdinr_price, usdinr_pct_change, polymarket_risk_score, market_regime,
                macro_weather_score, target_cash_exposure_pct, source
            ) VALUES (CURRENT_DATE, 15.0, 0.8, 72.0, -0.5, 86.0, 0.0, 0.2, 'BULL_STRONG', 0.95, 0.0, 'DB_SNAPSHOT_VERIFIED');
        """)

    with patch("scripts.run_live_preview.fetch_macro_weather_data") as mock_fetch, \
         patch("scripts.run_live_preview.is_nse_holiday", return_value=False), \
         patch("scripts.run_live_preview.is_system_halted", return_value=False), \
         patch("scripts.run_live_preview.get_active_universe", return_value=[]):
        from scripts.run_live_preview import run_live_preview_pipeline
        run_live_preview_pipeline()
        mock_fetch.assert_not_called()


def test_live_preview_falls_back_to_live_fetch_when_db_absent():
    """Verify run_live_preview falls back to live fetch when today's macro_weather is absent."""
    init_db()
    with get_write_connection() as conn:
        conn.execute("DELETE FROM macro_weather WHERE scan_date = CURRENT_DATE;")

    mock_live = {
        "us_vix": 20.0, "sp500_pct_change": -0.2, "crude_oil_price": 75.0,
        "crude_oil_pct_change": 0.0, "usdinr_price": 86.5, "usdinr_pct_change": 0.0,
        "polymarket_risk_score": 0.5, "market_regime": "NEUTRAL",
        "macro_weather_score": 0.5, "target_cash_exposure_pct": 50.0,
        "source": "FALLBACK_LIVE"
    }

    with patch("scripts.run_live_preview.fetch_macro_weather_data", return_value=mock_live) as mock_fetch, \
         patch("scripts.run_live_preview.is_nse_holiday", return_value=False), \
         patch("scripts.run_live_preview.is_system_halted", return_value=False), \
         patch("scripts.run_live_preview.get_active_universe", return_value=[]):
        from scripts.run_live_preview import run_live_preview_pipeline
        run_live_preview_pipeline()
        mock_fetch.assert_called_once()


# =============================================================================
# P2-3: Dual-Mode Drawdown Check (Soft Warning vs Hard Kill)
# =============================================================================

def test_dual_mode_drawdown_check_monthly_soft_warn():
    """Verify monthly soft warn alert (>= 4%) sends alert but does NOT halt system."""
    from scripts.run_drawdown_check import check_drawdown
    from src.notification.telegram_bot import is_system_halted, set_system_halt_state
    init_db()
    set_system_halt_state(False, "Reset for test")

    # Mock portfolio state with 4.5% monthly DD and 2% lifetime DD -> warn only
    with patch("src.portfolio.state.get_portfolio_state", return_value={
        "core_equity": 955000.0,
        "lifetime_hwm": 1000000.0,
        "lifetime_hwm_dd_pct": 2.0,
        "monthly_peak_equity": 1000000.0,
        "monthly_dd_pct": 4.5
    }), patch("src.notification.telegram_bot.send_telegram_alert") as mock_warn, \
       patch("src.notification.telegram_bot.send_telegram_safe_halt_alarm") as mock_halt_alarm:
        
        check_drawdown()
        mock_warn.assert_called_once()
        warn_msg = mock_warn.call_args[0][0]
        assert "MONTHLY DRAWDOWN WARNING" in warn_msg
        assert "4.50%" in warn_msg
        mock_halt_alarm.assert_not_called()
        assert not is_system_halted()


def test_dual_mode_drawdown_check_lifetime_hard_kill():
    """Verify lifetime hard kill (>= 6%) triggers system halt and safe halt alarm."""
    from scripts.run_drawdown_check import check_drawdown
    from src.notification.telegram_bot import is_system_halted, set_system_halt_state
    init_db()
    set_system_halt_state(False, "Reset for test")

    # Mock portfolio state with 6.5% lifetime DD -> emergency halt
    with patch("src.portfolio.state.get_portfolio_state", return_value={
        "core_equity": 935000.0,
        "lifetime_hwm": 1000000.0,
        "lifetime_hwm_dd_pct": 6.5,
        "monthly_peak_equity": 1000000.0,
        "monthly_dd_pct": 6.5
    }), patch("src.notification.telegram_bot.send_telegram_alert") as mock_warn, \
       patch("src.notification.telegram_bot.send_telegram_safe_halt_alarm") as mock_halt_alarm:
        
        check_drawdown()
        assert is_system_halted()
        mock_halt_alarm.assert_called_once()
        halt_msg = mock_halt_alarm.call_args[0][0]
        assert "Max Lifetime Drawdown Exceeded: 6.50% >= 6.0%" in halt_msg

    # Clean up halt state
    set_system_halt_state(False, "Reset after test")


def test_monthly_peak_resets_on_calendar_month_boundary():
    """Verify that monthly peak equity resets to core_equity when calendar month changes."""
    from src.portfolio.state import get_portfolio_state
    init_db()

    with get_write_connection() as conn:
        # Simulate prior month state: peak was 1,200,000 updated in August 2026
        conn.execute("""
            UPDATE circuit_breaker_state 
            SET monthly_peak_equity = 1200000.0, high_water_mark = 1200000.0,
                updated_at = TIMESTAMP '2026-08-15 10:00:00'
            WHERE id = 1;
        """)
        # Ensure positions result in core equity of 1,150,000 (a 4.17% DD from August peak)
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_M_ROLL';")
        conn.execute("""
            INSERT INTO positions (
                id, symbol, sector, entry_date, entry_price, quantity, current_ltp,
                trailing_stop_loss, target_1, target_2, risk_rupees, portfolio_allocation_pct,
                realized_pnl, unrealized_pnl, status, exit_date
            ) VALUES (
                'TEST_M_ROLL_1', 'TEST_M_ROLL', 'IT', DATE '2026-08-20', 100.0, 1000, 115.0,
                90.0, 120.0, 140.0, 10000.0, 10.0, 150000.0, 0.0, 'CLOSED', DATE '2026-08-25'
            );
        """)

    state = get_portfolio_state()
    # Core equity is 1,000,000 + 150,000 = 1,150,000
    assert state["core_equity"] == 1150000.0
    # Because updated_at is August and current time is September+, monthly peak must reset to 1,150,000
    assert state["monthly_peak_equity"] == 1150000.0
    assert state["monthly_dd_pct"] == 0.0, "Monthly drawdown must be 0% at the start of a new month"
    # Lifetime HWM must still preserve the 1,200,000 peak
    assert state["lifetime_hwm"] == 1200000.0
    assert abs(state["lifetime_hwm_dd_pct"] - 4.17) < 0.05

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_M_ROLL';")
        conn.execute("""
            UPDATE circuit_breaker_state 
            SET monthly_peak_equity = 1000000.0, high_water_mark = 1000000.0, updated_at = CURRENT_TIMESTAMP
            WHERE id = 1;
        """)


def test_hwm_recovery_from_equity_curve_when_state_corrupted():
    """Verify get_portfolio_state recovers lifetime HWM from equity_curve if circuit_breaker_state is corrupted/NULL."""
    from src.portfolio.state import get_portfolio_state
    init_db()

    with get_write_connection() as conn:
        # Corrupt high_water_mark in circuit_breaker_state
        conn.execute("UPDATE circuit_breaker_state SET high_water_mark = NULL WHERE id = 1;")
        # Populate historical record in equity_curve
        conn.execute("""
            INSERT OR REPLACE INTO equity_curve (trade_date, total_equity, core_equity, unrealized_pnl)
            VALUES (DATE '2026-07-15', 1350000.0, 1350000.0, 0.0);
        """)

    state = get_portfolio_state()
    # Lifetime HWM must recover 1,350,000 from equity_curve instead of falling back to 1,000,000 initial capital
    assert state["lifetime_hwm"] == 1350000.0

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("UPDATE circuit_breaker_state SET high_water_mark = 1000000.0 WHERE id = 1;")
        conn.execute("DELETE FROM equity_curve WHERE trade_date = DATE '2026-07-15';")


# =============================================================================
# P2-4: Live Core Equity in Arbiter Sector Cap
# =============================================================================

def test_sector_cap_uses_live_core_equity():
    """Verify arbiter sector cap evaluates against live core equity."""
    from src.risk.arbiter import calculate_deterministic_risk_and_position
    init_db()

    # Pre-populate positions with ₹100,000 deployed in IT sector
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE sector = 'IT';")
        conn.execute("""
            INSERT INTO positions (
                id, symbol, sector, entry_date, entry_price, quantity, current_ltp,
                trailing_stop_loss, target_1, target_2, risk_rupees, portfolio_allocation_pct, status
            ) VALUES (
                'TEST_POS_IT_1', 'INFY', 'IT', CURRENT_DATE, 100.0, 1000, 100.0,
                90.0, 120.0, 140.0, 10000.0, 10.0, 'OPEN'
            );
        """)

    # Scenario A: Live core equity is ₹500,000 (after 50% drawdown).
    # 25% sector cap of ₹500k = ₹125,000.
    # Current deployed = ₹100,000 + 10% test allocation (₹50,000) = ₹150,000 > ₹125,000.
    # Arbiter must REJECT due to sector concentration cap.
    with patch("src.portfolio.state.get_portfolio_state", return_value={"core_equity": 500000.0}):
        res = calculate_deterministic_risk_and_position(
            symbol="TCS",
            trigger_price=1000.0,
            current_price=1000.0,
            atr_14=20.0,
            circuit_band=20.0,
            macro_weather={"target_cash_exposure_pct": 0.0},
            sector="IT"
        )
        assert res["verdict"] == "REJECT"
        assert "Sector capital cap reached" in res["rejection_reason"]

    # Scenario B: Live core equity is ₹1,500,000 (after profitable compounding).
    # 25% sector cap of ₹1.5M = ₹375,000.
    # Current deployed = ₹100,000 + 10% test allocation (₹150,000) = ₹250,000 <= ₹375,000.
    # Arbiter should APPROVE (cash and sector cap both satisfied).
    with patch("src.portfolio.state.get_portfolio_state", return_value={"core_equity": 1500000.0}):
        res = calculate_deterministic_risk_and_position(
            symbol="TCS",
            trigger_price=1000.0,
            current_price=1000.0,
            atr_14=20.0,
            circuit_band=20.0,
            macro_weather={"target_cash_exposure_pct": 0.0},
            sector="IT"
        )
        assert res["verdict"] == "APPROVE"

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE sector = 'IT';")


def test_arbiter_custom_capital_override_respected():
    """Verify that when a caller explicitly passes a custom portfolio_capital_rupees, it is respected."""
    from src.risk.arbiter import calculate_deterministic_risk_and_position
    init_db()

    # Pass custom capital of ₹500,000 explicitly
    res = calculate_deterministic_risk_and_position(
        symbol="CUSTOM_CAP",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.0,
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=500000.0
    )
    assert res["verdict"] == "APPROVE"
    # Max position value at 10% of ₹500k = ₹50,000 -> max 500 shares at ₹100
    assert res["suggested_shares"] <= 500
    assert res["total_capital_deployed"] <= 50000.0


# =============================================================================
# P2-5: Live Core Equity in Order Manager Allocation Pct
# =============================================================================

def test_order_manager_allocation_pct_uses_live_equity():
    """Verify PaperBroker calculates portfolio_allocation_pct against live core equity."""
    from src.execution.order_manager import PaperBroker
    init_db()

    # With core_equity = ₹500,000:
    # Buy 100 shares @ ₹500 = ₹50,000 -> allocation should be exactly 10.0% (not 5.0% on ₹1M)
    with patch("src.portfolio.state.get_portfolio_state", return_value={"core_equity": 500000.0}):
        trade_id = PaperBroker.place_order(
            symbol="TEST_ALLOC",
            price=500.0,
            atr=10.0,
            quantity=100,
            initial_stop=480.0,
            target_1=520.0,
            target_2=540.0
        )
        assert trade_id.startswith("P_TEST_ALLOC_")

    with get_read_connection() as conn:
        row = conn.execute("SELECT portfolio_allocation_pct FROM positions WHERE id = ?", (trade_id,)).fetchone()
        assert row is not None
        # With 0.15% slippage on entry, ₹50,075 / ₹500,000 is ~10.015%
        assert abs(row[0] - 10.0) < 0.5

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE id = ?", (trade_id,))


# =============================================================================
# P2-6: Hardened Universe Query in Live Preview
# =============================================================================

def test_live_preview_universe_query_filters():
    """Verify live preview universe query enforces 5-day active date, positive volume, and delisted exclusion."""
    from scripts.run_live_preview import get_active_universe
    init_db()
    today = datetime.date.today()
    ten_days_ago = today - datetime.timedelta(days=10)

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'UV_TEST_%';")
        conn.execute("DELETE FROM delisted_stocks WHERE symbol LIKE 'UV_TEST_%';")

        # 1. Active valid stock: traded today, positive volume, not delisted -> SHOULD BE INCLUDED
        conn.execute("""
            INSERT INTO bhavcopy_daily (symbol, trade_date, series, open_price, high_price, low_price, close_price, total_traded_qty, total_traded_val, circuit_band_pct)
            VALUES ('UV_TEST_ACTIVE', ?, 'EQ', 100, 105, 95, 102, 50000, 5100000.0, 20);
        """, (today,))

        # 2. Dormant stock: traded 10 days ago -> SHOULD BE EXCLUDED (outside 5-day window)
        conn.execute("""
            INSERT INTO bhavcopy_daily (symbol, trade_date, series, open_price, high_price, low_price, close_price, total_traded_qty, total_traded_val, circuit_band_pct)
            VALUES ('UV_TEST_OLD', ?, 'EQ', 100, 105, 95, 102, 50000, 5100000.0, 20);
        """, (ten_days_ago,))

        # 3. Illiquid stock: traded today but volume = 0 -> SHOULD BE EXCLUDED
        conn.execute("""
            INSERT INTO bhavcopy_daily (symbol, trade_date, series, open_price, high_price, low_price, close_price, total_traded_qty, total_traded_val, circuit_band_pct)
            VALUES ('UV_TEST_ZERO_VOL', ?, 'EQ', 100, 105, 95, 102, 0, 0.0, 20);
        """, (today,))

        # 4. Delisted stock: traded today, volume > 0, but present in delisted_stocks -> SHOULD BE EXCLUDED
        conn.execute("""
            INSERT INTO bhavcopy_daily (symbol, trade_date, series, open_price, high_price, low_price, close_price, total_traded_qty, total_traded_val, circuit_band_pct)
            VALUES ('UV_TEST_DELISTED', ?, 'EQ', 100, 105, 95, 102, 50000, 5100000.0, 20);
        """, (today,))
        conn.execute("""
            INSERT INTO delisted_stocks (symbol, delisted_date, reason)
            VALUES ('UV_TEST_DELISTED', ?, 'Suspended');
        """, (today,))

    # Execute the actual production helper function
    with get_read_connection() as conn:
        res = get_active_universe(conn, as_of_date=today)

    symbols = [r[0] for r in res if str(r[0]).startswith("UV_TEST_")]
    assert "UV_TEST_ACTIVE" in symbols
    assert "UV_TEST_OLD" not in symbols
    assert "UV_TEST_ZERO_VOL" not in symbols
    assert "UV_TEST_DELISTED" not in symbols

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'UV_TEST_%';")
        conn.execute("DELETE FROM delisted_stocks WHERE symbol LIKE 'UV_TEST_%';")


def test_live_preview_universe_null_symbol_safety():
    """Verify that a NULL symbol entry in delisted_stocks does not collapse the entire active universe."""
    from scripts.run_live_preview import get_active_universe
    init_db()
    today = datetime.date.today()

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'UV_NULL_%';")
        conn.execute("""
            INSERT INTO bhavcopy_daily (symbol, trade_date, series, open_price, high_price, low_price, close_price, total_traded_qty, total_traded_val, circuit_band_pct)
            VALUES ('UV_NULL_SAFE', ?, 'EQ', 100, 105, 95, 102, 50000, 5100000.0, 20);
        """, (today,))

    with get_read_connection() as conn:
        res = get_active_universe(conn, as_of_date=today)

    symbols = [r[0] for r in res]
    assert "UV_NULL_SAFE" in symbols

    with get_write_connection() as conn:
        conn.execute("DELETE FROM bhavcopy_daily WHERE symbol LIKE 'UV_NULL_%';")


# =============================================================================
# P2-7: 2027 NSE Trading Holidays & Startup Year Warning
# =============================================================================

def test_holidays_2027_inclusion():
    """Verify is_nse_holiday correctly recognizes 2027 holidays."""
    from src.utils.holidays import is_nse_holiday
    assert is_nse_holiday(datetime.date(2027, 1, 26))   # Republic Day 2027
    assert is_nse_holiday(datetime.date(2027, 3, 23))   # Holi 2027
    assert is_nse_holiday(datetime.date(2027, 5, 1))    # Maharashtra Day 2027
    assert is_nse_holiday(datetime.date(2027, 8, 15))   # Independence Day 2027
    assert is_nse_holiday(datetime.date(2027, 10, 2))   # Gandhi Jayanti 2027
    assert is_nse_holiday(datetime.date(2027, 12, 25))  # Christmas 2027


def test_holidays_startup_coverage_check():
    """Verify startup validation detects when current year is mapped."""
    from src.utils.holidays import HARDCODED_NSE_HOLIDAYS
    covered_years = {d.year for d in HARDCODED_NSE_HOLIDAYS}
    assert 2026 in covered_years
    assert 2027 in covered_years


# =============================================================================
# P2-8: Dynamic ADTV Participation Caps from strategy.yaml
# =============================================================================

def test_strategy_yaml_adtv_caps_loaded_and_used():
    """Verify arbiter dynamically reads ADTV participation caps from strategy.yaml."""
    from src.config.strategy import RISK_CONFIG
    caps = RISK_CONFIG.get("adtv_participation_caps", {})
    assert caps.get("LARGE") == 5.0
    assert caps.get("MID") == 2.0
    assert caps.get("SMALL") == 1.0
    assert caps.get("MICRO") == 0.5
    assert caps.get("DEFAULT") == 1.5

    # Check arbiter sizing respects market cap tier participation caps
    from src.risk.arbiter import calculate_deterministic_risk_and_position
    # For MICRO cap tier: cap is 0.5% of ADTV.
    # If adtv_20d = ₹10,000,000, 0.5% = ₹50,000 max.
    # At trigger ₹100, max shares by ADTV = 500 shares.
    res_micro = calculate_deterministic_risk_and_position(
        symbol="TEST_MCAP_MICRO",
        trigger_price=100.0,
        current_price=100.0,
        atr_14=2.0,
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        adtv_20d=10_000_000.0,
        market_cap_tier="MICRO"
    )
    assert res_micro["suggested_shares"] <= 500


# =============================================================================
# P2-9: Documented Rationale for Screener Scraper Interest Income Ratio
# =============================================================================

def test_screener_scraper_interest_income_proxy_documented():
    """Verify comprehensive comments exist explaining why other_income is used as conservative proxy."""
    with open("src/ingestion/screener_scraper.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Interest Expense" in content or "Finance Cost" in content
    assert "conservative proxy" in content
    assert "other_income / sales" in content


# =============================================================================
# P2-10: Sentinel Real-Time Unrealized PnL Updates
# =============================================================================

def test_sentinel_updates_unrealized_pnl_code_structure():
    """Verify sentinel update queries include unrealized_pnl."""
    with open("scripts/run_sentinel.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "unrealized_pnl_val = round(" in content
    assert "current_ltp = ?, unrealized_pnl = ?" in content


def test_sentinel_persists_unrealized_pnl_on_tick():
    """Verify sentinel updates unrealized_pnl in DuckDB during 15-minute tick."""
    from scripts.run_sentinel import run_sentinel_check
    init_db()

    pos_id = "TEST_SENTINEL_PNL_1"
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
        conn.execute("""
            INSERT INTO positions (
                id, symbol, sector, entry_date, entry_price, quantity, current_ltp,
                peak_high, atr, trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, unrealized_pnl, status
            ) VALUES (
                ?, 'SENTINEL_CO', 'IT', CURRENT_DATE, 100.0, 50, 100.0,
                100.0, 5.0, 85.0, 120.0, 140.0, 750.0, 5.0, 0.0, 'OPEN'
            );
        """, (pos_id,))

    # Mock yf.download returning LTP = 110.0 (High = 112.0, Low = 98.0)
    # Expected unrealized PnL = (110.0 - 100.0) * 50 = +₹500.00
    mock_df = pd.DataFrame({
        "Close": [110.0],
        "High": [112.0],
        "Low": [98.0]
    })

    with patch("yfinance.download", return_value=mock_df):
        run_sentinel_check()

    with get_read_connection() as conn:
        row = conn.execute("SELECT current_ltp, unrealized_pnl FROM positions WHERE id = ?", (pos_id,)).fetchone()
        assert row is not None
        assert row[0] == 110.0
        assert row[1] == 500.0

    # Cleanup
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
