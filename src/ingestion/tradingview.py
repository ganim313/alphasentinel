"""
TradingView Technical Rating Ingestion Module ($0 Free Tier).
Fetches 26-indicator consensus recommendations and indicators for Indian equities.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_tradingview_technical_ratings(
    symbol: str, 
    exchange: str = "NSE", 
    interval: str = "1d"
) -> Dict[str, Any]:
    """
    Fetches aggregate technical indicator ratings from TradingView's scanner API.
    
    Returns:
        Dict containing:
            - recommendation: 'STRONG_BUY' | 'BUY' | 'NEUTRAL' | 'SELL' | 'STRONG_SELL'
            - summary: {'BUY': int, 'SELL': int, 'NEUTRAL': int}
            - oscillators: {'RECOMMENDATION': str, 'BUY': int, 'SELL': int, 'NEUTRAL': int}
            - moving_averages: {'RECOMMENDATION': str, 'BUY': int, 'SELL': int, 'NEUTRAL': int}
            - key_indicators: {'rsi': float, 'macd': float, 'ema20': float, 'sma50': float, 'sma200': float}
            - is_valid: bool
    """
    clean_symbol = (
        symbol.replace("NSE:", "")
        .replace("BSE:", "")
        .replace(".NS", "")
        .replace(".BO", "")
        .strip()
        .upper()
    )
    
    fallback_response = {
        "symbol": clean_symbol,
        "recommendation": "NEUTRAL",
        "summary": {"BUY": 0, "SELL": 0, "NEUTRAL": 0},
        "oscillators": {"RECOMMENDATION": "NEUTRAL", "BUY": 0, "SELL": 0, "NEUTRAL": 0},
        "moving_averages": {"RECOMMENDATION": "NEUTRAL", "BUY": 0, "SELL": 0, "NEUTRAL": 0},
        "key_indicators": {},
        "is_valid": False,
        "error": None
    }
    
    try:
        from tradingview_ta import TA_Handler, Interval

        
        interval_map = {
            "1m": Interval.INTERVAL_1_MINUTE,
            "5m": Interval.INTERVAL_5_MINUTES,
            "15m": Interval.INTERVAL_15_MINUTES,
            "1h": Interval.INTERVAL_1_HOUR,
            "4h": Interval.INTERVAL_4_HOURS,
            "1d": Interval.INTERVAL_1_DAY,
            "1w": Interval.INTERVAL_1_WEEK,
            "1M": Interval.INTERVAL_1_MONTH,
        }
        
        tv_interval = interval_map.get(interval, Interval.INTERVAL_1_DAY)
        
        handler = TA_Handler(
            symbol=clean_symbol,
            screener="india",
            exchange=exchange,
            interval=tv_interval,
            timeout=10
        )
        
        analysis = handler.get_analysis()
        if not analysis:
            logger.warning(f"[TradingView] No analysis returned for {clean_symbol}")
            return fallback_response
            
        summary = analysis.summary or {}
        rec = summary.get("RECOMMENDATION", "NEUTRAL")
        
        key_indicators = {}
        if analysis.indicators:
            for ind_name in ["RSI", "MACD.macd", "EMA20", "SMA50", "SMA200", "Stoch.K", "ADX", "volume"]:
                val = analysis.indicators.get(ind_name)
                if val is not None:
                    key_indicators[ind_name.lower().replace(".", "_")] = val
                    
        return {
            "symbol": clean_symbol,
            "recommendation": rec,
            "summary": summary,
            "oscillators": analysis.oscillators or {},
            "moving_averages": analysis.moving_averages or {},
            "key_indicators": key_indicators,
            "is_valid": True,
            "error": None
        }
        
    except Exception as e:
        logger.warning(f"[TradingView] Soft fallback for {clean_symbol}: {e}")
        fallback_response["error"] = str(e)
        return fallback_response
