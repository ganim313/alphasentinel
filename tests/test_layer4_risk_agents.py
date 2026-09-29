"""
Unit test suite for Layer 4: Deterministic Risk Arbiter, MCP Server, and Multi-Agent Gateway.
"""

import pytest
import json
from src.risk.arbiter import calculate_deterministic_risk_and_position
from src.mcp_server import handle_rpc_request
from src.agents.tools import tool_get_portfolio_status
from src.db.session import get_write_connection, init_db


def test_arbiter_insolvency_guard():
    res = calculate_deterministic_risk_and_position(
        symbol="INSOLVENT_CO",
        trigger_price=100.0,
        current_price=99.0,
        atr_14=2.0,
        circuit_band=20.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=0.0
    )
    assert res["verdict"] == "REJECT"
    assert res["suggested_shares"] == 0
    assert "equity exhausted" in res["reason"].lower() or "insolvency" in res["reason"].lower()


def test_arbiter_tight_circuit_rejection():
    res = calculate_deterministic_risk_and_position(
        symbol="TIGHT_CO",
        trigger_price=100.0,
        current_price=99.0,
        atr_14=2.0,
        circuit_band=2.0,
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=500000.0
    )
    assert res["verdict"] == "REJECT"
    assert res["suggested_shares"] == 0
    assert "circuit" in res["reason"].lower()


def test_arbiter_nan_circuit_guard():
    import math
    res = calculate_deterministic_risk_and_position(
        symbol="NAN_CO",
        trigger_price=100.0,
        current_price=99.0,
        atr_14=2.0,
        circuit_band=float("nan"),
        macro_weather={"target_cash_exposure_pct": 0.0},
        portfolio_capital_rupees=500000.0
    )
    assert res["verdict"] == "REJECT"
    assert res["suggested_shares"] == 0


def test_mcp_initialize_handshake():
    req = json.dumps({"jsonrpc": "2.0", "id": 42, "method": "initialize", "params": {}})
    resp = json.loads(handle_rpc_request(req))
    assert resp["id"] == 42
    assert resp["result"]["serverInfo"]["name"] == "AlphaSentinel-MCP"
    assert "tools" in resp["result"]["capabilities"]


def test_portfolio_status_tracks_trimmed_runners():
    init_db()
    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_TRIMMED'")
        conn.execute("""
            INSERT INTO positions (
                id, symbol, entry_date, entry_price, quantity, current_ltp,
                trailing_stop_loss, target_1, target_2, risk_rupees,
                portfolio_allocation_pct, status, realized_pnl
            ) VALUES (
                'POS_TEST_TRIMMED', 'TEST_TRIMMED', CURRENT_DATE, 100.0, 50, 105.0,
                100.0, 110.0, 120.0, 500.0, 5.0, 'TARGET_1_TRIMMED', 500.0
            )
        """)
    
    status = tool_get_portfolio_status()
    assert any(p["symbol"] == "TEST_TRIMMED" for p in status["open_positions"])
    assert status["total_realized_pnl"] >= 500.0

    with get_write_connection() as conn:
        conn.execute("DELETE FROM positions WHERE symbol = 'TEST_TRIMMED'")
