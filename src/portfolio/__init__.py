"""
Portfolio State Management Module.
Authoritative source for portfolio equity, drawdown metrics, and Sharpe ratios.
"""

from src.portfolio.state import get_portfolio_state
from src.portfolio.fyers_guardian import (
    SettlementStatus,
    ExitPriorityRule,
    reconcile_and_evaluate_holdings,
    evaluate_settlement,
    evaluate_exit_hierarchy,
    evaluate_exit_rule,
    count_trading_days,
    generate_gtt_oco_payload
)

__all__ = [
    "get_portfolio_state",
    "SettlementStatus",
    "ExitPriorityRule",
    "reconcile_and_evaluate_holdings",
    "evaluate_settlement",
    "evaluate_exit_hierarchy",
    "evaluate_exit_rule",
    "count_trading_days",
    "generate_gtt_oco_payload",
]
