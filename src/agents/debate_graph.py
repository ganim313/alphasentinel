"""
Stateful Adversarial Debate Graph using LangGraph (TradingAgents / AlphaSentinel Architecture).
Features:
1. Deterministic Python Risk Arbiter (Primacy over capital)
2. Bull Analyst Node (Upside Catalyst & Momentum Thesis)
3. Bear Trap Hunter Node (Red Flag & Downside Stress Test)
4. Research Judge Node (Impartial Synthesis & Conviction Score)
5. LangGraph Checkpoint Recovery (MemorySaver / Zero Token Waste)
"""

import logging
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.state import AgentState
from src.agents.llm_gateway import execute_llm_completion
from src.risk.arbiter import calculate_deterministic_risk_and_position
from src.config.settings import settings

logger = logging.getLogger(__name__)


def get_latest_strategy_feedback() -> str:
    """Retrieve the most recent STRATEGY_FEEDBACK from agent_memory."""
    try:
        from src.db.session import get_read_connection
        with get_read_connection() as conn:
            row = conn.execute(
                "SELECT content FROM agent_memory WHERE symbol='MARKET_WIDE' "
                "AND pattern_type='STRATEGY_FEEDBACK' ORDER BY memory_date DESC LIMIT 1"
            ).fetchone()
        return row[0] if row and row[0] else ""
    except Exception:
        return ""


def deterministic_risk_node(state: AgentState) -> Dict[str, Any]:
    """
    Evaluates trade using pure Python math and hard risk limits.
    LLMs have ZERO authority over capital allocation.
    """
    symbol = state.get("symbol", "UNKNOWN")
    trigger = state.get("trigger_price", 0.0)
    current = state.get("current_price", trigger)
    atr = state.get("fundamentals", {}).get("atr_14", trigger * 0.05)
    cb = state.get("circuit_band", 20.0)
    weather = state.get("macro_weather", {})
    adtv = state.get("adtv_20d", 0.0)
    sector = state.get("fundamentals", {}).get("sector_name") or state.get("fundamentals", {}).get("sector", "")
    market_cap_tier = state.get("market_cap_tier", "LARGE")
    
    from src.risk.correlation_guard import evaluate_correlation_guard
    corr_passed, corr_reason, corr_metrics = evaluate_correlation_guard(symbol)
    if not corr_passed:
        logger.warning(f"[{symbol}] Deterministic Risk REJECT: {corr_reason}")
        return {
            "risk_verdict": "REJECT",
            "suggested_shares": 0,
            "total_capital_deployed": 0.0,
            "rejection_reason": corr_reason,
            "messages": [AIMessage(content=f"Deterministic Risk Arbiter: REJECT. Reason: {corr_reason}")]
        }

    risk_result = calculate_deterministic_risk_and_position(
        symbol=symbol,
        trigger_price=trigger,
        current_price=current,
        atr_14=atr,
        circuit_band=cb,
        macro_weather=weather,
        adtv_20d=adtv,
        sector=sector,
        market_cap_tier=market_cap_tier,
        portfolio_capital_rupees=settings.ALGO_ALLOCATED_CAPITAL
    )
    
    verdict = risk_result.get("verdict", "REJECT")
    
    return {
        "risk_verdict": verdict,
        "suggested_shares": risk_result.get("suggested_shares", 0),
        "stop_loss_price": risk_result.get("stop_loss_price", 0.0),
        "target_1_price": risk_result.get("target_1_price", 0.0),
        "target_2_price": risk_result.get("target_2_price", 0.0),
        "risk_reward_ratio": risk_result.get("risk_reward_ratio", 0.0),
        "total_capital_deployed": risk_result.get("total_capital_deployed", 0.0),
        "portfolio_allocation_pct": risk_result.get("portfolio_allocation_pct", 0.0),
        "rejection_reason": risk_result.get("rejection_reason", ""),
        "messages": [AIMessage(content=f"Deterministic Risk Arbiter: {verdict}. Reason: {risk_result.get('rejection_reason')}")]
    }


def _resolve_setup_pattern(state: AgentState) -> tuple[str, bool]:
    """Determines canonical pattern label and whether the candidate is a MEAN_REVERSION setup."""
    raw_pattern = state.get("pattern_type")
    if not raw_pattern:
        if state.get("vcp_signal"):
            raw_pattern = "VCP Stage 2"
        elif state.get("mr_signal"):
            raw_pattern = "MEAN_REVERSION"
        else:
            raw_pattern = "VCP Stage 2"
    is_mr = (str(raw_pattern).upper() == "MEAN_REVERSION") or (
        bool(state.get("mr_signal")) and not bool(state.get("vcp_signal")) and not state.get("pattern_type")
    )
    return str(raw_pattern), is_mr


