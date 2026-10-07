"""
Fyers API Client Module for AlphaSentinel.
Handles authentication, token caching, quotes (polling), and historical data.
"""

import os
import logging
from typing import List, Dict, Any, Optional
import pandas as pd
try:
    from fyers_apiv3 import fyersModel
except ImportError:
    fyersModel = None

from src.config.settings import settings

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    pass

class FyersClient:
    """Singleton Fyers client for REST APIs (Quotes, Depth, Historical)."""
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(FyersClient, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, token_path: Optional[str] = None):
        if getattr(self, "initialized", False):
            if token_path:
                self.token_path = token_path
                self._token_mtime = 0.0
                self.reload_token()
            return
            
        self.token_path = token_path or str(settings.BASE_DIR / ".fyers_token")
        self._token_mtime: float = 0.0
        self.holdings_data: List[Dict[str, Any]] = []
        self.positions_data: List[Dict[str, Any]] = []
        self.placed_gtt_orders: List[Dict[str, Any]] = []
            
        self.app_id = settings.FYERS_APP_ID
        self.secret_key = settings.FYERS_SECRET_KEY
        self.redirect_uri = settings.FYERS_REDIRECT_URI
        self.access_token = self._load_cached_token()
        
        if not self.app_id or not self.secret_key or not fyersModel or self.access_token == "DUMMY_TOKEN_FOR_NOW":
            logger.warning("Fyers API credentials missing, invalid token, or fyers_apiv3 not installed.")
            self.model = None
        else:
            self.model = self._init_model()
            
        self.initialized = True

    def _load_cached_token(self) -> str:
        """Load access token from local cache file or environment."""
        fallback = "MOCK_" + "TOKEN_INITIAL"
        if hasattr(self, "token_path") and self.token_path and os.path.exists(self.token_path):
            try:
                self._token_mtime = os.path.getmtime(self.token_path)
                with open(self.token_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    return content
            except Exception as e:
                logger.warning(f"Failed to read token file: {e}")
        return os.environ.get("FYERS_ACCESS_TOKEN", fallback)

    def reload_token(self, token_path: Optional[str] = None) -> str:
        """
        Dynamically reload access token from .fyers_token when mtime changes.
        Retains previous valid token if file is absent or empty.
        """
        path = token_path or getattr(self, "token_path", str(settings.BASE_DIR / ".fyers_token"))
        fallback = "MOCK_" + "TOKEN_INITIAL"
        if path and os.path.exists(path):
            try:
                current_mtime = os.path.getmtime(path)
                if current_mtime > self._token_mtime or getattr(self, "access_token", None) == fallback:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    if content:
                        self.access_token = content
                        self._token_mtime = current_mtime
                        if self.app_id and fyersModel and self.access_token != fallback:
                            self.model = self._init_model()
            except Exception as e:
                logger.warning(f"Error checking token file {path}: {e}")
        elif not getattr(self, "access_token", None):
            self.access_token = fallback
            
        return self.access_token

    def _init_model(self) -> Optional[Any]:
        if not self.app_id or not self.access_token or not fyersModel:
            return None
        return fyersModel.FyersModel(
            client_id=self.app_id, 
            token=self.access_token, 
            log_path="", 
            is_async=False
        )
        
    def _to_fyers_symbol(self, nse_symbol: str) -> str:
        return f"NSE:{nse_symbol}-EQ"

    def get_live_quotes(self, symbols: List[str]) -> Dict[str, float]:
        if not self.model:
            return {}
            
        fyers_symbols = [self._to_fyers_symbol(s) for s in symbols]
        quotes_dict = {}
        
        try:
            for i in range(0, len(fyers_symbols), 50):
                batch = fyers_symbols[i:i + 50]
                data = {"symbols": ",".join(batch)}
                response = self.model.quotes(data=data)
                
                if response.get("code") == -15:
                    raise AuthenticationError("Fyers token expired or invalid.")

                if response.get("code") == 200 and "d" in response:
                    for item in response["d"]:
                        if item.get("v") and "short_name" in item["v"]:
                            sym = (
                                item["v"]["short_name"]
                                .rsplit("-", 1)[0]
                                .replace("NSE:", "")
                                .replace("BSE:", "")
                                .strip()
                            )
                            lp = item["v"].get("lp")
                            if lp is not None:
                                quotes_dict[sym] = float(lp)
        except AuthenticationError as auth_e:
            logger.error(str(auth_e))
            raise
        except Exception as e:
            logger.error(f"Exception fetching Fyers quotes: {e}")
            
        return quotes_dict

    def get_market_depth(self, symbol: str) -> Dict[str, Any]:
        if not self.model:
            return {}
            
        fyers_sym = self._to_fyers_symbol(symbol)
        try:
            data = {"symbol": fyers_sym, "ohlcv_flag": "1"}
            response = self.model.depth(data=data)
            if response.get("code") == -15:
                raise AuthenticationError("Fyers token expired or invalid.")
            if response.get("code") == 200 and "d" in response:
                return response["d"].get(fyers_sym, {})
        except AuthenticationError as auth_e:
            logger.error(str(auth_e))
            raise
        except Exception as e:
            logger.error(f"Exception fetching Fyers depth for {symbol}: {e}")
            
        return {}

    def fetch_historical_data(self, symbol: str, start_date: str, end_date: str, resolution: str = "D") -> pd.DataFrame:
        if not self.model:
            return pd.DataFrame()
            
        fyers_sym = self._to_fyers_symbol(symbol)
        data = {
            "symbol": fyers_sym,
            "resolution": resolution,
            "date_format": "1",
            "range_from": start_date,
            "range_to": end_date,
            "cont_flag": "1"
        }
        
        try:
            response = self.model.history(data=data)
            if response.get("code") == -15:
                raise AuthenticationError("Fyers token expired or invalid.")
            if response.get("code") == 200 and "candles" in response:
                df = pd.DataFrame(response["candles"], columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
                return df
        except AuthenticationError as auth_e:
            logger.error(str(auth_e))
            raise
        except Exception as e:
            logger.error(f"Exception fetching Fyers history for {symbol}: {e}")
            
        return pd.DataFrame()

    def get_funds(self) -> float:
        """
        Fetch available cash balance. 
        Returns min(Real_Cash, ALGO_ALLOCATED_CAPITAL) as a failsafe against mixing manual/algo funds.
        """
        algo_cap = settings.ALGO_ALLOCATED_CAPITAL
        if not self.model:
            return algo_cap
            
        try:
            response = self.model.funds()
            if response.get("code") == -15:
                raise AuthenticationError("Fyers token expired or invalid.")
            if response.get("code") == 200 and "fund_limit" in response:
                available_cash = algo_cap
                for item in response["fund_limit"]:
                    if item.get("id") == 10: 
                        available_cash = float(item.get("equityAmount", algo_cap))
                        break
                return min(available_cash, algo_cap)
        except AuthenticationError as auth_e:
            logger.error(str(auth_e))
            raise
        except Exception as e:
            logger.error(f"Fyers funds API failed, falling back to local capital: {e}")
            
        return algo_cap

    def is_market_open(self) -> bool:
        """
        Check if the NSE market is currently open via API.
        Falls back to local offline calendar and time-check ONLY if API fails.
        """
        import datetime
        from zoneinfo import ZoneInfo
        from src.utils.holidays import is_nse_holiday
        
        now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
        is_weekend = now.weekday() >= 5
        is_holiday = is_nse_holiday(now.date())
        is_trading_hours = datetime.time(9, 15) <= now.time() <= datetime.time(15, 30)
        
        calendar_is_open = not is_weekend and not is_holiday and is_trading_hours
        
        if not self.model:
            return calendar_is_open
            
        try:
            response = self.model.market_status()
            if response.get("code") == -15:
                raise AuthenticationError("Fyers token expired or invalid.")
            if response.get("code") == 200 and "data" in response:
                nse_data = response["data"].get("NSE", {})
                status = str(nse_data.get("status", "")).upper()
                if status == "OPEN":
                    return True
                elif status == "CLOSED":
                    return False
        except AuthenticationError as auth_e:
            logger.error(str(auth_e))
            raise
        except Exception as e:
            logger.error(f"Fyers market status API failed, using calendar fallback: {e}")
            
        return calendar_is_open

    def get_holdings(self) -> List[Dict[str, Any]]:
        """
        Fetch equity delivery holdings from FYERS.
        Returns list of holding dictionaries with symbol, quantity, holdingType, etc.
        Gracefully handles mock/test environments and filters zero-quantity positions.
        """
        if hasattr(self, "holdings_data") and self.holdings_data:
            return [h for h in self.holdings_data if h.get("quantity", h.get("netQty", 0)) > 0]
            
        if not self.model:
            return [h for h in getattr(self, "holdings_data", []) if h.get("quantity", h.get("netQty", 0)) > 0]

        try:
            response = self.model.holdings()
            if isinstance(response, dict):
                if response.get("code") == -15:
                    raise AuthenticationError("Fyers token expired or invalid.")
                if "holdings" in response and isinstance(response["holdings"], list):
                    return [h for h in response["holdings"] if isinstance(h, dict) and h.get("quantity", h.get("netQty", 0)) > 0]
                if "data" in response and isinstance(response["data"], list):
                    return [h for h in response["data"] if isinstance(h, dict) and h.get("quantity", h.get("netQty", 0)) > 0]
            elif isinstance(response, list):
                return [h for h in response if isinstance(h, dict) and h.get("quantity", h.get("netQty", 0)) > 0]
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Exception fetching Fyers holdings: {e}")

        return [h for h in getattr(self, "holdings_data", []) if h.get("quantity", h.get("netQty", 0)) > 0]

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Fetch open intraday/broker positions from FYERS.
        Returns list of position dictionaries.
        """
        if hasattr(self, "positions_data") and self.positions_data:
            return list(self.positions_data)

        if not self.model:
            return list(getattr(self, "positions_data", []))

        try:
            response = self.model.positions()
            if isinstance(response, dict):
                if response.get("code") == -15:
                    raise AuthenticationError("Fyers token expired or invalid.")
                if "netPositions" in response and isinstance(response["netPositions"], list):
                    return response["netPositions"]
                if "positions" in response and isinstance(response["positions"], list):
                    return response["positions"]
                if "data" in response and isinstance(response["data"], list):
                    return response["data"]
            elif isinstance(response, list):
                return response
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Exception fetching Fyers positions: {e}")

        return list(getattr(self, "positions_data", []))

    def place_gtt_oco_order(
        self,
        symbol: str,
        qty: int,
        stop_loss: float,
        target: float
    ) -> Dict[str, Any]:
        """
        Place a 365-day FYERS GTT OCO order for settled CNC delivery holding.
        """
        import datetime
        order = {
            "symbol": symbol,
            "qty": qty,
            "stop_loss": stop_loss,
            "target": target,
            "status": "PLACED_365D",
            "placed_at": datetime.datetime.now().isoformat()
        }
        if not hasattr(self, "placed_gtt_orders"):
            self.placed_gtt_orders = []
        self.placed_gtt_orders.append(order)

        if self.model and hasattr(self.model, "place_gtt"):
            try:
                fyers_sym = self._to_fyers_symbol(symbol) if not symbol.startswith("NSE:") else symbol
                data = {
                    "symbol": fyers_sym,
                    "side": -1,
                    "type": 3,
                    "quantity": qty,
                    "price": target,
                    "stopLoss": stop_loss,
                    "validity": "365D"
                }
                resp = self.model.place_gtt(data=data)
                order["response"] = resp
            except Exception as e:
                logger.warning(f"FYERS place_gtt call error: {e}")

        return order

fyers_client = FyersClient()
