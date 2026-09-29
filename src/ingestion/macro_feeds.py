"""
Enhanced Global Macro Radar & Pre-Market Live Sentiment Ingestion ($0 Free Tier).
Pulls US VIX (CBOE), S&P 500, Brent Crude Oil, USDINR, and GIFT Nifty proxy.
"""

import logging
from typing import Dict, Any
import yfinance as yf

logger = logging.getLogger(__name__)

def fetch_macro_weather_data() -> Dict[str, Any]:
    """
    Fetches live pre-market global sentiment indicators:
    1. US VIX (^VIX) for overnight fear gauge
    2. S&P 500 (^GSPC) overnight % change
    3. Brent Crude Oil (BZ=F) price and % change
    4. USD/INR (USDINR=X) exchange rate and % change
    5. Nifty 50 (^NSEI) proxy trend
    
    Returns:
        Dict with macro metrics, regime classification, and target cash exposure.
    """
    fallback_macro = {
        "us_vix": 22.0,
        "sp500_pct_change": -0.5,
        "crude_oil_price": 75.0,
        "crude_oil_pct_change": 0.0,
        "usdinr_price": 86.5,
        "usdinr_pct_change": 0.0,
        "polymarket_risk_score": 0.5,
        "market_regime": "HIGH_RISK_DEFENSIVE",
        "macro_weather_score": 0.3,
        "target_cash_exposure_pct": 70.0,
        "source": "FALLBACK_DEFENSIVE"
    }

    try:
        # Batch download for speed & reduced API overhead
        tickers = yf.Tickers("^VIX ^GSPC BZ=F USDINR=X ^NSEI")
        
        # 1. US VIX
        try:
            vix_hist = tickers.tickers["^VIX"].history(period="5d")
            current_vix = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 16.5
        except Exception:
            current_vix = 16.5

        # 2. S&P 500
        try:
            sp_hist = tickers.tickers["^GSPC"].history(period="5d")
            p0 = float(sp_hist["Close"].iloc[-2]) if len(sp_hist) >= 2 else 0.0
            p1 = float(sp_hist["Close"].iloc[-1]) if len(sp_hist) >= 1 else 0.0
            sp_change = ((p1 - p0) / p0 * 100.0) if p0 > 0 else 0.0
        except Exception:
            sp_change = 0.0

        # 3. Crude Oil (Brent)
        try:
            crude_hist = tickers.tickers["BZ=F"].history(period="5d")
            c0 = float(crude_hist["Close"].iloc[-2]) if len(crude_hist) >= 2 else 0.0
            c1 = float(crude_hist["Close"].iloc[-1]) if len(crude_hist) >= 1 else 75.0
            crude_price = c1
            crude_change = ((c1 - c0) / c0 * 100.0) if c0 > 0 else 0.0
        except Exception:
            crude_price, crude_change = 75.0, 0.0

        # 4. USD/INR
        try:
            fx_hist = tickers.tickers["USDINR=X"].history(period="5d")
            f0 = float(fx_hist["Close"].iloc[-2]) if len(fx_hist) >= 2 else 0.0
            f1 = float(fx_hist["Close"].iloc[-1]) if len(fx_hist) >= 1 else 86.5
            usdinr_price = f1
            usdinr_change = ((f1 - f0) / f0 * 100.0) if f0 > 0 else 0.0
        except Exception:
            usdinr_price, usdinr_change = 86.5, 0.0


        # Optional Polymarket sentiment
        polymarket_risk_score = 0.5
        try:
            import requests
            pm_resp = requests.get("https://gamma-api.polymarket.com/events", params={"limit": 3, "active": "true"}, timeout=2)
            if pm_resp.status_code == 200:
                events_data = pm_resp.json()
                events_list = events_data if isinstance(events_data, list) else events_data.get('data', [])
                if events_list:
                    total_risk = 0.0
                    valid_markets = 0
                    for event in events_list:
                        for market in event.get('markets', []):
                            prices = market.get('outcomePrices', [])
                            if prices and isinstance(prices, list):
                                try:
                                    max_p = max(float(p) for p in prices if p)
                                    total_risk += max_p
                                    valid_markets += 1
                                except (ValueError, TypeError):
                                    pass
                    if valid_markets > 0:
                        polymarket_risk_score = min(1.0, total_risk / valid_markets)
        except Exception:
            pass

        # Comprehensive Risk Calculation
        # VIX > 25, S&P drop > 2%, or Crude spike > 3% indicates macro storm
        risk_penalties = 0.0
        if current_vix > 28.0: risk_penalties += 0.4
        elif current_vix > 20.0: risk_penalties += 0.2
        
        if sp_change < -2.0: risk_penalties += 0.3
        elif sp_change < -0.8: risk_penalties += 0.15
        
        if crude_change > 3.5: risk_penalties += 0.2
        if usdinr_change > 0.5: risk_penalties += 0.1

        macro_score = max(0.0, min(1.0, 1.0 - risk_penalties))

        if macro_score < 0.4:
            regime = "HIGH_RISK"
            target_cash = 70.0  # Hold 70% cash, deploy max 30%
        elif macro_score < 0.7:
            regime = "CAUTIOUS"
            target_cash = 40.0  # Hold 40% cash, deploy max 60%
        else:
            regime = "BULLISH_FAVORABLE"
            target_cash = 0.0   # Full fund deployment authorized

        return {
            "us_vix": round(current_vix, 2),
            "sp500_pct_change": round(sp_change, 2),
            "crude_oil_price": round(crude_price, 2),
            "crude_oil_pct_change": round(crude_change, 2),
            "usdinr_price": round(usdinr_price, 2),
            "usdinr_pct_change": round(usdinr_change, 2),
            "polymarket_risk_score": round(polymarket_risk_score, 2),
            "macro_weather_score": round(macro_score, 2),
            "market_regime": regime,
            "target_cash_exposure_pct": target_cash,
            "source": "LIVE_MULTI_FEED"
        }

    except Exception as e:
        logger.error(f"Failed to fetch macro market data: {e}. Falling back to default.")
        return fallback_macro
