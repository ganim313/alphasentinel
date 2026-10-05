import datetime
import json
import logging
import requests
from src.db.session import get_read_connection
from src.db.queue_writer import db_write

logger = logging.getLogger(__name__)

# Official verified NSE Trading Holidays for 2026
HARDCODED_NSE_HOLIDAYS = [
    datetime.date(2026, 1, 26),   # Republic Day
    datetime.date(2026, 3, 3),    # Holi
    datetime.date(2026, 3, 20),   # Id-Ul-Fitr (Ramzan Id)
    datetime.date(2026, 3, 27),   # Ram Navami
    datetime.date(2026, 3, 31),   # Mahavir Jayanti
    datetime.date(2026, 4, 3),    # Good Friday
    datetime.date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    datetime.date(2026, 5, 1),    # Maharashtra Day
    datetime.date(2026, 5, 27),   # Bakrid / Eid-ul-Adha
    datetime.date(2026, 6, 26),   # Muharram
    datetime.date(2026, 8, 15),   # Independence Day
    datetime.date(2026, 9, 14),   # Ganesh Chaturthi
    datetime.date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    datetime.date(2026, 10, 20),  # Dussehra
    datetime.date(2026, 11, 8),   # Diwali Laxmi Pujan (Muhurat Trading)
    datetime.date(2026, 11, 10),  # Diwali Balipratipada
    datetime.date(2026, 11, 24),  # Guru Nanak Jayanti
    datetime.date(2026, 12, 25),  # Christmas
    # Official & Provisional verified NSE Trading Holidays for 2027
    datetime.date(2027, 1, 26),   # Republic Day
    datetime.date(2027, 2, 26),   # Mahashivratri
    datetime.date(2027, 3, 23),   # Holi
    datetime.date(2027, 3, 26),   # Good Friday
    datetime.date(2027, 4, 14),   # Dr. Ambedkar Jayanti
    datetime.date(2027, 4, 21),   # Ram Navami
    datetime.date(2027, 5, 1),    # Maharashtra Day
    datetime.date(2027, 5, 19),   # Bakrid / Eid-ul-Adha
    datetime.date(2027, 8, 15),   # Independence Day
    datetime.date(2027, 9, 4),    # Ganesh Chaturthi
    datetime.date(2027, 10, 2),   # Mahatma Gandhi Jayanti
    datetime.date(2027, 10, 11),  # Dussehra
    datetime.date(2027, 11, 1),   # Diwali Laxmi Pujan (Muhurat Trading)
    datetime.date(2027, 11, 14),  # Guru Nanak Jayanti
    datetime.date(2027, 12, 25),  # Christmas
]

# Startup validation: Warn if operating in an unmapped calendar year
from zoneinfo import ZoneInfo
_current_year = datetime.datetime.now(ZoneInfo("Asia/Kolkata")).date().year
_covered_years = {d.year for d in HARDCODED_NSE_HOLIDAYS}
if _current_year not in _covered_years:
    logger.warning(
        f"NSE_HOLIDAYS WARNING: No hardcoded holiday data for year {_current_year}. "
        f"Update src/utils/holidays.py to ensure scheduler pauses on market holidays."
    )

def is_nse_holiday(check_date: datetime.date) -> bool:
    """
    Checks if a given date is an NSE trading holiday or weekend.
    Returns True on Saturdays, Sundays, and official exchange holidays.
    """
    # 1. Weekends (5 = Saturday, 6 = Sunday)
    if check_date.weekday() >= 5:
        return True

    # 2. Hardcoded verified holiday list
    if check_date in HARDCODED_NSE_HOLIDAYS:
        return True

    cache_key = f"nse_holidays_{check_date.year}"

    # 3. Cached holiday check from DuckDB
    try:
        with get_read_connection() as conn:
            row = conn.execute(
                "SELECT holidays_json FROM nse_holiday_cache WHERE cache_key = ?",
                (cache_key,)
            ).fetchone()
            if row and row[0]:
                holidays = set(json.loads(row[0]))
                if holidays:
                    return check_date.isoformat() in holidays
    except Exception as e:
        logger.warning(f"NSE holiday cache read failed: {e}")

    # 4. Live fetch from NSE with browser session simulation
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        # Warm session cookies
        session.get("https://www.nseindia.com", timeout=5)
        resp = session.get(
            "https://www.nseindia.com/api/holiday-master?type=trading",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            holidays = set()
            for month_holidays in data.values():
                if isinstance(month_holidays, list):
                    for h in month_holidays:
                        try:
                            dt = datetime.datetime.strptime(h["tradingDate"], "%d-%b-%Y").date()
                            if dt.year == check_date.year:
                                holidays.add(dt.isoformat())
                        except Exception:
                            continue
            
            # Guard against cache poisoning: only write if at least 10 holidays were returned
            if len(holidays) >= 10:
                try:
                    db_write(
                        "INSERT OR REPLACE INTO nse_holiday_cache (cache_key, holidays_json) VALUES (?, ?)",
                        (cache_key, json.dumps(list(holidays))),
                        sync=True
                    )
                except Exception as db_err:
                    logger.warning(f"Failed to write NSE holiday cache: {db_err}")
                    
                return check_date.isoformat() in holidays
    except Exception as e:
        logger.warning(f"NSE holiday API fetch failed: {e}. Falling back to default.")

    return False

