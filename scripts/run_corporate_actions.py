import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import yfinance as yf
from src.db.session import get_read_connection
from src.ingestion.corporate_actions import record_corporate_action, apply_pending_corporate_actions

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_corporate_actions")

def fetch_and_record_splits():
    """
    Automated fetcher for Corporate Actions (Splits) using yfinance.
    Prioritizes active portfolio holdings and recent watchlist candidates to prevent IP rate bans.
    """
    logger.info("Scanning for recent stock splits...")
    
    with get_read_connection() as conn:
        # Prioritize symbols in open positions or recent screener candidates
        portfolio_symbols = [row[0] for row in conn.execute(
            "SELECT DISTINCT symbol FROM positions WHERE status IN ('OPEN', 'TARGET_1_TRIMMED')"
        ).fetchall()]
        candidate_symbols = [row[0] for row in conn.execute(
            "SELECT DISTINCT symbol FROM screener_candidates WHERE scan_date >= CURRENT_DATE - INTERVAL 7 DAY"
        ).fetchall()]
        
        symbols = list(dict.fromkeys(portfolio_symbols + candidate_symbols))
        
        # If no active positions or candidates, sample top liquid symbols
        if not symbols:
            symbols = [row[0] for row in conn.execute(
                "SELECT symbol FROM bhavcopy_daily GROUP BY symbol ORDER BY MAX(total_traded_val) DESC LIMIT 50"
            ).fetchall()]
        
    cutoff_date = datetime.now(ZoneInfo("Asia/Kolkata")).date() - timedelta(days=14)
    logger.info(f"Checking splits for {len(symbols)} focused symbols...")
    
    for symbol in symbols:
        try:
            ticker = yf.Ticker(f"{symbol}.NS")
            splits = ticker.splits
            
            if splits.empty:
                continue
                
            # Filter for recent splits
            recent_splits = splits[splits.index.date >= cutoff_date]
            
            for split_date, split_factor in recent_splits.items():
                ex_date = split_date.date()
                
                # yfinance format: split_factor = new_shares / old_shares (e.g., 10.0 means 10 for 1)
                # Our schema: ratio_from = old, ratio_to = new
                ratio_from = 1.0
                ratio_to = float(split_factor)
                
                record_corporate_action(
                    symbol=symbol,
                    action_type="SPLIT",
                    ex_date=ex_date,
                    ratio_from=ratio_from,
                    ratio_to=ratio_to
                )
        except Exception as e:
            logger.error(f"Error fetching splits for {symbol}: {e}")
            
    logger.info("Corporate actions scan complete. Applying pending actions to database...")
    apply_pending_corporate_actions()


if __name__ == "__main__":
    try:
        fetch_and_record_splits()
    except Exception as e:
        import traceback
        logger.error(f"Cron execution failed: {e}")
        from src.notification.telegram_bot import send_telegram_error_alert
        send_telegram_error_alert("run_corporate_actions", str(e) + "\n" + traceback.format_exc())
