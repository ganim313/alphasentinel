"""
Fyers Symbol Master Synchronization.
Downloads the daily Fyers Symbol Master CSV and updates the local DuckDB instrument_master table.
This mapping is crucial for routing raw NSE symbols to Fyers Tokens or Dhan Security IDs.
"""

import logging
import time
import requests
import pandas as pd
from io import BytesIO
from src.db.queue_writer import db_write_many

logger = logging.getLogger(__name__)

FYERS_SYMBOL_MASTER_URL = "https://public.fyers.in/sym_details/NSE_CM.csv"

def sync_instrument_master(max_retries=3):
    """
    Downloads Fyers Symbol Master, parses it safely, and UPSERTs into DuckDB.
    Failsafes: Only applies update if > 2000 rows are successfully parsed.
    """
    logger.info("Starting Fyers Symbol Master Sync...")
    
    delay = 2
    response = None
    for attempt in range(max_retries):
        try:
            response = requests.get(FYERS_SYMBOL_MASTER_URL, timeout=30)
            response.raise_for_status()
            break
        except Exception as e:
            logger.warning(f"Fyers CSV fetch failed on attempt {attempt+1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                logger.error("All retries exhausted for Fyers Symbol Master sync.")
                return False
        
    try:
        # Fyers CSV doesn't have headers and currently has 21 columns. 
        # Column 0: Fytoken, Column 3: LotSize, Column 4: TickSize, Column 9: SymbolTicker
        df = pd.read_csv(BytesIO(response.content), header=None)
        
        if len(df) < 2000:
            logger.error(f"Symbol Master downloaded but only {len(df)} rows parsed. Aborting UPSERT to protect mapping table.")
            return False
            
        records = []
        for _, row in df.iterrows():
            ticker = str(row.iloc[9]).strip() if len(row) > 9 else ""
            if not ticker.startswith("NSE:"):
                continue
                
            parts = ticker.replace("NSE:", "").rsplit("-", 1)
            if len(parts) >= 2:
                base_sym = parts[0]
                series = parts[1]
                if series not in ["EQ", "BE", "SM"]:
                    continue # Ignore indices and non-equity for now
                    
                records.append((
                    base_sym,
                    str(row.iloc[0]),
                    # dhan_security_id (null for now, will map later if needed)
                    None,
                    "NSE",
                    series,
                    int(row.iloc[3] if pd.notna(row.iloc[3]) else 1),
                    float(row.iloc[4] if pd.notna(row.iloc[4]) else 0.05)
                ))
                
        # Deduplicate records by base_sym, strictly prioritizing 'EQ' series
        best_records = {}
        for r in records:
            base_sym = r[0]
            series = r[4]
            if base_sym not in best_records:
                best_records[base_sym] = r
            elif series == "EQ":
                best_records[base_sym] = r
        final_records = list(best_records.values())

        if len(final_records) > 1000:
            query = """
            INSERT INTO instrument_master (symbol, fyers_token, dhan_security_id, exchange, series, lot_size, tick_size)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (symbol) DO UPDATE SET
                fyers_token = EXCLUDED.fyers_token,
                series = CASE WHEN instrument_master.series = 'EQ' AND EXCLUDED.series != 'EQ' THEN instrument_master.series ELSE EXCLUDED.series END,
                lot_size = EXCLUDED.lot_size,
                tick_size = EXCLUDED.tick_size,
                updated_at = now();
            """
            db_write_many(query, final_records)
            logger.info(f"Successfully UPSERTed {len(final_records)} instruments into instrument_master.")
            return True

        else:
            logger.error("Failed to parse enough valid equity symbols from Fyers Symbol Master. Aborting UPSERT.")
            return False
            
    except Exception as e:
        logger.error(f"Failed to sync instrument master: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_instrument_master()
