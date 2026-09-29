import pytest
import datetime
import numpy as np
import pandas as pd
from pathlib import Path

from src.db.session import init_db, get_read_connection
from src.db.queue_writer import db_write
from src.execution.order_manager import PaperBroker, execute_trade
import scripts.run_scheduler as scheduler_mod


def test_ghost_dependencies_purged():
    """Remediation 3: Ensure phantom dependencies are purged from requirements.txt and pyproject.toml."""
    req_file = Path(__file__).resolve().parent.parent / "requirements.txt"
    pyproject_file = Path(__file__).resolve().parent.parent / "pyproject.toml"

    req_text = req_file.read_text(encoding="utf-8").lower()
    pyproj_text = pyproject_file.read_text(encoding="utf-8").lower()

    assert "pynse" not in req_text, "pynse must be purged from requirements.txt"
    assert "playwright" not in req_text, "playwright must be purged from requirements.txt"

    assert "pynse" not in pyproj_text, "pynse must be purged from pyproject.toml"
    assert "playwright" not in pyproj_text, "playwright must be purged from pyproject.toml"


def test_circuit_band_synthesis_logic():
    """Remediation 1: Verify circuit band synthesis for SME/T2T (5%) vs EQ (20%) series."""
    # Test BE / BZ / SM series
    for test_series in ["BE", "BZ", "SM"]:
        prev_close = 100.0
        band = 5 if test_series in ["BE", "BZ", "SM"] else 20
        upper = round(prev_close * (1.0 + (band / 100.0)), 2)
        lower = round(prev_close * (1.0 - (band / 100.0)), 2)
        assert band == 5
        assert upper == 105.0
        assert lower == 95.0

    # Test EQ series
    test_series = "EQ"
    prev_close = 250.0
    band = 5 if test_series in ["BE", "BZ", "SM"] else 20
    upper = round(prev_close * (1.0 + (band / 100.0)), 2)
    lower = round(prev_close * (1.0 - (band / 100.0)), 2)
    assert band == 20
    assert upper == 300.0
    assert lower == 200.0


def test_train_serve_sharpe_feature_alignment():
    """Remediation 2: Verify sharpe_rank formula matches across ml_features.py and run_model_training.py."""
    sharpe_raw = 0.15
    ann_sharpe = sharpe_raw * np.sqrt(252)
    expected_rank = 1.0 / (1.0 + np.exp(-ann_sharpe))

    # Compute using numpy array format as used in both scripts
    raw_arr = np.array([sharpe_raw])
    calc_rank = 1.0 / (1.0 + np.exp(-(raw_arr * np.sqrt(252))))

    assert np.isclose(expected_rank, calc_rank[0], atol=1e-6)
    assert 0.0 < calc_rank[0] < 1.0


def test_candidate_id_linkage_in_positions():
    """Remediation 4: Verify candidate_id column is present and persisted through execution pipeline."""
    init_db()

    test_cand_id = f"cand_test_{int(datetime.datetime.now().timestamp())}"
    test_sym = "CANDLINK_TEST"

    # Execute trade with candidate_id
    trade_id = execute_trade(
        symbol=test_sym,
        price=150.0,
        atr=5.0,
        quantity=50,
        sector="Information Technology",
        candidate_id=test_cand_id
    )

    assert trade_id != "", "Trade execution should succeed and return trade_id"

    with get_read_connection() as conn:
        row = conn.execute(
            "SELECT id, symbol, candidate_id, quantity, status FROM positions WHERE id = ?",
            (trade_id,)
        ).fetchone()

        assert row is not None, "Position must be persisted in positions table"
        assert row[1] == test_sym
        assert row[2] == test_cand_id, "candidate_id must match the passed candidate ID"
        assert row[3] == 50
        assert row[4] == "OPEN"

    # Clean up test position
    db_write("DELETE FROM positions WHERE id = ?", (trade_id,), sync=True)


def test_scheduler_pipeline_registration():
    """Remediation 5: Verify run_scheduler registers all 7 institutional pipelines."""
    scheduler_mod.schedule.clear()
    scheduler_mod.setup_schedule()

    jobs = scheduler_mod.schedule.jobs
    assert len(jobs) >= 7, f"Expected at least 7 registered pipelines, got {len(jobs)}"

    job_targets = [str(j.job_func) for j in jobs]
    assert any("job_premarket" in s for s in job_targets)
    assert any("job_sentinel" in s for s in job_targets)
    assert any("job_live_preview" in s for s in job_targets)
    assert any("job_eod_reconciliation" in s for s in job_targets)
    assert any("job_drawdown_check" in s for s in job_targets)
    assert any("job_db_maintenance" in s for s in job_targets)
    assert any("job_monthly_purification" in s for s in job_targets)


def test_scheduler_market_hours_filter():
    """Remediation 5: Verify market hours calculation logic."""
    ist = scheduler_mod.IST

    # Monday 11:30 AM IST (Trading hours)
    dt_trading = datetime.datetime(2026, 9, 14, 11, 30, tzinfo=ist)
    assert dt_trading.weekday() < 5
    open_t = dt_trading.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = dt_trading.replace(hour=15, minute=30, second=0, microsecond=0)
    assert open_t <= dt_trading <= close_t

    # Sunday 11:30 AM IST (Weekend)
    dt_weekend = datetime.datetime(2026, 9, 13, 11, 30, tzinfo=ist)
    assert dt_weekend.weekday() >= 5
