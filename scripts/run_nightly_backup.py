"""
Nightly DuckDB Cloud Backup to Backblaze B2 (S3-compatible).
Scheduled: 02:00 AM IST daily via run_scheduler.py.

Strategy:
  1. Force DuckDB WAL checkpoint (safe to copy after this)
  2. Copy DB file to staging path
  3. Upload via boto3 (S3-compatible B2 API)
  4. Verify upload size matches local size
  5. Enforce 30-day rolling retention (delete old files)
  6. Send Telegram confirmation or failure alert
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import shutil
import logging
import datetime
import duckdb
import boto3
from botocore.client import Config

from src.config.settings import settings
from src.notification.telegram_bot import send_telegram_alert
from src.utils.job_alert import job_alert_context

logger = logging.getLogger("run_nightly_backup")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = str(PROJECT_ROOT / "alphasentinel.duckdb")
STAGING_DIR = PROJECT_ROOT / "data" / "backup_staging"


def _get_s3_client():
    """Returns a boto3 S3 client configured for Backblaze B2 or S3-compatible store."""
    if not settings.B2_KEY_ID or not settings.B2_APPLICATION_KEY:
        raise RuntimeError("B2 credentials not configured. Set B2_KEY_ID and B2_APPLICATION_KEY in .env")
    
    endpoint = settings.B2_ENDPOINT_URL if settings.B2_ENDPOINT_URL else None
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.B2_KEY_ID,
        aws_secret_access_key=settings.B2_APPLICATION_KEY,
        config=Config(signature_version="s3v4"),
    )


def _enforce_retention(s3_client, bucket: str, retention_days: int = 30) -> None:
    """Delete backups older than retention_days from the bucket."""
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=retention_days)
    try:
        response = s3_client.list_objects_v2(Bucket=bucket)
        if "Contents" not in response:
            return
        for obj in response["Contents"]:
            if obj.get("LastModified") and obj["LastModified"] < cutoff:
                s3_client.delete_object(Bucket=bucket, Key=obj["Key"])
                logger.info(f"Backup retention: deleted old backup {obj['Key']}")
    except Exception as e:
        logger.warning(f"Error enforcing retention policy: {e}")


def run_backup() -> str:
    """
    Checkpoint DuckDB WAL, stage a copy, upload to B2, verify, and enforce retention.
    Returns the backup filename.
    """
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"alphasentinel_{timestamp}.duckdb"
    staging_path = STAGING_DIR / backup_filename

    # Step 1: Force WAL checkpoint so the DB file is safe to copy
    try:
        if Path(DB_PATH).exists():
            with duckdb.connect(DB_PATH, read_only=False) as con:
                con.execute("CHECKPOINT;")
            logger.info("DuckDB WAL checkpoint completed.")
        else:
            logger.info(f"Database file {DB_PATH} not yet created on disk. Skipping backup.")
            return ""
    except Exception as e:
        logger.error(f"DuckDB WAL checkpoint failed: {e}")
        send_telegram_alert(f"🚨 [run_nightly_backup] WAL checkpoint failed: {e}")
        raise

BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


def _enforce_local_retention(backup_dir: Path, retention_days: int = 30) -> None:
    """Delete local backups older than retention_days."""
    cutoff = datetime.datetime.now().timestamp() - (retention_days * 86400)
    for p in backup_dir.glob("alphasentinel_*.duckdb"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                logger.info(f"Local backup retention: removed old backup {p.name}")
        except Exception as e:
            logger.warning(f"Error removing old local backup {p.name}: {e}")


def run_backup() -> str:
    """
    Checkpoint DuckDB WAL, create timestamped backup, upload to B2 if configured or retain locally.
    Returns the backup filename.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"alphasentinel_{timestamp}.duckdb"
    dest_path = BACKUP_DIR / backup_filename

    # Step 1: Force WAL checkpoint so the DB file is safe to copy
    try:
        if Path(DB_PATH).exists():
            with duckdb.connect(DB_PATH, read_only=False) as con:
                con.execute("CHECKPOINT;")
            logger.info("DuckDB WAL checkpoint completed.")
        else:
            logger.info(f"Database file {DB_PATH} not yet created on disk. Skipping backup.")
            return ""
    except Exception as e:
        logger.error(f"DuckDB WAL checkpoint failed: {e}")
        send_telegram_alert(f"🚨 [run_nightly_backup] WAL checkpoint failed: {e}")
        raise

    # Step 2: Copy to local backup directory
    shutil.copy2(DB_PATH, dest_path)
    local_size = os.path.getsize(dest_path)
    logger.info(f"DB backed up at {dest_path} ({local_size / 1024 / 1024:.2f} MB)")

    # Step 3: Check if Cloud S3 / B2 upload is configured
    has_b2 = bool(settings.B2_KEY_ID and settings.B2_APPLICATION_KEY)
    if has_b2:
        try:
            s3 = _get_s3_client()
            s3.upload_file(str(dest_path), settings.B2_BUCKET_NAME, backup_filename)
            logger.info(f"Uploaded {backup_filename} to bucket {settings.B2_BUCKET_NAME}")

            remote_meta = s3.head_object(Bucket=settings.B2_BUCKET_NAME, Key=backup_filename)
            remote_size = remote_meta["ContentLength"]
            if local_size != remote_size:
                raise ValueError(
                    f"Size mismatch after upload: local={local_size}, remote={remote_size}"
                )

            send_telegram_alert(
                f"✅ Nightly Cloud Backup Complete: {backup_filename} "
                f"({local_size / 1024 / 1024:.2f} MB)"
            )
            _enforce_retention(s3, settings.B2_BUCKET_NAME, settings.BACKUP_RETENTION_DAYS)
        except Exception as e:
            logger.error(f"Cloud backup upload failed: {e}")
            send_telegram_alert(f"⚠️ [run_nightly_backup] Cloud upload failed (local copy preserved): {e}")
            raise
    else:
        logger.info(f"B2 credentials not configured. Maintained local backup in {BACKUP_DIR}")
        _enforce_local_retention(BACKUP_DIR, settings.BACKUP_RETENTION_DAYS)
        send_telegram_alert(
            f"✅ Nightly Local Backup Complete: {backup_filename} "
            f"({local_size / 1024 / 1024:.2f} MB preserved on VM disk)"
        )

    return backup_filename


if __name__ == "__main__":
    with job_alert_context("run_nightly_backup"):
        run_backup()