def bull_analyst_node(state: AgentState) -> Dict[str, Any]:
    """
    Bull Analyst: Builds the strongest evidence-based upside case.
    Pattern-aware: Evaluates VCP Stage 2 breakouts or Oversold 200-DMA Structural Uptrend Pullbacks.
    """
    symbol = state.get("symbol", "UNKNOWN")
    tv = state.get("tv_technical_rating", {})
    tv_rec = tv.get("recommendation", "NEUTRAL") if tv else "NEUTRAL"
    funds = state.get("fundamentals", {})
    pattern, is_mr = _resolve_setup_pattern(state)

    if is_mr:
        setup_desc = "Oversold 200-DMA Structural Uptrend Pullback (RSI < 30 above 200-DMA)"
        focus_instr = (
            "Evaluate this candidate as an Oversold 200-DMA Structural Uptrend Pullback (RSI < 30 above 200-DMA) "
            "rather than penalizing it for lacking a VCP Stage 2 volume breakout. "
            "Format your response as exactly 3 concise bullet points focusing on structural 200-DMA uptrend support, "
            "oversold RSI mean-reversion asymmetry, and fundamental earnings resilience."
        )
        sys_msg = (
            "You are a quantitative swing trader identifying high-probability Oversold 200-DMA Structural Uptrend "
            "Pullback (RSI < 30 above 200-DMA) mean-reversion setups."
        )
    else:
        setup_desc = "Confirmed VCP Stage 2" if state.get("vcp_signal") else f"Standard Trend ({pattern})"
        focus_instr = (
            "Format your response as exactly 3 concise bullet points focusing on volume accumulation, "
            "pattern catalyst, and earnings momentum."
        )
        sys_msg = "You are a quantitative swing trader identifying high-probability Stage 2 momentum breakouts."

    prompt = f"""You are the Lead Bull Quantitative Analyst for an Indian Equity Fund.
Analyze {symbol} and construct a crisp 3-bullet upside thesis.

Technical Setup:
- Pattern Type: {pattern} ({setup_desc})
- Trigger Price: ₹{state.get('trigger_price', 0)}
- 20D ADTV: ₹{state.get('adtv_20d', 0):,.0f}
- TradingView Consensus: {tv_rec}

Fundamentals:
- P/E: {funds.get('pe_ratio', 'N/A')}
- ROCE: {funds.get('roce_pct', 'N/A')}%
- QoQ Profit Growth: {funds.get('profit_growth_pct', 'N/A')}%

{focus_instr}"""

    feedback = get_latest_strategy_feedback()
    if feedback:
        prompt += f"\n\nSTRATEGY FEEDBACK (from last weekly review):\n{feedback}"

    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": prompt}
    ]
    
    thesis = execute_llm_completion(messages, model_type="primary")
    return {
        "bull_thesis": thesis,
        "messages": [AIMessage(content=f"BULL THESIS ({symbol}):\n{thesis}")]
    }


def bear_hunter_node(state: AgentState) -> Dict[str, Any]:
    """
    Bear Trap Hunter: Actively hunts for fatal downside flaws.
    Pattern-aware: Stress-tests VCP breakouts or Oversold 200-DMA Structural Uptrend Pullbacks.
    """
    symbol = state.get("symbol", "UNKNOWN")
    weather = state.get("macro_weather", {})
    funds = state.get("fundamentals", {})
    bull_case = state.get("bull_thesis", "N/A")
    pattern, is_mr = _resolve_setup_pattern(state)

    if is_mr:
        pattern_context = "Oversold 200-DMA Structural Uptrend Pullback (RSI < 30 above 200-DMA)"
        bear_instr = (
            "Evaluate this setup as an Oversold 200-DMA Structural Uptrend Pullback (RSI < 30 above 200-DMA) "
            "rather than penalizing it for lacking a VCP Stage 2 volume breakout. "
            "Format your response as exactly 3 concise bullet points outlining specific mean-reversion trap risks "
            "(e.g. structural 200-DMA breakdown / falling-knife risk, fundamental catalyst behind the selloff, "
            "liquidity trap, or macro headwind)."
        )
    else:
        pattern_context = pattern
        bear_instr = (
            "Format your response as exactly 3 concise bullet points outlining specific trap risks "
            "(e.g. liquidity trap, valuation saturation, operator pump risk, macro headwind)."
        )

    prompt = f"""You are the Adversarial Bear Trap Hunter for an Indian Equity Quant Desk.
Your mission is to aggressively stress-test this setup for {symbol} and identify 3 potential red flags or failure modes.

Setup Context:
- Pattern: {pattern} ({pattern_context})
- Current Trigger: ₹{state.get('trigger_price', 0)}
- Circuit Band: {state.get('circuit_band', 20)}%
- Macro Regime: {weather.get('market_regime', 'NEUTRAL')} (US VIX: {weather.get('us_vix', 'N/A')})
- Debt to Equity: {funds.get('debt_to_equity', 'N/A')}
- Promoter Pledge: {funds.get('promoter_pledged_pct', funds.get('promoter_pledge_pct', 0.0))}%

Bull Case to Challenge:
{bull_case}

{bear_instr}"""

    feedback = get_latest_strategy_feedback()
    if feedback:
        prompt += f"\n\nSTRATEGY FEEDBACK (from last weekly review):\n{feedback}"

    messages = [
        {"role": "system", "content": "You are a skeptical quant risk auditor hunting for false setups and liquidity traps in Indian equities."},
        {"role": "user", "content": prompt}
    ]
    
    risks = execute_llm_completion(messages, model_type="primary")
    return {
        "bear_risks": risks,
        "messages": [AIMessage(content=f"BEAR RISK AUDIT ({symbol}):\n{risks}")]
    }


