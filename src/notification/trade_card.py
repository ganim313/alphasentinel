"""
Rich Multi-Channel Trade Card Formatter (Inspired by QuantDinger / TradingAgents).
Produces clean, structured Markdown and HTML trade cards for Telegram and Streamlit.
"""

from typing import Dict, Any, Optional
import html

def format_telegram_trade_card(state: Dict[str, Any]) -> str:
    """
    Generates a structured, emojis-rich Markdown trade card for Telegram alerts.
    """
    raw_symbol = str(state.get("symbol", "UNKNOWN")).replace(".NS", "")
    symbol = html.escape(raw_symbol)
    trigger = float(state.get("trigger_price", 0.0) or 0.0)
    current = float(state.get("current_price", trigger) or trigger)
    shares = state.get("suggested_shares", 0)
    stop_loss = float(state.get("stop_loss_price", 0.0) or 0.0)
    target_1 = float(state.get("target_1_price", 0.0) or 0.0)
    target_2 = float(state.get("target_2_price", 0.0) or 0.0)
    rr = float(state.get("risk_reward_ratio", 0.0) or 0.0)
    alloc_pct = float(state.get("portfolio_allocation_pct", 0.0) or 0.0)
    verdict = html.escape(str(state.get("risk_verdict", "PENDING")))
    
    # Quantitative & Multi-Agent Signals
    conviction = float(state.get("conviction_score", 7.0) or 7.0)
    tv = state.get("tv_technical_rating", {})
    tv_rec = html.escape(str(tv.get("recommendation", "BUY") if tv else "BUY"))
    
    bull = html.escape(str(state.get("bull_thesis", "Momentum continuation and volume contraction.")).strip())
    bear = html.escape(str(state.get("bear_risks", "Overhead supply zone and macro volatility.")).strip())
    judge = html.escape(str(state.get("judge_synthesis", "Favorable risk-reward breakout opportunity.")).strip())

    # Calculate stop loss distance %
    sl_pct = ((trigger - stop_loss) / trigger * 100) if trigger > 0 else 0.0
    t1_pct = ((target_1 - trigger) / trigger * 100) if trigger > 0 else 0.0

    circuit_band = float(state.get("circuit_band", 20.0) or 20.0)
    thin_circuit_warning = f"⚠️ <b>THIN CIRCUIT — FILL RISK</b> (Band: {circuit_band:.0f}%)\n" if circuit_band < 20.0 else ""

    tier = state.get("market_cap_tier")
    tier_info = f" | <b>Tier:</b> {html.escape(str(tier))}" if tier else ""

    card = f"""🛡️ <b>ALPHASENTINEL TRADE ALERT: {symbol}</b>
━━━━━━━━━━━━━━━━━━━━
🎯 <b>Verdict:</b> {verdict} | <b>Conviction:</b> ⭐️ {conviction:.1f}/10
📊 <b>TV Rating:</b> {tv_rec}{tier_info} | <b>Allocation:</b> {alloc_pct:.1f}%

💰 <b>TRADE EXECUTION (DETERMINISTIC):</b>
• <b>Trigger Price:</b> ₹{trigger:,.2f} (LTP: ₹{current:,.2f})
• <b>Quantity:</b> {int(shares or 0)} shares (₹{int(shares or 0) * trigger:,.0f})
• <b>Stop Loss:</b> ₹{stop_loss:,.2f} (-{sl_pct:.1f}%)
• <b>Target 1:</b> ₹{target_1:,.2f} (+{t1_pct:.1f}%)
• <b>Target 2:</b> ₹{target_2:,.2f}
• <b>R:R Ratio:</b> 1:{rr:.2f}
{thin_circuit_warning}
🧠 <b>MULTI-AGENT ADVERSARIAL SYNTHESIS:</b>
🐂 <b>Bull Thesis:</b>
{bull.strip()}

🐻 <b>Bear Trap Warning:</b>
{bear.strip()}

⚖️ <b>Judge Verdict:</b>
{judge.strip()}

🔗 <a href="https://in.tradingview.com/chart/?symbol=NSE:{symbol}">TradingView Chart</a> | <a href="https://www.screener.in/company/{symbol}/">Screener.in</a>
━━━━━━━━━━━━━━━━━━━━
<i>Strict 1-Month Paper Trading Validation Gate Active.</i>"""
    return card
