import sys
import os
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import duckdb
from pathlib import Path
import os
import portalocker
from src.db.session import get_db_path, db_rlock
from src.utils.job_alert import job_alert_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("run_db_maintenance")

def perform_maintenance():
    """
    Checkpoints the WAL file and vacuums the database to prevent storage explosion.
    Addresses the 'DuckDB WAL File Explosion' vulnerability.
    Acquires exclusive process lock and thread lock to prevent concurrent write collisions.
    """
    logger.info("Starting DuckDB maintenance (Checkpoint & Vacuum)...")
    
    db_path = get_db_path()
    lock_path = db_path + ".lock"
    wal_path = Path(str(db_path) + ".wal")
    if wal_path.exists():
        wal_size_mb = os.path.getsize(wal_path) / (1024 * 1024)
        logger.info(f"WAL file size before checkpoint: {wal_size_mb:.2f} MB")
    
    try:
        with db_rlock, portalocker.Lock(lock_path, timeout=300, fail_when_locked=False):
            conn = duckdb.connect(str(db_path))
            try:
                conn.execute("PRAGMA threads=2;")
                conn.execute("PRAGMA force_checkpoint;")
                logger.info("WAL checkpoint complete.")
                conn.execute("VACUUM;")
                logger.info("VACUUM complete.")
            finally:
                conn.close()
        logger.info("Database maintenance completed successfully.")
    except portalocker.LockException:
        logger.error("Maintenance ABORTED: Could not acquire exclusive DB lock within 300s.")
        raise
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        raise
        
    if wal_path.exists():
        wal_size_mb = os.path.getsize(wal_path) / (1024 * 1024)
        logger.info(f"WAL file size after checkpoint: {wal_size_mb:.2f} MB")

if __name__ == "__main__":
    with job_alert_context("run_db_maintenance"):
        perform_maintenance()
