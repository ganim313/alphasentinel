"""
LangGraph Multi-Agent State Schema.
Type-safe TypedDict representing the immutable context passed between nodes.
"""

from typing import TypedDict, List, Dict, Any, Optional, Sequence, Annotated
import operator
from langchain_core.messages import BaseMessage

class AgentState(TypedDict, total=False):
    symbol: str
    scan_date: str
    pattern_type: Optional[str]
    current_price: float
    trigger_price: float
    adtv_20d: float
    circuit_band: float
    market_cap_tier: Optional[str]
    portfolio_capital_rupees: Optional[float]
    
    # Financials & Ingestion
    fundamentals: Dict[str, Any]
    technicals: Dict[str, Any]
    macro_weather: Dict[str, Any]
    historical_memory: List[Dict[str, Any]]
    tv_technical_rating: Optional[Dict[str, Any]]
    
    # LangGraph state fields
    messages: Annotated[Sequence[BaseMessage], operator.add]
    macro_context: str
    current_verdict: Optional[str]
    
    # Multi-Model Consensus Signals
    vcp_signal: bool
    ml_probability: float
    mr_signal: bool
    shield_passed: bool
    
    # Agent Debate Outputs
    macro_regime_score: float
    bull_thesis: Optional[str]
    bear_risks: Optional[str]
    judge_synthesis: Optional[str]
    conviction_score: float
    clarification_count: int
    
    # Deterministic Risk Manager Verdict (Pure Python)
    risk_verdict: Optional[str]        # APPROVE, REJECT, REDUCE_SIZE
    suggested_shares: int
    stop_loss_price: float
    target_1_price: float
    target_2_price: float
    risk_reward_ratio: float
    total_capital_deployed: float
    portfolio_allocation_pct: float
    rejection_reason: Optional[str]
    
    # Execution & Human Review
    telegram_card_markdown: Optional[str]
    manual_review_payload: Optional[str]

