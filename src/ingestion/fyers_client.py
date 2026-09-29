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
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FyersClient, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
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
        """Load access token from local cache/db if valid."""
        return os.environ.get("FYERS_ACCESS_TOKEN", "DUMMY_TOKEN_FOR_NOW")

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

fyers_client = FyersClient()
