# Progress - Worker M1 (Risk Parity Unchoking & Structural Stops)

Last visited: 2026-10-07T12:35:00Z

## Status: COMPLETE

### Completed Steps
- [x] Initialized DISPATCH.md and BRIEFING.md
- [x] Dumped domain skill copy to workspace and reviewed methodologies
- [x] Read ORIGINAL_REQUEST.md, PROJECT.md, and survey handoff.md
- [x] Inspected baseline `src/config/strategy.yaml`, `src/risk/arbiter.py`, and existing test suites
- [x] Executed baseline tests (11 passed)
- [x] Updated `src/config/strategy.yaml` with `max_pct_stop: 8.0`, `max_position_size_pct: 16.0`, `max_portfolio_heat_pct: 5.0`, `risk_per_trade_pct: 1.0`, `risk_per_trade_neutral_pct: 0.5`, `max_open_positions: 6`, `max_positions_per_sector: 2`, `atr_multiplier: 2.5`
- [x] Refactored `src/risk/arbiter.py`:
  - Added `base_low_10d: Optional[float] = None`, `regime_risk_pct: Optional[float] = None`, and `open_positions: Optional[List[Dict[str, Any]]] = None` to `calculate_deterministic_risk_and_position`
  - Implemented structural stop formula: `Stop = max(Base_Low_10d - 0.25 * ATR_14, Trigger - 2.5 * ATR_14)` with fallback `Trigger - 2.5 * ATR_14`
  - Enforced max stop loss distance rejection threshold: strictly rejects only when `(trigger_price - stop_loss) / trigger_price > 0.08`
  - Enabled regime risk per trade calculation (1.0% default / RISK_ON, 0.5% NEUTRAL, 0.0% RISK_OFF rejection)
  - Unchoked sizing up to 16.0% position value (`max_position_size_pct`)
  - Implemented aggregate portfolio heat ceiling (<= 5.0% of core equity) across open positions + candidate risk, with regulation and blocking
  - Added all interface contract fields (`shares_to_buy`, `position_value_rupees`, `risk_rupees`, `risk_per_trade_pct`, `stop_distance_pct`, `portfolio_heat_pct_after`) alongside full backward compatibility keys
- [x] Updated assertion thresholds in `tests/test_risk_arbiter_and_agents.py` and `tests/test_financial_logic_fixes.py`
- [x] Created comprehensive test suite `tests/test_risk_parity_unchoked.py` with 6 detailed test cases covering all R1 criteria
- [x] Ran test suite: 17 of 17 tests passed (100% pass rate)
- [x] Handed off deliverables and prepared report
