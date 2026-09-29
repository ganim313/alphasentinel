"""
Stealth Screener.in Fundamental Scraper.
Extracts Valuation, Debt/Equity (Shariah), and Promoter data headlessly ($0 budget).
Implements strict NaN imputation for soft degradation resilience.
"""

import logging
import time
from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from src.config.settings import settings

logger = logging.getLogger(__name__)


def fetch_screener_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Scrapes Screener.in company page for key financial metrics.
    Returns normalized dictionary with imputed fallback values on failure.
    """
    url = f"https://www.screener.in/company/{symbol}/consolidated/"
    # -------------------------------------------------------------
    # CRITICAL FIX: Read from DB cache FIRST to avoid 429/IP Ban
    # -------------------------------------------------------------
    import json
    import random
    from src.db.session import get_read_connection
    from src.db.queue_writer import db_write
    
    try:
        with get_read_connection() as conn:
            # Check if cache is < 7 days old
            row = conn.execute("""
                SELECT fundamentals_json 
                FROM fundamentals_cache 
                WHERE symbol = ? AND updated_at >= CURRENT_DATE - INTERVAL 7 DAY
            """, (symbol,)).fetchone()
            if row:
                cached = json.loads(row[0])
                cached["source"] = "DB_CACHE_FIRST"
                return cached
    except Exception as e:
        logger.warning(f"Failed to read fundamentals_cache for {symbol}: {e}")

    # Jitter to avoid rapid-fire IP ban
    time.sleep(random.uniform(1.0, 3.5))

    # Rotating User Agents
    UAS = [
        settings.USER_AGENT,
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    ]
    
    headers = {
        "User-Agent": random.choice(UAS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    # Safe fallback defaults (Hard degradation for risk metrics)
    fallback_data = {
        "symbol": symbol,
        "news_headlines": [],
        "recent_news_count": 0,
        "pe_ratio": 20.0,
        "sector_pe": 25.0,
        "market_cap_crores": 500.0,
        "debt_to_equity": 0.2,
        "roce_pct": 15.0,
        "promoter_holding_pct": 55.0,
        "promoter_pledged_pct": 0.0,
        "pledge_trend_3m": 0.0,
        "sector_name": "",
        "sales": 0.0,
        "other_income": 0.0,
        "borrowings": 0.0,
        "total_assets": 0.0,
        "fixed_assets": 0.0,
        "cwip": 0.0,
        "inventories": 0.0,
        "intangible_assets": 0.0,
        "interest_income_ratio": 0.0,
        "debt_to_assets": 0.0,
        "illiquid_ratio": 0.0,
        "other_liabilities": 0.0,
        "net_liquid_assets_crores": 0.0,
        "is_shariah_compliant": False,
        "source": "FALLBACK_IMPUTED"
    }

    try:
        response = requests.get(url, headers=headers, timeout=settings.REQUEST_TIMEOUT_SECONDS)
        
        if response.status_code in [429, 403]:
            logger.error(f"Screener.in IP Ban/Throttle ({response.status_code}) for {symbol}. Fast failing without blocking.")
            return fallback_data

        # Fallback to standalone if consolidated page 404s
        if response.status_code == 404:
            url_standalone = f"https://www.screener.in/company/{symbol}/"
            time.sleep(random.uniform(0.5, 1.0))
            response = requests.get(url_standalone, headers=headers, timeout=settings.REQUEST_TIMEOUT_SECONDS)

        if response.status_code != 200:
            logger.warning(f"Screener.in returned status {response.status_code} for {symbol}. Using imputed fallbacks.")
            return fallback_data

        if "Just a moment..." in response.text or "challenge-platform" in response.text:
            logger.warning(f"Cloudflare challenge page detected on Screener.in for {symbol}. Aborting parse to protect cache.")
            return fallback_data

        soup = BeautifulSoup(response.text, "html.parser")
        
        # Parse top ratios block
        ratios: Dict[str, float] = {}
        for item in soup.select("ul#top-ratios li"):
            name_el = item.select_one("span.name")
            val_el = item.select_one("span.number")
            if name_el and val_el:
                key = name_el.get_text(strip=True).lower()
                raw_val = val_el.get_text(strip=True).replace(",", "")
                try:
                    ratios[key] = float(raw_val)
                except ValueError:
                    pass

        pe = ratios.get("stock p/e", fallback_data["pe_ratio"])
        market_cap = ratios.get("market cap", fallback_data["market_cap_crores"])
        roce = ratios.get("roce", fallback_data["roce_pct"])
        debt_to_equity = ratios.get("debt to equity", fallback_data["debt_to_equity"])
        pledged = ratios.get("pledged percentage", fallback_data["promoter_pledged_pct"])

        # Extract Industry/Sector for Shariah Compliance
        sector_name = ""
        sector_el = soup.select_one('a[href^="/explore/?sector="]')
        if sector_el:
            sector_name = sector_el.get_text(strip=True)

        # Helper to extract quantitative P&L / Balance Sheet data
        def get_row_last_val(section_id, row_name):
            section = soup.find('section', id=section_id)
            if not section: return 0.0
            for tr in section.find_all('tr'):
                tds = tr.find_all('td')
                if not tds: continue
                if row_name.lower() in tds[0].text.lower():
                    val = tds[-1].text.strip().replace(',', '')
                    try:
                        return float(val)
                    except ValueError:
                        return 0.0
            return 0.0

        # Extract strict quantitative Shariah metrics
        sales = get_row_last_val('profit-loss', 'sales')
        if sales <= 0.0:
            sales = get_row_last_val('profit-loss', 'revenue')

        other_income = get_row_last_val('profit-loss', 'other income')
        # CRITICAL BUG FIX: P&L "Interest" is Interest Expense (Finance Cost), NOT Interest Income. Removed fallback.

        borrowings = get_row_last_val('balance-sheet', 'borrowings')
        if borrowings <= 0.0:
            borrowings = get_row_last_val('balance-sheet', 'debt')

        total_assets = get_row_last_val('balance-sheet', 'total assets')
        fixed_assets = get_row_last_val('balance-sheet', 'fixed assets')
        cwip = get_row_last_val('balance-sheet', 'cwip')
        inventories = get_row_last_val('balance-sheet', 'inventories')
        intangible_assets = get_row_last_val('balance-sheet', 'intangible assets')
        other_liabilities = get_row_last_val('balance-sheet', 'other liabilities')

        # Calculate quantitative compliance:
        # NOTE: PRD specifies max(other_income, interest_income) / sales.
        # Screener.in's P&L row labeled "Interest" is Interest Expense (Finance Cost),
        # NOT Interest Income. Using it as income would UNDERSTATE impure income ratio.
        # other_income is retained as a conservative proxy (fail-safe direction for Shariah compliance).
        interest_income_ratio = (other_income / sales) if sales > 0 else 0.0
        debt_to_assets = (borrowings / total_assets) if total_assets > 0 else 0.0
        
        # Updated Illiquid Asset Formula matching Excel (Fixed + CWIP + Inventory + Intangible)
        total_illiquid = fixed_assets + cwip + inventories + intangible_assets
        illiquid_ratio = (total_illiquid / total_assets) if total_assets > 0 else 0.0

        # Net Liquid Assets (Mufti Taqi Usmani 5th Rule: Net Liquid Assets <= Market Cap)
        # Net Liquid Assets = Total Assets - Illiquid Assets - Total Liabilities
        total_liabilities = borrowings + other_liabilities
        net_liquid_assets = (total_assets - total_illiquid) - total_liabilities

        # Fetch News Headlines via yfinance
        news_headlines = []
        recent_news_count = 0
        try:
            yf_symbol = f"{symbol}.NS"
            ticker = yf.Ticker(yf_symbol)
            news = ticker.news
            if news:
                news_headlines = [n.get('content', {}).get('title', '') or n.get('title', '') for n in news]
                news_headlines = [title for title in news_headlines if title]
                recent_news_count = len(news_headlines)
        except Exception as e:
            logger.warning(f"Failed to fetch yfinance news for {symbol}: {e}")

        # Calculate pledge trend using history
        pledge_trend_3m = 0.0
        try:
            from src.db.session import get_read_connection
            with get_read_connection() as conn:
                row = conn.execute(
                    "SELECT pledge_pct FROM promoter_pledge_history WHERE symbol = ? ORDER BY quarter_end_date DESC LIMIT 1", 
                    (symbol,)
                ).fetchone()
                if row:
                    pledge_3m_ago = float(row[0])
                    pledge_trend_3m = pledged - pledge_3m_ago
        except Exception as e:
            logger.warning(f"Failed to fetch pledge history for {symbol}: {e}")

        # Persist scraped pledge percentage into promoter_pledge_history
        try:
            from src.db.queue_writer import db_write
            db_write("""
                INSERT OR REPLACE INTO promoter_pledge_history (
                    symbol, quarter_end_date, pledge_pct, created_at
                ) VALUES (?, CURRENT_DATE, ?, CURRENT_TIMESTAMP);
            """, (symbol, float(pledged)))
        except Exception as pledge_err:
            logger.debug(f"Failed to record promoter_pledge_history for {symbol}: {pledge_err}")

        result = {
            "symbol": symbol,
            "news_headlines": news_headlines,
            "recent_news_count": recent_news_count,
            "pe_ratio": pe,
            "sector_pe": fallback_data["sector_pe"],
            "market_cap_crores": market_cap,
            "debt_to_equity": debt_to_equity,
            "roce_pct": roce,
            "promoter_holding_pct": ratios.get("promoter holding", fallback_data["promoter_holding_pct"]),
            "promoter_pledged_pct": pledged,
            "pledge_trend_3m": pledge_trend_3m,
            "sector_name": sector_name,
            "sales": sales,
            "other_income": other_income,
            "borrowings": borrowings,
            "total_assets": total_assets,
            "fixed_assets": fixed_assets,
            "cwip": cwip,
            "inventories": inventories,
            "intangible_assets": intangible_assets,
            "interest_income_ratio": interest_income_ratio,
            "debt_to_assets": debt_to_assets,
            "illiquid_ratio": illiquid_ratio,
            "other_liabilities": other_liabilities,
            "net_liquid_assets_crores": net_liquid_assets,
            "source": "SCREENER_LIVE"
        }
        
        # Save to DB cache only if authentic data was extracted
        if market_cap > 0 and len(ratios) > 0:
            try:
                from src.db.queue_writer import db_write
                import json
                
                db_write(
                    "INSERT OR REPLACE INTO fundamentals_cache (symbol, fundamentals_json) VALUES (?, ?)", 
                    (symbol, json.dumps(result))
                )
            except Exception as cache_err:
                logger.error(f"Failed to cache fundamentals for {symbol}: {cache_err}")
            
        return result

    except Exception as e:
        logger.error(f"Failed to scrape Screener.in for {symbol}: {e}. Attempting DB cache fallback.")
        
        try:
            from src.db.session import get_read_connection
            import json
            with get_read_connection() as conn:
                row = conn.execute("SELECT fundamentals_json FROM fundamentals_cache WHERE symbol = ?", (symbol,)).fetchone()
                if row:
                    cached = json.loads(row[0])
                    cached["source"] = "DB_CACHE_FALLBACK"
                    return cached
        except Exception as db_err:
            logger.error(f"DB Cache fallback failed: {db_err}")
            
        # If cache fails or doesn't exist, send alert and use hardcoded
        try:
            from src.notification.telegram_bot import send_telegram_alert
            send_telegram_alert(f"⚠️ SCREENER.IN SCRAPER FAILURE for {symbol}. No DB cache. Using hard defaults.")
        except Exception:
            pass
            
        return fallback_data


# Alias for backward compatibility
scrape_screener_fundamentals = fetch_screener_fundamentals
