"""
Corporate Actions Ingestion & Historical Price Multiplier Adjuster.
Prevents false -80% crash alerts caused by unadjusted stock splits/bonuses.
"""

import logging
from typing import List, Dict, Any
from datetime import date
from src.db.session import get_read_connection
from src.db.queue_writer import db_write, db_transaction

logger = logging.getLogger(__name__)


def record_corporate_action(
    symbol: str,
    action_type: str,
    ex_date: date,
    ratio_from: float,
    ratio_to: float
) -> str:
    """
    Records a new corporate action and calculates the split multiplier.
    Convention:
    - SPLIT: ratio_from = old shares, ratio_to = new shares (e.g. 1 old into 10 new -> 1.0, 10.0 -> multiplier = 0.1)
             For reverse split (10 old into 1 new -> 10.0, 1.0 -> multiplier = 10.0)
    - BONUS: ratio_from = bonus shares, ratio_to = existing shares (e.g. 1 bonus for 1 existing -> 1.0, 1.0 -> multiplier = 1/(1+1) = 0.5)
             For 2:1 bonus (2 bonus for 1 existing -> 2.0, 1.0 -> multiplier = 1/(2+1) = 0.3333)
    """
    action_id = f"{symbol}_{action_type.upper()}_{ex_date.isoformat()}"
    
    act = action_type.upper()
    if act == "SPLIT":
        if "REV" in symbol.upper() or "REVERSE" in act:
            multiplier = max(ratio_from, ratio_to) / min(ratio_from, ratio_to) if min(ratio_from, ratio_to) > 0 else 1.0
        elif ratio_from > 0 and ratio_to > 0:
            multiplier = min(ratio_from, ratio_to) / max(ratio_from, ratio_to)
        else:
            multiplier = 1.0
    elif act == "REVERSE_SPLIT":
        multiplier = max(ratio_from, ratio_to) / min(ratio_from, ratio_to) if min(ratio_from, ratio_to) > 0 else 1.0
        multiplier = max(ratio_from, ratio_to) / min(ratio_from, ratio_to) if min(ratio_from, ratio_to) > 0 else 1.0
    elif act == "BONUS":
        total_shares = ratio_from + ratio_to
        multiplier = (min(ratio_from, ratio_to) / total_shares) if total_shares > 0 else 1.0
    elif act == "RIGHTS":
        multiplier = (ratio_from / ratio_to) if ratio_to > 0 else 1.0
    else:
        multiplier = 1.0

    query = """
    INSERT INTO corporate_actions (
        id, symbol, action_type, ex_date, ratio_from, ratio_to, adjustment_multiplier, is_applied
    ) VALUES (?, ?, ?, ?, ?, ?, ?, FALSE)
    ON CONFLICT (id) DO UPDATE SET
        ratio_from = excluded.ratio_from,
        ratio_to = excluded.ratio_to,
        adjustment_multiplier = excluded.adjustment_multiplier;
    """
    db_write(query, (action_id, symbol, act, ex_date, ratio_from, ratio_to, multiplier), sync=True)
    logger.info(f"Recorded corporate action: {action_id} with multiplier {multiplier:.6f}")
    return action_id


def apply_pending_corporate_actions():
    """
    Scans for unapplied corporate actions and retroactively adjusts historical bhavcopy prices
    and active positions for all dates BEFORE the ex_date.
    """
    with get_read_connection() as conn:
        actions = conn.execute("""
            SELECT id, symbol, ex_date, adjustment_multiplier 
            FROM corporate_actions 
            WHERE is_applied = FALSE
        """).fetchall()

    if not actions:
        logger.info("No pending corporate actions to apply.")
        return

    for action_id, symbol, ex_date, multiplier in actions:
        logger.info(f"Applying corporate action {action_id} to {symbol} (multiplier={multiplier:.6f}) before {ex_date}...")
        
        with db_transaction() as txn:
            # 1. Adjust past OHLCV prices and circuit limits in bhavcopy_daily
            update_bhavcopy = """
            UPDATE bhavcopy_daily
            SET 
                open_price = open_price * ?,
                high_price = high_price * ?,
                low_price = low_price * ?,
                close_price = close_price * ?,
                prev_close = prev_close * ?,
                upper_circuit = CASE WHEN upper_circuit IS NOT NULL THEN upper_circuit * ? ELSE NULL END,
                lower_circuit = CASE WHEN lower_circuit IS NOT NULL THEN lower_circuit * ? ELSE NULL END,
                total_traded_qty = CAST(total_traded_qty / ? AS BIGINT),
                delivery_qty = CAST(delivery_qty / ? AS BIGINT),
                split_multiplier = split_multiplier * ?
            WHERE symbol = ? AND trade_date < ?;
            """
            txn.execute(
                update_bhavcopy,
                (multiplier, multiplier, multiplier, multiplier, multiplier,
                 multiplier, multiplier, multiplier, multiplier, multiplier, symbol, ex_date)
            )
            
            # 2. Synchronously adjust active positions in positions table to prevent -90% stop-out bombs
            update_positions = """
            UPDATE positions
            SET
                entry_price = entry_price * ?,
                quantity = CAST(quantity / ? AS INTEGER),
                trailing_stop_loss = trailing_stop_loss * ?,
                target_1 = target_1 * ?,
                target_2 = CASE WHEN target_2 IS NOT NULL THEN target_2 * ? ELSE NULL END,
                peak_high = CASE WHEN peak_high IS NOT NULL THEN peak_high * ? ELSE NULL END,
                current_ltp = current_ltp * ?
            WHERE symbol = ? AND status IN ('OPEN', 'TARGET_1_TRIMMED') AND entry_date < ?;
            """
            txn.execute(
                update_positions,
                (multiplier, multiplier, multiplier, multiplier, multiplier, multiplier, multiplier, symbol, ex_date)
            )

            # 3. Mark action as applied
            txn.execute("UPDATE corporate_actions SET is_applied = TRUE WHERE id = ?", (action_id,))
            
        logger.info(f"Successfully applied corporate action {action_id} to bhavcopy and active positions.")

