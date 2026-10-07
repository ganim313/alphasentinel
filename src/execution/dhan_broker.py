"""
================================================================================
DEPRECATED: src/execution/dhan_broker.py
================================================================================
DEPRECATION NOTICE:
This module is DEPRECATED. FYERS API v3 CNC delivery (`NSE:EQ`) with server-side
GTT OCO order placement is the canonical broker execution adapter for AlphaSentinel.

DhanHQ v2 REST broker adapter is retained strictly for historical reference / simulated fallback
and MUST NOT be used for live trade routing in production.

CANONICAL BROKER:
- FYERS API v3 via `src/ingestion/fyers_client.py` and `scripts/fyers_auth.py`.
================================================================================
"""

import warnings
warnings.warn(
    "src/execution/dhan_broker.py is DEPRECATED: FYERS CNC is canonical.",
    DeprecationWarning,
    stacklevel=2
)

import json
import logging
import uuid
from typing import Any, Dict, List, Optional
import requests

from src.config.settings import settings
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)

DHAN_API_BASE_URL = "https://api.dhan.co/v2"


class DhanBroker:
    """
    DEPRECATED DhanHQ v2 REST broker adapter.
    Retained for fallback / simulation. FYERS API v3 is canonical.
    """

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "access-token": str(settings.DHAN_ACCESS_TOKEN or ""),
            "client-id": str(settings.DHAN_CLIENT_ID or ""),
        }

    @staticmethod
    def place_order(
        symbol: str,
        price: float,
        atr: float,
        quantity: int = 100,
        sector: Optional[str] = None,
        initial_stop: Optional[float] = None,
        target_1: Optional[float] = None,
        target_2: Optional[float] = None,
        candidate_id: Optional[str] = None,
    ) -> str:
        """
        Structures and routes a Dhan Order (Entry + Target + Stop Loss).
        Guarded by LIVE_TRADING_ENABLED safety gate.
        """
        logger.warning("DEPRECATED: DhanBroker is deprecated. FYERS CNC is canonical broker adapter.")
        from src.execution.order_manager import PaperBroker

        if not getattr(settings, "LIVE_TRADING_ENABLED", False):
            logger.warning(
                "\n" + "=" * 65 + "\n"
                "  ⚠️ DHAN BROKER SAFETY GUARD: LIVE TRADING DISABLED\n"
                "  settings.LIVE_TRADING_ENABLED is False.\n"
                "  All orders route strictly to PaperBroker simulation (DHAN_SIMULATED).\n"
                "  Set LIVE_TRADING_ENABLED=True in .env to enable real exchange execution.\n"
                + "=" * 65
            )
            return PaperBroker.place_order(
                symbol,
                price,
                atr,
                quantity,
                sector,
                execution_type="DHAN_SIMULATED",
                initial_stop=initial_stop,
                target_1=target_1,
                target_2=target_2,
                candidate_id=candidate_id,
            )

        logger.critical(f"LIVE TRADING ROUTING: Sending live order for {symbol} to Dhan API...")

        executed_price = price
        final_stop = initial_stop if initial_stop is not None else (executed_price - (atr * 1.8))
        risk_per_share = executed_price - final_stop if (executed_price - final_stop) > 0 else (atr * 1.8)
        final_t1 = target_1 if target_1 is not None else (executed_price + (risk_per_share * 2.0))
        final_t2 = target_2 if target_2 is not None else (executed_price + (risk_per_share * 3.5))

        security_id = None
        try:
            with get_read_connection() as conn:
                res = conn.execute(
                    "SELECT dhan_security_id FROM instrument_master WHERE symbol = ?",
                    (symbol,),
                ).fetchone()
                if res and res[0]:
                    security_id = str(res[0])
        except Exception as e:
            logger.warning(f"Could not resolve dhan_security_id for {symbol}: {e}")

        if not security_id:
            logger.error(
                f"Execution Failed: No dhan_security_id mapped for symbol {symbol}. "
                "Failing closed to prevent misrouting."
            )
            return ""

        payload = {
            "dhanClientId": settings.DHAN_CLIENT_ID,
            "correlationId": f"D_{symbol}_{uuid.uuid4().hex[:8]}",
            "transactionType": "BUY",
            "exchangeSegment": "NSE_EQ",
            "productType": "CNC",
            "orderType": "LIMIT",
            "validity": "DAY",
            "tradingSymbol": symbol,
            "securityId": security_id,
            "quantity": int(quantity),
            "disclosedQuantity": 0,
            "price": round(float(executed_price), 2),
            "triggerPrice": 0,
            "afterMarketOrder": False,
            "amoTime": "OPEN",
            "boProfitValue": round(float(final_t1 - executed_price), 2),
            "boStopLossValue": round(float(executed_price - final_stop), 2),
        }

        if settings.DHAN_ACCESS_TOKEN and settings.DHAN_CLIENT_ID:
            try:
                resp = requests.post(
                    f"{DHAN_API_BASE_URL}/orders",
                    headers=DhanBroker._headers(),
                    json=payload,
                    timeout=settings.REQUEST_TIMEOUT_SECONDS,
                )
                if resp.status_code in (200, 201, 202):
                    data = resp.json() if resp.text else {}
                    broker_order_id = str(data.get("orderId") or payload["correlationId"])
                    logger.info(f"Dhan Live Order Accepted: {broker_order_id} for {symbol}")
                    return PaperBroker.place_order(
                        symbol,
                        price,
                        atr,
                        quantity,
                        sector,
                        execution_type="DHAN_LIVE",
                        initial_stop=initial_stop,
                        target_1=target_1,
                        target_2=target_2,
                        candidate_id=candidate_id,
                    )
                else:
                    logger.error(f"Dhan API rejected order ({resp.status_code}): {resp.text}")
                    return ""
            except Exception as api_err:
                logger.error(f"Dhan API order request failed for {symbol}: {api_err}")
                return ""

        logger.warning(f"DHAN ORDER SIMULATION (NO CREDENTIALS CONFIGURED):\n{json.dumps(payload, indent=2)}")
        return PaperBroker.place_order(
            symbol,
            price,
            atr,
            quantity,
            sector,
            execution_type="DHAN_SIMULATED",
            initial_stop=initial_stop,
            target_1=target_1,
            target_2=target_2,
            candidate_id=candidate_id,
        )

    @staticmethod
    def get_order_status(order_id: str) -> Dict[str, Any]:
        """Fetches order status from DhanHQ REST API or returns simulated status in paper mode."""
        if not getattr(settings, "LIVE_TRADING_ENABLED", False) or not settings.DHAN_ACCESS_TOKEN:
            return {"orderId": order_id, "orderStatus": "SIMULATED_TRADED", "mode": "PAPER"}
        try:
            resp = requests.get(
                f"{DHAN_API_BASE_URL}/orders/{order_id}",
                headers=DhanBroker._headers(),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"orderId": order_id, "orderStatus": "ERROR", "httpStatus": resp.status_code}
        except Exception as e:
            logger.error(f"Failed to fetch Dhan order status for {order_id}: {e}")
            return {"orderId": order_id, "orderStatus": "ERROR", "error": str(e)}

    @staticmethod
    def cancel_order(order_id: str) -> bool:
        """Cancels a pending order via DhanHQ REST API."""
        if not getattr(settings, "LIVE_TRADING_ENABLED", False) or not settings.DHAN_ACCESS_TOKEN:
            return True
        try:
            resp = requests.delete(
                f"{DHAN_API_BASE_URL}/orders/{order_id}",
                headers=DhanBroker._headers(),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
            return resp.status_code in (200, 202)
        except Exception as e:
            logger.error(f"Failed to cancel Dhan order {order_id}: {e}")
            return False

    @staticmethod
    def get_positions() -> List[Dict[str, Any]]:
        """Fetches open positions from DhanHQ REST API or DuckDB when in paper mode."""
        if not getattr(settings, "LIVE_TRADING_ENABLED", False) or not settings.DHAN_ACCESS_TOKEN:
            try:
                with get_read_connection() as conn:
                    rows = conn.execute(
                        "SELECT id, symbol, quantity, entry_price, status FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')"
                    ).fetchall()
                return [
                    {"id": r[0], "tradingSymbol": r[1], "netQty": r[2], "buyAvg": r[3], "status": r[4]}
                    for r in rows
                ]
            except Exception:
                return []
        try:
            resp = requests.get(
                f"{DHAN_API_BASE_URL}/positions",
                headers=DhanBroker._headers(),
                timeout=settings.REQUEST_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else data.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch Dhan positions: {e}")
        return []
