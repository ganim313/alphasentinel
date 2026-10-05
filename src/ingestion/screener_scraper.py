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
                if cached.get("sector_name"):
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
        "trade_receivables": 0.0,
        "accounts_receivable": 0.0,
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

        # Extract Industry/Sector for Shariah Compliance & Sector Concentration Caps
        sector_name = ""
        sector_candidates = []
        for sel in (
            'a[href^="/explore/?sector="]',
            'a[href*="/explore/"]',
            '#peers a[href^="/market/"]',
            'a[href^="/market/"]',
            '#peers a',
        ):
            for el in soup.select(sel):
                href = (el.get("href") or "").strip()
                if any(href.startswith(p) for p in ("/company/", "/screen/", "/user/", "#", "javascript:")):
                    continue
                txt = el.get_text(strip=True)
                if txt and txt.lower() not in ("customize", "edit", "peers", "more") and txt not in sector_candidates:
                    sector_candidates.append(txt)
            if sector_candidates:
                break

        if sector_candidates:
            # Prefer explicit 'Sector' title link if present, else first breadcrumb
            sector_title_el = soup.select_one('#peers a[title="Sector"], a[title="Sector"]')
            if sector_title_el and sector_title_el.get_text(strip=True):
                sector_name = sector_title_el.get_text(strip=True)
            else:
                sector_name = sector_candidates[0]

            # If a sub-industry breadcrumb contains a Shariah-prohibited keyword, preserve it in sector_name
            try:
                from src.screening.shariah_filter import PROHIBITED_SECTORS
                for cand_txt in sector_candidates:
                    cand_low = cand_txt.lower()
                    if any(p in cand_low for p in PROHIBITED_SECTORS) and cand_txt not in sector_name:
                        sector_name = f"{sector_name} - {cand_txt}" if sector_name else cand_txt
                        break
            except Exception:
                pass

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
        if inventories <= 0.0:
            inventories = get_row_last_val('balance-sheet', 'inventory')
        intangible_assets = get_row_last_val('balance-sheet', 'intangible assets')
        other_liabilities = get_row_last_val('balance-sheet', 'other liabilities')
        trade_receivables = get_row_last_val('balance-sheet', 'trade receivables')
        if trade_receivables <= 0.0:
            trade_receivables = get_row_last_val('balance-sheet', 'accounts receivable')
        if trade_receivables <= 0.0:
            trade_receivables = get_row_last_val('balance-sheet', 'receivables')

        # Screener.in nests Inventories and Trade receivables inside the 'Other Assets' schedule JSON
        if inventories <= 0.0 or trade_receivables <= 0.0:
            company_info_el = soup.find("div", id="company-info")
            company_id = company_info_el.get("data-company-id") if company_info_el else None
            if company_id:
                try:
                    is_cons = company_info_el.get("data-consolidated") == "true"
                    sched_url = (
                        f"https://www.screener.in/api/company/{company_id}/schedules/"
                        f"?parent=Other+Assets&section=balance-sheet"
                        + ("&consolidated=" if is_cons else "")
                    )
                    sched_resp = requests.get(
                        sched_url, headers=headers, timeout=settings.REQUEST_TIMEOUT_SECONDS
                    )
                    if getattr(sched_resp, "status_code", None) == 200:
                        sched_data = sched_resp.json()
                        if isinstance(sched_data, dict):
                            def _last_sched_num(row_dict: Any) -> float:
                                if not isinstance(row_dict, dict):
                                    return 0.0
                                for k, v in reversed(list(row_dict.items())):
                                    if k == "isExpandable":
                                        continue
                                    try:
                                        return float(str(v).replace(",", "").strip())
                                    except (ValueError, TypeError):
                                        continue
                                return 0.0

                            for k_name, row_dict in sched_data.items():
                                k_low = str(k_name).lower()
                                if inventories <= 0.0 and ("inventor" in k_low):
                                    inventories = _last_sched_num(row_dict)
                                elif trade_receivables <= 0.0 and ("receivable" in k_low or "debtor" in k_low):
                                    trade_receivables = _last_sched_num(row_dict)
                except Exception as sched_err:
                    logger.debug(f"Could not fetch Other Assets schedule for {symbol}: {sched_err}")

        # Fallback to Ratios section Debtor Days if trade_receivables still 0.0
        if trade_receivables <= 0.0 and sales > 0.0:
            debtor_days = get_row_last_val('ratios', 'debtor days')
            if debtor_days > 0.0:
                trade_receivables = round((debtor_days / 365.0) * sales, 2)

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

        # Fetch News Headlines via yfinance (and fallback sector metadata if missing)
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
            if not sector_name:
                info = getattr(ticker, "info", None)
                if isinstance(info, dict):
                    yf_sec = info.get("sector") or info.get("industry") or ""
                    if isinstance(yf_sec, str) and yf_sec.strip():
                        sector_name = yf_sec.strip()
        except Exception as e:
            logger.warning(f"Failed to fetch yfinance news for {symbol}: {e}")

        # Calculate pledge trend using history from prior dates (before inserting today's row)
        pledge_trend_3m = 0.0
        try:
            from src.db.session import get_read_connection
            with get_read_connection() as conn:
                row = conn.execute(
                    """
                    SELECT pledge_pct FROM promoter_pledge_history
                    WHERE symbol = ? AND quarter_end_date <= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY quarter_end_date DESC LIMIT 1
                    """,
                    (symbol,)
                ).fetchone()
                if not row:
                    row = conn.execute(
                        """
                        SELECT pledge_pct FROM promoter_pledge_history
                        WHERE symbol = ? AND quarter_end_date < CURRENT_DATE
                        ORDER BY quarter_end_date ASC LIMIT 1
                        """,
                        (symbol,)
                    ).fetchone()
                if row and row[0] is not None:
                    pledge_3m_ago = float(row[0])
                    pledge_trend_3m = pledged - pledge_3m_ago
        except Exception as e:
            logger.warning(f"Failed to fetch pledge history for {symbol}: {e}")

        # Persist scraped pledge percentage into promoter_pledge_history ONLY if valid company ratios exist (skip ETFs)
        if len(ratios) > 0:
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
            "trade_receivables": trade_receivables,
            "accounts_receivable": trade_receivables,
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
                    if cached.get("sector_name"):
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
