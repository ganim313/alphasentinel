"""
09:09 AM Pre-Market Macro Radar Runner.
Fetches global indices, FII/DII data, and crude oil prices.
Generates an Executive Morning Brief.
"""

import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
from src.ingestion.macro_feeds import fetch_macro_weather_data
from src.notification.telegram_bot import is_system_halted
from src.db.queue_writer import db_write

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_premarket")


def run_premarket_routine():
    if is_system_halted():
        logger.warning("System is currently HALTED by kill switch. Aborting pre-market routine.")
        return

    logger.info("Executing 09:09 AM Pre-Market Macro Analysis...")
    try:
        macro_data = fetch_macro_weather_data()
    except Exception as e:
        logger.error(f"Failed to fetch macro data: {e}")
        from src.notification.telegram_bot import set_system_halt_state, send_telegram_safe_halt_alarm
        set_system_halt_state(True, f"Macro Data Provider Failure: {e}")
        send_telegram_safe_halt_alarm(f"Macro Data Provider Failure: {e}")
        return
    
    logger.info(
        f"Pre-Market Macro Weather: Regime={macro_data['market_regime']} | "
        f"US VIX={macro_data['us_vix']} | S&P Change={macro_data['sp500_pct_change']:.2f}% | "
        f"Target Cash Exposure={macro_data['target_cash_exposure_pct']}%"
    )

    db_write("""
        INSERT OR REPLACE INTO macro_weather (
            scan_date, us_vix, sp500_pct_change, crude_oil_price, crude_oil_pct_change,
            usdinr_price, usdinr_pct_change, polymarket_risk_score, market_regime,
            macro_weather_score, target_cash_exposure_pct, source
        ) VALUES (CURRENT_DATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        macro_data.get('us_vix'), macro_data.get('sp500_pct_change'),
        macro_data.get('crude_oil_price'), macro_data.get('crude_oil_pct_change'),
        macro_data.get('usdinr_price'), macro_data.get('usdinr_pct_change'),
        macro_data.get('polymarket_risk_score'), macro_data.get('market_regime'),
        macro_data.get('macro_weather_score'), macro_data.get('target_cash_exposure_pct'),
        macro_data.get('source', 'PREMARKET_LIVE')
    ), sync=True)
    
    logger.info("Saved premarket macro state to database.")
    
    # 2. Compile Top Movers
    top_movers = []
    watchlist = []
    try:
        from src.db.session import get_read_connection
        with get_read_connection() as conn:
            # Get latest trade date
            max_date_row = conn.execute("SELECT MAX(trade_date) FROM bhavcopy_daily").fetchone()
            if max_date_row and max_date_row[0]:
                max_date = max_date_row[0]
                top_movers = conn.execute(f"""
                    SELECT symbol, ((close_price - prev_close)/prev_close * 100) as pct_change
                    FROM bhavcopy_daily
                    WHERE trade_date = '{max_date}' AND prev_close > 0
                    ORDER BY pct_change DESC
                    LIMIT 5;
                """).fetchall()
            
            # Get latest approved watchlist candidates
            watchlist = conn.execute("""
                SELECT symbol, pattern_type, trigger_price
                FROM screener_candidates
                WHERE status = 'APPROVED' 
                  AND scan_date >= (CURRENT_DATE - INTERVAL '5 days')
                ORDER BY scan_date DESC
                LIMIT 5;
            """).fetchall()
    except Exception as e:
        logger.error(f"Failed to fetch brief data from DB: {e}")

    # 3. Send Telegram Brief
    from src.notification.telegram_bot import send_telegram_morning_brief
    send_telegram_morning_brief(macro_data, top_movers, watchlist)
    logger.info("Morning Brief Sent Successfully.")


# Alias for compatibility with tests and pipelines
run_premarket = run_premarket_routine


if __name__ == "__main__":
    try:
        run_premarket_routine()
    except Exception as e:
        import traceback
        logger.error(f"Cron execution failed: {e}")
        from src.notification.telegram_bot import send_telegram_error_alert
        send_telegram_error_alert("run_premarket", str(e) + "\n" + traceback.format_exc())
