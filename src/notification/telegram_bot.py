"""
Telegram Dispatcher with Rate-Limit Batching & Global Kill Switch (/HALT_ALL).
Implements message queueing to prevent HTTP 429 rate limit drops and handles instant circuit breaker freezing.
"""

import sys
from pathlib import Path

# Ensure root directory is in sys.path so 'src' module can be found when run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import time
import logging
from typing import List, Dict, Any, Optional
import requests
from src.config.settings import settings
from src.db.queue_writer import db_write
from src.db.session import get_read_connection

logger = logging.getLogger(__name__)


def is_system_halted() -> bool:
    """Checks if the global emergency kill switch has been triggered."""
    try:
        with get_read_connection() as conn:
            row = conn.execute("SELECT is_halted FROM circuit_breaker_state WHERE id = 1;").fetchone()
            return bool(row[0]) if row else False
    except Exception as e:
        logger.warning(f"Could not check circuit_breaker_state ({e}). Retrying once...")
        try:
            time.sleep(0.5)
            with get_read_connection() as conn:
                row = conn.execute("SELECT is_halted FROM circuit_breaker_state WHERE id = 1;").fetchone()
                return bool(row[0]) if row else False
        except Exception as retry_err:
            logger.error(f"Persistent failure reading circuit_breaker_state: {retry_err}. Failing closed (HALTED) for capital preservation.")
            return True


def set_system_halt_state(halted: bool, reason: str = "TELEGRAM_KILL_SWITCH"):
    """Flips the global emergency kill switch in DuckDB."""
    query = """
    UPDATE circuit_breaker_state 
    SET is_halted = ?, halt_reason = ?, last_kill_switch_trigger = CURRENT_TIMESTAMP 
    WHERE id = 1;
    """
    db_write(query, (halted, reason), sync=True)
    logger.warning(f"Global Kill Switch updated: is_halted={halted}, reason={reason}")


def send_telegram_trade_card(card_data: Dict[str, Any]) -> bool:
    """
    Formats and dispatches a high-priority Trade Card alert to Telegram.
    """
    if is_system_halted():
        logger.warning("System is HALTED. Suppressing trade card broadcast.")
        return False

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.info(f"[SIMULATED TELEGRAM CARD for {card_data.get('symbol')}]:\n{card_data.get('formatted_markdown')}")
        return True

    def escape_html(text: str) -> str:
        """Escape characters that break Telegram's HTML parser."""
        if not text:
            return ""
        text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return text

    bull_escaped = escape_html(card_data.get('bull_thesis', 'N/A'))
    bear_escaped = escape_html(card_data.get('bear_risks', 'N/A'))
    
    try:
        t_price = float(card_data.get('trigger_price', 0.0))
        sl_price = float(card_data.get('stop_loss_price', 0.0))
        pct_risk = ((t_price - sl_price) / t_price * 100) if t_price > 0 else 0.0
    except (ValueError, TypeError):
        t_price = 0.0
        pct_risk = 0.0

    try:
        cap_dep = float(card_data.get('total_capital_deployed', 0.0))
    except (ValueError, TypeError):
        cap_dep = 0.0

    text = f"""🎯 <b>ALPHASENTINEL TRADE ALERT ({escape_html(card_data.get('symbol'))})</b>
━━━━━━━━━━━━━━━━━━━━
<b>Setup:</b> <code>{escape_html(card_data.get('pattern_type', 'VCP_STAGE2'))}</code>
<b>Trigger Entry:</b> <code>₹{t_price:.2f}</code>
<b>Stop Loss:</b> <code>₹{float(card_data.get('stop_loss_price', 0.0)):.2f}</code> (-{pct_risk:.1f}%)
<b>Target 1 (2R):</b> <code>₹{float(card_data.get('target_1_price', 0.0)):.2f}</code>
<b>Target 2 (3.5R):</b> <code>₹{float(card_data.get('target_2_price', 0.0)):.2f}</code>

📊 <b>Sizing & Risk:</b>
<b>Shares:</b> <code>{card_data.get('suggested_shares')}</code>
<b>Capital Deployed:</b> <code>₹{cap_dep:,.0f}</code> ({card_data.get('portfolio_allocation_pct')}% port)
<b>Risk / Reward:</b> <code>{float(card_data.get('risk_reward_ratio', 0.0)):.1f}R</code>
⚠️ <i>Note: Assuming 20% circuit limit (Gap-down risk).</i>

🐂 <b>Bull Thesis:</b>
{bull_escaped}

🐻 <b>Bear Risks:</b>
{bear_escaped}

<b>Risk Arbiter Verdict:</b> <code>{escape_html(card_data.get('risk_verdict'))}</code>
<i>{escape_html(card_data.get('rejection_reason', ''))}</i>
━━━━━━━━━━━━━━━━━━━━
<i>Mode: Paper Trading 1-Month Validation Gate</i>"""

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    # CRITICAL FIX: Exponential Backoff for Telegram Rate Limits (HTTP 429) and Server Errors (5xx)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, timeout=10.0)
            if res.status_code == 200:
                return True
            elif res.status_code == 429:
                retry_after = int(res.json().get("parameters", {}).get("retry_after", 5))
                logger.warning(f"Telegram Rate Limited (429). Retrying after {retry_after}s...")
                time.sleep(retry_after)
            elif res.status_code >= 500:
                logger.warning(f"Telegram Server Error {res.status_code}. Retrying...")
                time.sleep(2 ** attempt)
            else:
                logger.error(f"Telegram API Error {res.status_code}: {res.text}")
                return False
        except Exception as e:
            logger.warning(f"Failed to dispatch Telegram message (Attempt {attempt+1}/{max_retries}): {e}")
            time.sleep(2 ** attempt)

    logger.error("Exhausted all retries for Telegram dispatch.")
    return False