def research_judge_node(state: AgentState) -> Dict[str, Any]:
    """
    Research Judge: Impartially synthesizes the Bull thesis vs Bear critique.
    Assigns a conviction score (1.0 - 10.0) and produces the final executive synthesis.
    """
    symbol = state.get("symbol", "UNKNOWN")
    bull = state.get("bull_thesis", "")
    bear = state.get("bear_risks", "")
    fundamentals = state.get("fundamentals", {})
    trigger = state.get("trigger_price", 0.0)
    stop_loss = state.get("stop_loss_price", 0.0)
    target_1 = state.get("target_1_price", 0.0)
    adtv = state.get("adtv_20d", 0.0)
    circuit_band = state.get("circuit_band", "N/A")
    pattern, is_mr = _resolve_setup_pattern(state)

    if is_mr:
        pattern_guidance = (
            "\nPATTERN EVALUATION GUIDANCE:\n"
            "This setup is a MEAN_REVERSION candidate — an Oversold 200-DMA Structural Uptrend Pullback "
            "(RSI < 30 above 200-DMA). Evaluate it as an Oversold 200-DMA Structural Uptrend Pullback "
            "rather than penalizing it for lacking a VCP Stage 2 volume breakout.\n"
        )
    else:
        pattern_guidance = ""

    prompt = f"""You are the Chief Quantitative Research Judge.
Evaluate the Bull Thesis and Bear Critique for {symbol} impartially against ground-truth quantitative data.

GROUND-TRUTH QUANTITATIVE DATA:
- Pattern: {pattern}
- Trigger Price: ₹{trigger} | Stop Loss: ₹{stop_loss} | Target 1: ₹{target_1}
- 20-Day ADTV: ₹{adtv:,.0f} | Circuit Band: {circuit_band}%
- Profit Growth: {fundamentals.get('profit_growth_pct', 'N/A')}% | Sales Growth: {fundamentals.get('sales_growth_pct', 'N/A')}%
- Debt / Assets: {fundamentals.get('debt_to_assets', 'N/A')} | Promoter Pledge: {fundamentals.get('pledged_pct', 'N/A')}%
{pattern_guidance}
BULL THESIS:
{bull}

BEAR CRITIQUE:
{bear}

Task:
1. Provide a 2-sentence executive synthesis reconciling both perspectives against the ground-truth data.
2. Assign a Conviction Score from 1.0 to 10.0 (where 1.0 = High Trap Probability, 10.0 = Exceptional Asymmetric Opportunity).

Format:
SYNTHESIS: [Your 2-sentence synthesis]
CONVICTION_SCORE: [e.g. 7.5]"""

    messages = [
        {"role": "system", "content": "You are an objective research judge weighing quantitative evidence."},
        {"role": "user", "content": prompt}
    ]
    
    raw_judge = execute_llm_completion(messages, model_type="primary")
    
    import re
    # Extract conviction score safely
    conviction = 5.0 # Neutral fallback if score cannot be parsed
    try:
        match = re.search(r"(?:CONVICTION[_\s]*SCORE|CONVICTION)\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)", raw_judge, re.IGNORECASE)
        if match:
            conviction = float(match.group(1))
            conviction = max(1.0, min(10.0, conviction))
        else:
            logger.warning(f"Could not extract CONVICTION_SCORE from Judge synthesis for {symbol}. Defaulting to neutral 5.0.")
    except Exception as e:
        logger.warning(f"Error parsing conviction score for {symbol}: {e}. Defaulting to 5.0.")
        
    # Record to agent_memory for continuous learning loop
    try:
        from src.db.queue_writer import db_write
        import json
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        today_date = datetime.now(ZoneInfo('Asia/Kolkata')).date()
        memory_content = json.dumps({
            "bull_thesis": state.get("bull_thesis", ""),
            "bear_risks": state.get("bear_risks", ""),
            "judge_synthesis": raw_judge,
            "target_1": state.get("target_1_price", 0.0),
            "target_2": state.get("target_2_price", 0.0),
            "stop_loss": state.get("stop_loss_price", 0.0),
            "suggested_shares": state.get("suggested_shares", 0),
        })
        
        db_write("""
            INSERT OR REPLACE INTO agent_memory (
                symbol, memory_date, pattern_type, previous_verdict,
                rejection_reason, bear_flags_noted, kronos_score,
                conviction_score, content, outcome_label, triple_barrier_label, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, CURRENT_TIMESTAMP);
        """, (
            symbol,
            today_date,
            state.get("pattern_type") or pattern,
            state.get("risk_verdict", "APPROVE"),
            state.get("rejection_reason", ""),
            state.get("bear_risks", ""),
            conviction,
            conviction,
            memory_content,
        ))
    except Exception as mem_err:
        logger.warning(f"Could not persist agent_memory record for {symbol}: {mem_err}")

    return {
        "judge_synthesis": raw_judge,
        "conviction_score": conviction,
        "messages": [AIMessage(content=f"JUDGE SYNTHESIS ({symbol}) [Score: {conviction}/10]:\n{raw_judge}")]
    }


