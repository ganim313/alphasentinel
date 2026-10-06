import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
from src.db.session import get_write_connection
from src.screening.shariah_filter import check_shariah_compliance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clean_fundamentals_cache")

def clean_cache():
    with get_write_connection() as conn:
        rows = conn.execute("SELECT symbol, fundamentals_json FROM fundamentals_cache").fetchall()
        logger.info(f"Examining {len(rows)} cached symbols...")
        deleted = []
        for sym, f_json in rows:
            try:
                data = json.loads(f_json)
                sec = (data.get("sector_name") or "").strip()
                if not sec:
                    deleted.append((sym, "EMPTY_SECTOR"))
                    continue
                ok, reason = check_shariah_compliance(data, sector_name=sec)
                if not ok:
                    deleted.append((sym, reason))
            except Exception as e:
                deleted.append((sym, str(e)))

        logger.info(f"Purging {len(deleted)} non-compliant/invalid rows from fundamentals_cache...")
        for sym, reason in deleted:
            conn.execute("DELETE FROM fundamentals_cache WHERE symbol = ?", (sym,))

        remaining = conn.execute("SELECT COUNT(*) FROM fundamentals_cache").fetchone()[0]
        logger.info(f"Done. Remaining compliant symbols in fundamentals_cache: {remaining}")

if __name__ == "__main__":
    clean_cache()
