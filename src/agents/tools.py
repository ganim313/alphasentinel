"""
AlphaSentinel Modular Tooling Layer (Inspired by QuantDinger).
Provides deterministic tools for LangGraph Agents and MCP Clients.
"""

import logging
from typing import Dict, Any, List
from src.ingestion.tradingview import get_tradingview_technical_ratings
from src.ingestion.macro_feeds import fetch_macro_weather_data
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)

def tool_get_stock_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Fetches fundamental metrics, Shariah compliance status, and ratios for an NSE stock.
    """
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    try:
        from src.ingestion.screener_scraper import scrape_screener_fundamentals
        data = scrape_screener_fundamentals(clean_sym)
        return data or {"symbol": clean_sym, "status": "NO_DATA"}
    except Exception as e:
        logger.warning(f"Error fetching fundamentals for {clean_sym}: {e}")
        return {"symbol": clean_sym, "error": str(e)}

def tool_get_technical_analysis(symbol: str, interval: str = "1d") -> Dict[str, Any]:
    """
    Fetches TradingView 26-indicator consensus rating and key technicals (RSI, MACD, EMAs).
    """
    return get_tradingview_technical_ratings(symbol, interval=interval)

def tool_get_macro_weather() -> Dict[str, Any]:
    """
    Fetches live macro regime indicators (US VIX, S&P 500, Crude, USDINR, Target Cash).
    """
    return fetch_macro_weather_data()

def tool_get_portfolio_status() -> Dict[str, Any]:
    """
    Fetches open paper/live positions, total exposure, and realized P&L from DuckDB.
    """
    try:
        with get_read_connection() as conn:
            pos_df = conn.execute("SELECT symbol, entry_date, entry_price, current_ltp, unrealized_pnl, status FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')").df()
            pnl_res = conn.execute("SELECT COALESCE(SUM(realized_pnl), 0.0) FROM positions").fetchone()
            realized_pnl = float(pnl_res[0]) if pnl_res else 0.0
            
            return {
                "open_positions_count": len(pos_df),
                "open_positions": pos_df.to_dict(orient="records"),
                "total_realized_pnl": realized_pnl
            }
    except Exception as e:
        logger.error(f"Error querying portfolio status: {e}")
        return {"error": str(e), "open_positions_count": 0, "open_positions": []}