def conviction_gate_node(state: AgentState) -> Dict[str, Any]:
    """
    Conviction Score Gate: Hard minimum threshold enforced AFTER research judge.
    Reads min_conviction_score from src/config/strategy.yaml (default: 6.5).
    Rejects the trade if the conviction score falls below the configured threshold.
    LLM cost has already been spent; this node prevents low-confidence orders from leaking
    through to order execution.
    """
    symbol = state.get("symbol", "UNKNOWN")
    score = state.get("conviction_score", 5.0)

    # Load threshold from strategy.yaml; fall back to 6.5 if unavailable
    threshold = 6.5
    try:
        import yaml
        from pathlib import Path
        _config_path = Path(__file__).resolve().parent.parent / "config" / "strategy.yaml"
        with open(_config_path, "r", encoding="utf-8") as _f:
            _cfg = yaml.safe_load(_f)
        threshold = float(_cfg.get("risk", {}).get("min_conviction_score", 6.5))
    except Exception as _e:
        logger.warning(f"[{symbol}] Could not load min_conviction_score from strategy.yaml: {_e}. Using default 6.5.")

    if score < threshold:
        reason = f"Conviction score {score}/10 below minimum threshold {threshold}/10"
        logger.warning(f"[{symbol}] Conviction Gate REJECT: {reason}")
        return {
            "risk_verdict": "REJECT",
            "rejection_reason": reason,
            "messages": [AIMessage(content=f"CONVICTION GATE ({symbol}): REJECT. {reason}")]
        }

    logger.info(f"[{symbol}] Conviction Gate PASS: score {score}/10 >= threshold {threshold}/10")
    return {
        "messages": [AIMessage(content=f"CONVICTION GATE ({symbol}): PASS. Score {score}/10 >= {threshold}/10")]
    }


def risk_router(state: AgentState) -> str:
    """
    Gatekeeper routing: Only proceed to multi-agent LLM debate if deterministic risk passes.
    Saves 100% of LLM API costs on mathematically invalid setups.
    """
    verdict = state.get("risk_verdict", "REJECT")
    if verdict in ["APPROVE", "APPROVE_WITH_WARNING", "REDUCE_SIZE"]:
        return "bull_analyst"
    return END


def build_debate_graph(checkpointer: Optional[MemorySaver] = None):
    """
    Constructs and compiles the full LangGraph debate pipeline.

    Graph flow:
        deterministic_risk → (APPROVE) → bull_analyst → bear_hunter → research_judge → conviction_gate → END
        deterministic_risk → (REJECT)  → END
    """
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("deterministic_risk", deterministic_risk_node)
    workflow.add_node("bull_analyst", bull_analyst_node)
    workflow.add_node("bear_hunter", bear_hunter_node)
    workflow.add_node("research_judge", research_judge_node)
    workflow.add_node("conviction_gate", conviction_gate_node)
    
    # Set Entry Point
    workflow.set_entry_point("deterministic_risk")
    
    # Conditional Routing from Deterministic Risk
    workflow.add_conditional_edges(
        "deterministic_risk",
        risk_router,
        {
            "bull_analyst": "bull_analyst",
            END: END
        }
    )
    
    # Sequential Adversarial Flow: Bull -> Bear -> Judge -> Conviction Gate -> End
    workflow.add_edge("bull_analyst", "bear_hunter")
    workflow.add_edge("bear_hunter", "research_judge")
    workflow.add_edge("research_judge", "conviction_gate")
    workflow.add_edge("conviction_gate", END)
    
    # Compile with Checkpointer (Default to MemorySaver if none provided)
    active_checkpointer = checkpointer or MemorySaver()
    app = workflow.compile(checkpointer=active_checkpointer)
    return app
