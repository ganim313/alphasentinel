"""
AlphaSentinel Quantitative MCP Server (Model Context Protocol).
Exposes AlphaSentinel's market screening, fundamentals, and portfolio state to AI clients.

Run directly via:
    python -m src.mcp_server
"""

import sys
import json
import logging
from typing import Dict, Any

from src.agents.tools import (
    tool_get_stock_fundamentals,
    tool_get_technical_analysis,
    tool_get_macro_weather,
    tool_get_portfolio_status
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AlphaSentinel-MCP")

AVAILABLE_TOOLS = {
    "get_stock_fundamentals": {
        "description": "Fetch fundamentals, P/E, ROCE, and Shariah debt status for an NSE symbol.",
        "handler": tool_get_stock_fundamentals,
        "parameters": {"symbol": "str"}
    },
    "get_technical_analysis": {
        "description": "Fetch TradingView 26-indicator consensus (BUY/SELL/NEUTRAL) and RSI/MACD/EMAs.",
        "handler": tool_get_technical_analysis,
        "parameters": {"symbol": "str", "interval": "str (optional, default 1d)"}
    },
    "get_macro_weather": {
        "description": "Fetch global market regime radar (US VIX, Crude Oil, USDINR, Target Cash Exposure).",
        "handler": tool_get_macro_weather,
        "parameters": {}
    },
    "get_portfolio_status": {
        "description": "Fetch active positions and realized P&L from DuckDB.",
        "handler": tool_get_portfolio_status,
        "parameters": {}
    }
}

def handle_rpc_request(request_str: str) -> str:
    """Handles JSON-RPC request for MCP execution."""
    try:
        req = json.loads(request_str)
        method = req.get("method")
        req_id = req.get("id", 1)
        params = req.get("params", {})

        if method == "initialize":
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "AlphaSentinel-MCP",
                        "version": "1.0.0"
                    }
                }
            })

        elif method == "notifications/initialized":
            return ""

        elif method == "tools/list":
            tools_list = [
                {
                    "name": name,
                    "description": meta["description"],
                    "inputSchema": {
                        "type": "object",
                        "properties": {k: {"type": "string"} for k in meta["parameters"]}
                    }
                }
                for name, meta in AVAILABLE_TOOLS.items()
            ]
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}})

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if tool_name not in AVAILABLE_TOOLS:
                return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}})

            handler = AVAILABLE_TOOLS[tool_name]["handler"]
            result = handler(**tool_args)
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, default=str)}]}})

        elif method == "ping":
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "result": "pong"})

        else:
            return json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not recognized"}})

    except Exception as e:
        safe_id = locals().get("req_id", 1)
        return json.dumps({"jsonrpc": "2.0", "id": safe_id, "error": {"code": -32000, "message": str(e)}})

def main():
    logger.info("AlphaSentinel MCP Server running on stdio...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = handle_rpc_request(line)
        sys.stdout.write(response + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
