import logging
from datetime import date
from typing import Optional
import pandas as pd
import numpy as np
from src.db.session import get_read_connection
from src.ingestion.corporate_actions import apply_pending_corporate_actions

logger = logging.getLogger(__name__)


def ingest_bhavcopy_dataframe(df: pd.DataFrame, trade_date: date) -> int:
    """
    Ingests a normalized Bhavcopy dataframe into DuckDB bhavcopy_daily table.
    Ensures NaN values are imputed and types are strictly validated.
    """
    if df.empty:
        logger.warning(f"Empty Bhavcopy dataframe provided for date {trade_date}")
        return 0

    # Map new NSE Bhavcopy format to old format if necessary
    format_mapping = {
        'TckrSymb': 'SYMBOL',
        'SctySrs': 'SERIES',
        'OpnPric': 'OPEN',
        'HghPric': 'HIGH',
        'LwPric': 'LOW',
        'ClsPric': 'CLOSE',
        'PrvsClsgPric': 'PREVCLOSE',
        'TtlTradgVol': 'TOTTRDQTY',
        'TtlTrfVal': 'TOTTRDVAL'
    }
    df.rename(columns=format_mapping, inplace=True)

    # Ensure required columns exist
    required_cols = [
        "SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE", 
        "TOTTRDQTY", "TOTTRDVAL"
    ]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required Bhavcopy column: {col}")

    # Standardize column naming
    df["trade_date"] = trade_date
    df["split_multiplier"] = 1.0
    
    # Impute missing delivery metrics with safe defaults
    if "DELIV_QTY" not in df.columns:
        df["delivery_qty"] = 0
        df["delivery_pct"] = 0.0
    else:
        df["delivery_qty"] = df["DELIV_QTY"].fillna(0)
        df["delivery_pct"] = df["DELIV_PER"].fillna(0.0)

    def safe_float(val):
        if not pd.notna(val): return None
        try:
            if isinstance(val, str):
                val = val.strip()
                if val == "-" or val == "" or val.upper() in ["NA", "NAN", "NULL"]: return None
                val = val.replace(",", "")
            return float(val)
        except ValueError:
            return None
    
    def safe_int(val):
        if not pd.notna(val): return None
        try:
            if isinstance(val, str):
                val = val.strip()
                if val == "-" or val == "" or val.upper() in ["NA", "NAN", "NULL"]: return None
                val = val.replace(",", "")
            return int(float(val))
        except ValueError:
            return None

    # Pre-fetch previous day close prices in a single batch query to prevent N+1 connection overhead
    prev_close_map = {}
    try:
        with get_read_connection() as conn:
            prior_rows = conn.execute("""
                SELECT symbol, close_price 
                FROM bhavcopy_daily 
                WHERE trade_date = (SELECT MAX(trade_date) FROM bhavcopy_daily WHERE trade_date < ?)
            """, (trade_date,)).fetchall()
            prev_close_map = {r[0]: float(r[1]) for r in prior_rows if r[1] is not None}
    except Exception as e:
        logger.warning(f"Could not batch pre-fetch prior closes: {e}")

    param_list = []
    
    for _, row in df.iterrows():
        symbol = str(row["SYMBOL"]).strip()
        series = str(row.get("SERIES", "EQ")).strip()
        if series not in ["EQ", "BE", "SM"]:
            continue  # Filter out non-equity series (bonds, preference shares)

        upper = row.get("UPPER_CIRCUIT")
        upper = safe_float(upper) if upper is not None else None
        
        lower = row.get("LOWER_CIRCUIT")
        lower = safe_float(lower) if lower is not None else None
        
        band = row.get("CIRCUIT_BAND_PCT")
        band = safe_int(band) if band is not None else None

        prev_close_val = row.get("PREVCLOSE")
        if not pd.notna(prev_close_val) or str(prev_close_val).strip() in ("-", "nan", "NaN", "None", ""):
            prev_close_val = None
        prev_close = safe_float(prev_close_val)
        if prev_close is None:
            prev_close = prev_close_map.get(symbol)
        if prev_close is None:
            prev_close = safe_float(row.get("OPEN"))
        
        if band is None:
            if upper is not None and prev_close is not None and prev_close > 0:
                band = int(round((upper - prev_close) / prev_close * 100))
            else:
                # By NSE rules: Trade-to-Trade (BE, BZ) and SME (SM) have 5% (or 2%) circuit limits
                band = 5 if series in ["BE", "BZ", "SM"] else 20

        # Synthesize upper/lower limits from prev_close and band if omitted in Bhavcopy CSV
        if prev_close is not None and prev_close > 0:
            if upper is None:
                upper = round(prev_close * (1.0 + (band / 100.0)), 2)
            if lower is None:
                lower = round(prev_close * (1.0 - (band / 100.0)), 2)


        deliv_q = row.get("DELIV_QTY") if row.get("DELIV_QTY") is not None else row.get("delivery_qty")
        deliv_p = row.get("DELIV_PER") if row.get("DELIV_PER") is not None else row.get("delivery_pct")

        params = (
            symbol, trade_date, series,
            safe_float(row.get("OPEN")), safe_float(row.get("HIGH")),
            safe_float(row.get("LOW")), safe_float(row.get("CLOSE")),
            prev_close, safe_int(row.get("TOTTRDQTY")),
            safe_float(row.get("TOTTRDVAL")), safe_int(deliv_q) or 0,
            safe_float(deliv_p) or 0.0, 1.0,
            upper, lower, band, False, False
        )
        param_list.append(params)

    if param_list:
        from src.db.queue_writer import db_write_many
        query = """
        INSERT OR IGNORE INTO bhavcopy_daily (
            symbol, trade_date, series, open_price, high_price, low_price, 
            close_price, prev_close, total_traded_qty, total_traded_val, 
            delivery_qty, delivery_pct, split_multiplier,
            upper_circuit, lower_circuit, circuit_band_pct,
            is_asm, is_gsm
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        db_write_many(query, param_list)
        rows_inserted = len(param_list)
        logger.info(f"Bulk ingested {rows_inserted} Bhavcopy records for {trade_date}.")
    else:
        rows_inserted = 0
        logger.info(f"No valid records found to ingest for {trade_date}.")
    
    # Apply corporate actions retroactively if any were logged
    apply_pending_corporate_actions()
    
    return rows_inserted

def fetch_bhavcopy_with_retry_and_fallback(trade_date: date, max_retries: int = 3) -> Optional[pd.DataFrame]:
    """
    Attempts to download Bhavcopy for a given date.
    If it fails, retries with exponential backoff.
    If all retries fail, falls back to yfinance to fetch data for the symbols tracked in bhavcopy_daily.
    """
    import os
    import time
    from jugaad_data.nse import bhavcopy_save
    
    delay = 2
    for attempt in range(max_retries):
        try:
            file_path = bhavcopy_save(trade_date, ".")
            if file_path and os.path.exists(file_path):
                df_bhav = pd.read_csv(file_path)
                os.remove(file_path)
                logger.info(f"Successfully downloaded Bhavcopy for {trade_date} on attempt {attempt+1}")
                return df_bhav
        except Exception as e:
            logger.warning(f"Bhavcopy download failed on attempt {attempt+1} for {trade_date}: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"All {max_retries} attempts failed for Bhavcopy on {trade_date}. Falling back to yfinance.")
                
    # Fallback to Fyers API
    try:
        logger.error(f"All attempts failed for Bhavcopy on {trade_date}. Falling back to Fyers Historical API.")
        from src.ingestion.fyers_client import fyers_client
        from src.db.session import get_read_connection
        
        # Pull entire mapped universe to prevent downstream starvation
        with get_read_connection() as conn:
            symbols = conn.execute("SELECT DISTINCT symbol FROM instrument_master WHERE fyers_token IS NOT NULL").df()['symbol'].tolist()
            
        if not symbols:
            logger.error("No mapped symbols in instrument_master. Fyers fallback aborted.")
            try:
                from src.notification.telegram_bot import send_telegram_alert
                send_telegram_alert(
                    "🚨 <b>BHAVCOPY FALLBACK EMPTY</b>\n"
                    "Fyers token fallback = 0 symbols. <code>instrument_master</code> is unpopulated.\n"
                    "Run <code>symbol_sync.py</code> manually."
                )
            except Exception:
                pass
            return pd.DataFrame()
            
        if fyers_client.model is None and not isinstance(getattr(fyers_client.fetch_historical_data, "return_value", None), pd.DataFrame):
            logger.warning(f"Fyers client model is None (unauthenticated). Skipping Fyers historical fallback loop for {trade_date}.")
            return None

        dfs = []
        date_str = trade_date.strftime("%Y-%m-%d")
        for sym in symbols:
            df_sym = fyers_client.fetch_historical_data(sym, date_str, date_str)
            if not df_sym.empty:
                # Map to standard bhavcopy format
                df_sym['SYMBOL'] = sym
                df_sym['SERIES'] = 'EQ'
                df_sym['OPEN'] = df_sym['open']
                df_sym['HIGH'] = df_sym['high']
                df_sym['LOW'] = df_sym['low']
                df_sym['CLOSE'] = df_sym['close']
                
                # Do NOT fake prev_close; leave NaN so downstream calculates from historical DB row
                df_sym['PREVCLOSE'] = np.nan 
                
                df_sym['TOTTRDQTY'] = df_sym['volume']
                df_sym['TOTTRDVAL'] = df_sym['close'] * df_sym['volume']
                
                # Do NOT fake delivery data; Broker APIs lack clearing house stats
                df_sym['DELIV_QTY'] = np.nan
                df_sym['DELIV_PER'] = np.nan
                
                dfs.append(df_sym)
                
        if dfs:
            fallback_df = pd.concat(dfs, ignore_index=True)
            logger.info(f"Successfully constructed Bhavcopy fallback for {len(fallback_df)} symbols via Fyers.")
            return fallback_df
            
        logger.error("Fyers fallback returned 0 rows for all symbols.")
        try:
            from src.notification.telegram_bot import send_telegram_alert
            send_telegram_alert(
                f"🚨 <b>BHAVCOPY FALLBACK RETURNED 0 ROWS</b>\n"
                f"Fyers historical fallback returned 0 rows for {trade_date} across {len(symbols)} symbols."
            )
        except Exception:
            pass
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Fallback to Fyers API failed: {e}")
        try:
            from src.notification.telegram_bot import send_telegram_alert
            send_telegram_alert(f"🚨 <b>BHAVCOPY FALLBACK EXCEPTION</b>\nFyers API fallback failed for {trade_date}: {e}")
        except Exception:
            pass
        return pd.DataFrame()


# Alias for compatibility with tests and pipelines
download_and_ingest_bhavcopy = fetch_bhavcopy_with_retry_and_fallback


def main():
    import argparse
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    from src.utils.holidays import is_nse_holiday

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="NSE Bhavcopy Ingestion & Backfill Utility")
    parser.add_argument("--date", type=str, help="Specific trade date to ingest (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, help="Number of recent trading days to backfill")
    parser.add_argument("--start", type=str, help="Start date for backfill range (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date for backfill range (YYYY-MM-DD)")
    args = parser.parse_args()

    ist = ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist).date()

    dates_to_ingest = []

    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
        dates_to_ingest = [d]
    elif args.start and args.end:
        start_d = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_d = datetime.strptime(args.end, "%Y-%m-%d").date()
        curr = start_d
        while curr <= end_d:
            if curr.weekday() < 5 and not is_nse_holiday(curr):
                dates_to_ingest.append(curr)
            curr += timedelta(days=1)
    elif args.days:
        curr = today
        count = 0
        while count < args.days:
            if curr.weekday() < 5 and not is_nse_holiday(curr):
                dates_to_ingest.append(curr)
                count += 1
            curr -= timedelta(days=1)
        dates_to_ingest.reverse()
    else:
        # Default: Ingest from last ingested date up to today (or today if empty)
        try:
            with get_read_connection() as conn:
                last_row = conn.execute("SELECT MAX(trade_date) FROM bhavcopy_daily").fetchone()
                last_date = last_row[0] if last_row and last_row[0] else (today - timedelta(days=5))
        except Exception:
            last_date = today - timedelta(days=5)

        curr = last_date + timedelta(days=1)
        while curr <= today:
            if curr.weekday() < 5 and not is_nse_holiday(curr):
                dates_to_ingest.append(curr)
            curr += timedelta(days=1)

        if not dates_to_ingest:
            # If already up to date, check if today is a trading day
            if today.weekday() < 5 and not is_nse_holiday(today):
                dates_to_ingest = [today]

    if not dates_to_ingest:
        logger.info("No trading dates to ingest. Database is already up to date.")
        return

    logger.info(f"Targeting {len(dates_to_ingest)} trading date(s) for Bhavcopy ingestion: {dates_to_ingest}")

    total_records = 0
    for d in dates_to_ingest:
        logger.info(f"Fetching Bhavcopy for {d}...")
        df = fetch_bhavcopy_with_retry_and_fallback(d)
        if df is not None and not df.empty:
            count = ingest_bhavcopy_dataframe(df, d)
            total_records += count
            logger.info(f"✓ Ingested {count} records for {d}.")
        else:
            logger.warning(f"⚠ No Bhavcopy data available for {d} (exchange may not have published yet).")

    logger.info(f"Bhavcopy ingestion completed. Total records inserted: {total_records}")


if __name__ == "__main__":
    main()



