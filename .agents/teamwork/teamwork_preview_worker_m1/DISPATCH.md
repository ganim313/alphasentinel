## 2026-10-07T12:13:08Z
[Message] timestamp=2026-10-07T12:13:08Z sender=fe9b6c0a-5651-4bc7-812f-d77697cb2e43 priority=MESSAGE_PRIORITY_HIGH content=You are Worker M1 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_worker_m1
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m1
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture and feature inventory:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`

Read the survey handoff report:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_explorer_survey_1\handoff.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Exclusive file write ownership:
- `src/config/strategy.yaml`
- `src/risk/arbiter.py`
- `tests/test_risk_parity_unchoked.py`
- `tests/test_financial_logic_fixes.py` (updating assertion thresholds if needed)
- `tests/test_risk_arbiter_and_agents.py` (updating assertion thresholds if needed)

DO NOT modify any other files in `src/portfolio`, `src/screening`, `src/ingestion`, or `scripts/`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Mission (Requirement R1):
1. Update `src/config/strategy.yaml`:
   - Set `max_pct_stop: 8.0` (replace `max_pct_drop: 5.5`).
   - Increase `max_position_size_pct` from `10.0` to `16.0` to unchoke the 1.0% portfolio risk allocation.
   - Add `max_portfolio_heat_pct: 5.0` (sum of open stop risk across all positions <= 5.0% of core equity).
   - Add `risk_per_trade_pct: 1.0` and `risk_per_trade_neutral_pct: 0.5`.
   - Add `max_open_positions: 6` and `max_positions_per_sector: 2`.
2. Refactor `src/risk/arbiter.py`:
   - In `calculate_deterministic_risk_and_position`:
     - Add `base_low_10d: Optional[float] = None`, `regime_risk_pct: Optional[float] = None`, and `open_positions: Optional[List[Dict[str, Any]]] = None`.
     - Implement structural stop formula:
       `Stop = max(Base_Low_10d - 0.25 * ATR_14, Trigger - 2.5 * ATR_14)` when `base_low_10d` is provided, else `Trigger - 2.5 * ATR_14` (with clean backward-compatible fallback).
     - Reject candidate ONLY if stop distance > 8.0%: `(trigger_price - stop_loss) / trigger_price > 0.08`.
     - Risk per trade: use `regime_risk_pct` if provided (e.g. 1.0% for RISK_ON, 0.5% for NEUTRAL), otherwise default to `risk_per_trade_pct` (1.0%).
     - Sizing: `raw_shares = math.floor(max_trade_risk_rupees / risk_per_share)`.
     - Max position value: allow up to 16.0% (`max_position_size_pct`). Confirm a 1.0% risk trade with a 6.0% stop is correctly allocated without being capped at 0.55%!
     - Portfolio heat ceiling: calculate aggregate open risk across `open_positions` plus current candidate risk. If aggregate open risk > 5.0% of core equity (`max_portfolio_heat_pct`), reject or scale down candidate.
3. Implement `tests/test_risk_parity_unchoked.py`:
   - Test 1: 1.0% risk trade with 6.0% stop correctly allocated ~16% position size without being throttled to 0.55%.
   - Test 2: Structural stop calculation `max(Base_Low_10d - 0.25*ATR, Trigger - 2.5*ATR)`.
   - Test 3: Stop distance > 8.0% rejected; stop distance <= 8.0% approved.
   - Test 4: Portfolio heat ceiling: when existing positions have 4.5% heat, adding a 1.0% trade is blocked/regulated to keep heat <= 5.0%.
4. Run tests:
   `python -m pytest tests/test_risk_arbiter_and_agents.py tests/test_layer4_risk_agents.py tests/test_financial_logic_fixes.py tests/test_risk_parity_unchoked.py -v`
   Ensure ALL tests pass 100%.
5. Write your complete handoff report to `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m1\handoff.md` and send message to Orchestrator.