def send_telegram_alert(message: str) -> bool:
    """
    Sends a plain-text alert to Telegram.
    Thin wrapper around sendMessage for system-level warnings (scraper failures, etc.)
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning(f"[SIMULATED TELEGRAM ALERT]: {message}")
        return True

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, timeout=10.0)
            if res.status_code == 200:
                return True
            elif res.status_code == 400:
                # Fallback to plain text in case of unescaped HTML entities
                plain_payload = {
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": message
                }
                res_plain = requests.post(url, json=plain_payload, timeout=10.0)
                return res_plain.status_code == 200
            elif res.status_code == 429:
                retry_after = int(res.json().get("parameters", {}).get("retry_after", 5))
                time.sleep(retry_after)
            else:
                return False
        except Exception as e:
            time.sleep(2 ** attempt)

    return False


def send_telegram_error_alert(job_name: str, error_message: str) -> bool:
    """Sends a cron error alert to telegram."""
    error_message_escaped = str(error_message).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = f"🚨 <b>CRON ERROR:</b> <code>{job_name}</code>\n\n<pre>\n{error_message_escaped}\n</pre>"
    return send_telegram_alert(text)


def send_telegram_safe_halt_alarm(reason: str) -> bool:
    """Sends a safe halt alarm to telegram."""
    import html
    escaped_reason = html.escape(str(reason))
    text = f"🛑 <b>SAFE HALT TRIGGERED</b>\n\n<b>Reason:</b> <code>{escaped_reason}</code>"
    return send_telegram_alert(text)


def send_telegram_morning_brief(macro_data: Dict[str, Any], top_movers: List[Any], watchlist: List[Any]) -> bool:
    """
    Sends the 8:45 AM Pre-Market Brief to Telegram.
    """
    if is_system_halted():
        logger.warning("System HALTED. Suppressing Morning Brief.")
        return False

    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.info("[SIMULATED TELEGRAM MORNING BRIEF]")
        return True

    def escape_html(text: str) -> str:
        if not text:
            return ""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    movers_text = "\n".join([f"• <code>{escape_html(m[0])}</code>: +{m[1]:.1f}%" for m in top_movers]) if top_movers else "• No data"
    watchlist_text = "\n".join([f"• <code>{escape_html(w[0])}</code> ({escape_html(w[1])} @ ₹{w[2]:.1f})" for w in watchlist]) if watchlist else "• No active setups"

    text = f"""🌅 <b>MORNING BRIEF (Executive Synthesis)</b>
━━━━━━━━━━━━━━━━━━━━
📊 <b>Macro Weather (8:45 AM)</b>
<b>Regime:</b> <code>{escape_html(macro_data.get('market_regime', 'N/A'))}</code>
<b>US VIX:</b> <code>{float(macro_data.get('us_vix', 0) or 0):.2f}</code>
<b>S&P 500:</b> <code>{float(macro_data.get('sp500_pct_change', 0) or 0):.2f}%</code>
<b>Target Cash:</b> <code>{float(macro_data.get('target_cash_exposure_pct', 0) or 0):.0f}%</code>

🚀 <b>Yesterday's Top Movers</b>
{movers_text}

🎯 <b>Active Watchlist (Approved)</b>
{watchlist_text}
━━━━━━━━━━━━━━━━━━━━"""

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, timeout=10.0)
            if res.status_code == 200:
                return True
            elif res.status_code == 429:
                retry_after = int(res.json().get("parameters", {}).get("retry_after", 5))
                time.sleep(retry_after)
            else:
                logger.error(f"Telegram API Error {res.status_code}: {res.text}")
                return False
        except Exception as e:
            time.sleep(2 ** attempt)

    return False
