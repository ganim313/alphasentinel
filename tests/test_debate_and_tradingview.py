import pytest
from unittest.mock import patch, MagicMock
from src.ingestion.tradingview import get_tradingview_technical_ratings
from src.ingestion.macro_feeds import fetch_macro_weather_data
from src.agents.tools import (
    tool_get_stock_fundamentals,
    tool_get_technical_analysis,
    tool_get_macro_weather,
    tool_get_portfolio_status
)
from src.mcp_server import handle_rpc_request
from src.agents.debate_graph import build_debate_graph, deterministic_risk_node, risk_router
from src.notification.trade_card import format_telegram_trade_card

def test_tradingview_ingestion_fallback():
    """Verify TradingView ingestion handles invalid symbols gracefully with soft fallback."""
    res = get_tradingview_technical_ratings("INVALID_TICKER_XYZ")
    assert isinstance(res, dict)
    assert "recommendation" in res
    assert res["recommendation"] in ["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
    assert "summary" in res

def test_macro_feeds_structure():
    """Verify macro radar returns required regime scores and metrics."""
    data = fetch_macro_weather_data()
    assert isinstance(data, dict)
    assert "market_regime" in data
    assert data["market_regime"] in ["BULLISH_FAVORABLE", "CAUTIOUS", "HIGH_RISK"]
    assert "macro_weather_score" in data
    assert 0.0 <= data["macro_weather_score"] <= 1.0
    assert "target_cash_exposure_pct" in data

def test_mcp_tools_execution():
    """Verify all modular MCP tools return valid dicts without exceptions."""
    tv_res = tool_get_technical_analysis("TATASTEEL")
    assert isinstance(tv_res, dict)
    
    macro_res = tool_get_macro_weather()
    assert isinstance(macro_res, dict)
    assert "market_regime" in macro_res
    
    port_res = tool_get_portfolio_status()
    assert isinstance(port_res, dict)
    assert "open_positions_count" in port_res

def test_mcp_server_rpc_dispatch():
    """Verify MCP JSON-RPC 2.0 tool listing and call handling."""
    # Test tools/list
    list_req = '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
    list_res = handle_rpc_request(list_req)
    assert "get_stock_fundamentals" in list_res
    assert "get_technical_analysis" in list_res
    
    # Test ping
    ping_req = '{"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}'
    ping_res = handle_rpc_request(ping_req)
    assert '"result": "pong"' in ping_res

def test_deterministic_risk_node():
    """Verify pure Python deterministic risk node calculates proper sizing and stops."""
    state = {
        "symbol": "TATASTEEL",
        "trigger_price": 150.0,
        "current_price": 149.5,
        "adtv_20d": 10000000.0,
        "circuit_band": 20.0,
        "fundamentals": {"atr_14": 5.0, "sector": "METALS"},
        "macro_weather": {"market_regime": "BULLISH_FAVORABLE"}
    }
    res = deterministic_risk_node(state)
    assert "risk_verdict" in res
    assert res["risk_verdict"] in ["APPROVE", "APPROVE_WITH_WARNING", "REDUCE_SIZE", "REJECT"]
    assert res["stop_loss_price"] > 0
    assert res["target_1_price"] > res["stop_loss_price"]

def test_debate_graph_compilation_and_routing():
    """Verify debate graph compiles with checkpointer and respects risk routing."""
    app = build_debate_graph()
    assert app is not None
    
    # Test router rejection bypass
    reject_state = {"risk_verdict": "REJECT"}
    assert risk_router(reject_state) == "__end__"
    
    # Test router approval flow
    approve_state = {"risk_verdict": "APPROVE"}
    assert risk_router(approve_state) == "bull_analyst"

def test_trade_card_formatting():
    """Verify rich trade card formats without syntax errors and contains essential sections."""
    sample_state = {
        "symbol": "RELIANCE",
        "trigger_price": 2800.0,
        "current_price": 2795.0,
        "suggested_shares": 50,
        "stop_loss_price": 2720.0,
        "target_1_price": 2960.0,
        "target_2_price": 3100.0,
        "risk_reward_ratio": 2.0,
        "portfolio_allocation_pct": 10.0,
        "risk_verdict": "APPROVE",
        "conviction_score": 8.5,
        "tv_technical_rating": {"recommendation": "STRONG_BUY"},
        "bull_thesis": "Stage 2 Breakout confirmed.",
        "bear_risks": "Approaching historical 52W high resistance.",
        "judge_synthesis": "High conviction trade with clear ATR stop."
    }
    card = format_telegram_trade_card(sample_state)
    assert "ALPHASENTINEL TRADE ALERT: RELIANCE" in card
    assert "8.5/10" in card and "Conviction:" in card
    assert "TradingView Chart" in card
