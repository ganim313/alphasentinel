# Worker M1 Handoff Report: Volatility-Adjusted Risk Parity Math & Structural Stops (Requirement R1)

**Agent**: `teamwork_preview_worker_m1`  
**Parent Orchestrator**: `fe9b6c0a-5651-4bc7-812f-d77697cb2e43`  
**Working Directory**: `c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_worker_m1`  
**Milestone**: Milestone M1 (Requirement R1)  
**Status**: COMPLETE  

---

## 1. Observation

### 1.1 Initial State Observations
1. **`src/config/strategy.yaml` (Lines 20–39)**:
   - Contained: `max_position_size_pct: 10.0`, `stop_loss: atr_multiplier: 1.8, max_pct_drop: 5.5`, and `sector_exposure: max_open_positions: 3, max_portfolio_pct: 25.0`.
   - Keys `max_pct_stop: 8.0`, `max_portfolio_heat_pct: 5.0`, `risk_per_trade_pct: 1.0`, `risk_per_trade_neutral_pct: 0.5`, `max_open_positions: 6`, and `max_positions_per_sector: 2` were completely absent.
2. **`src/risk/arbiter.py` (Signature & Lines 143–192)**:
   - `calculate_deterministic_risk_and_position` lacked parameters `base_low_10d`, `regime_risk_pct`, and `open_positions`.
   - The stop loss calculation used `atr_stop = trigger_price - 1.8 * atr_14` and rejected any candidate where `atr_stop < trigger_price * (1.0 - 0.055)`. Candidates with stop distances between 5.5% and 8.0% were falsely rejected as "too volatile".
   - Sizing logic capped total position value at 10.0% (`max_pos_pct = 10.0%`). At a 5.5% max drop, this throttled total trade risk to $10\% \times 5.5\% = 0.55\%$ of portfolio equity, choking institutional 1.0% risk parity sizing.
   - Aggregate portfolio heat (sum of open stop risk across open positions) was completely unmonitored.
   - Return dictionary omitted interface contract fields specified in `PROJECT.md` (`shares_to_buy`, `position_value_rupees`, `risk_rupees`, `risk_per_trade_pct`, `stop_distance_pct`, `portfolio_heat_pct_after`).
3. **Existing Test Suite Baseline**:
   - Running `python -m pytest tests/test_risk_arbiter_and_agents.py tests/test_layer4_risk_agents.py tests/test_financial_logic_fixes.py -v`:
     - 11 passed in 8.51s.
   - `tests/test_risk_arbiter_and_agents.py:26` hardcoded `assert result["stop_loss_price"] == 94.6 # 100 - (1.8 * 3) = 94.6` and `assert result["portfolio_allocation_pct"] <= 12.0`.
   - `tests/test_financial_logic_fixes.py:33` hardcoded `assert res["portfolio_allocation_pct"] <= 12.0`.

### 1.2 Implementation Observations
1. **Config Update**:
   - `src/config/strategy.yaml` was updated with:
     ```yaml
     risk:
       max_position_size_pct: 16.0
       max_portfolio_heat_pct: 5.0
       risk_per_trade_pct: 1.0
       risk_per_trade_neutral_pct: 0.5
       max_open_positions: 6
       max_positions_per_sector: 2
       ...
       stop_loss:
         atr_multiplier: 2.5
         max_pct_stop: 8.0
     ```
2. **Arbiter Refactoring (`src/risk/arbiter.py`)**:
   - Extended signature of `calculate_deterministic_risk_and_position`:
     ```python
     def calculate_deterministic_risk_and_position(
         symbol: str,
         trigger_price: float,
         current_price: Optional[float] = None,
         atr_14: float = 0.0,
         base_low_10d: Optional[float] = None,
         regime_risk_pct: Optional[float] = None,
         circuit_band: float = 20.0,
         macro_weather: Optional[Dict[str, Any]] = None,
         portfolio_capital_rupees: float = 10_00_000.0,
         adtv_20d: float = 0.0,
         sector: str = "",
         market_cap_tier: str = "LARGE",
         open_positions: Optional[List[Dict[str, Any]]] = None
     ) -> Dict[str, Any]:
     ```
   - Implemented structural stop calculation:
     `Stop = max(Base_Low_10d - 0.25 * ATR_14, Trigger - 2.5 * ATR_14)` when `base_low_10d` is provided, else fallback `Trigger - 2.5 * ATR_14`.
   - Enforced rejection gate strictly when `(trigger_price - stop_loss) / trigger_price > 0.08` (8.0%). Stops $\le 8.0\%$ are approved.
   - Sizing: `risk_per_trade_pct` defaults to `1.0%` (or `regime_risk_pct` if provided; returns `REJECT` if $\le 0.0\%$ for `RISK_OFF`). Sized via `raw_shares = math.floor(max_trade_risk_rupees / risk_per_share)`.
   - Max position value: increased from 10.0% to 16.0% (`max_position_size_pct`). For a 1.0% risk trade with a 6.0% stop, exactly 1600 shares / ₹1,60,000 (16.0% allocation, ₹9,600 rupee risk) are allocated.
   - Portfolio heat ceiling: aggregate open risk across `open_positions` plus current candidate risk is evaluated against `max_portfolio_heat_pct` (5.0%). If existing open risk is $\ge 5.0\%$, trade is REJECTED. If candidate risk exceeds remaining heat budget, candidate shares are regulated/scaled down to preserve $\le 5.0\%$ aggregate heat.
   - Added all interface contract fields from `PROJECT.md` alongside legacy keys.
3. **Test Suite Addition**:
   - Created `tests/test_risk_parity_unchoked.py` containing 6 unit tests covering all R1 acceptance criteria.
   - Updated threshold assertions in `tests/test_risk_arbiter_and_agents.py` (stop loss 92.5, allocation $\le 16.0\%$) and `tests/test_financial_logic_fixes.py` (allocation $\le 16.0\%$).
4. **Execution Results**:
   - Executing: `python -m pytest tests/test_risk_arbiter_and_agents.py tests/test_layer4_risk_agents.py tests/test_financial_logic_fixes.py tests/test_risk_parity_unchoked.py -v`
   - Output: `17 passed in 42.86s` (100% pass rate).

---

## 2. Logic Chain

1. **Unchoking Sizing Math**:
   - *Premise*: Sizing formula is $\text{shares} = \lfloor \frac{\text{Equity} \times \text{Risk \%}}{\text{Trigger} - \text{Stop}} \rfloor$. Position value is capped by $\text{max\_position\_size\_pct} \times \text{Equity}$.
   - *Issue*: With legacy `max_position_size_pct: 10.0%` and `max_pct_drop: 5.5%`, any trade with a 6.0% stop was either rejected or capped at $10\% \times 5.5\% = 0.55\%$ risk.
   - *Resolution*: By setting `max_position_size_pct: 16.0%` and `max_pct_stop: 8.0%`, a 1.0% risk trade with a 6.0% stop ($₹100 \rightarrow ₹94$) binds at $\frac{1.0\%}{6.0\%} = 16.66\%$ raw shares ($1666$ shares). Capped at $16.0\%$ ($1600$ shares), the resulting position value is ₹1,60,000 (16.0% of ₹10L portfolio), and actual dollar risk taken is ₹9,600 (0.96% of portfolio), unchoking the 1.0% risk budget cleanly.

2. **Structural Stop Formula**:
   - *Formula*: $\text{Stop} = \max(\text{Base\_Low}_{10\text{d}} - 0.25\times\text{ATR}_{14}, \text{Trigger} - 2.5\times\text{ATR}_{14})$.
   - If `base_low_10d` is provided, the stop anchors to the cheat pivot swing low buffered by $0.25\times\text{ATR}$, protected by the $2.5\times\text{ATR}$ volatility floor.
   - If `base_low_10d` is None, it defaults cleanly to $\text{Trigger} - 2.5\times\text{ATR}_{14}$.
   - The rejection tripwire only triggers when $\frac{\text{Trigger} - \text{Stop}}{\text{Trigger}} > 0.08$.

3. **Portfolio Heat Ceiling Guard**:
   - *Requirement*: Global aggregate open stop risk $\le 5.0\%$ of core equity at all times.
   - When a new candidate is evaluated, existing open rupee risk is summed across all open positions.
   - Available risk budget = $5.0\% \times \text{Core Equity} - \text{Existing Open Risk}$.
   - If available budget $\le 0$, the candidate is REJECTED.
   - If desired candidate risk exceeds available budget, shares are regulated to $\lfloor \frac{\text{Available Budget}}{\text{Risk Per Share}} \rfloor$, ensuring aggregate heat post-entry $\le 5.0\%$.

4. **Zero Lookahead & Real Computation**:
   - No mock facades or hardcoded return values were used. All mathematical formulas operate directly on real inputs, DuckDB state, and live core equity.

---

## 3. Caveats

1. **Floating Point Rounding in CPPI/Vol Scalars**:
   - CPPI calculation in `src/risk/cppi.py` returns `0.9999999999999991` when `core_equity == lifetime_hwm` due to IEEE-754 precision in `(1.0 - 0.94)`. A numerical tolerance check (`< 0.9999`) was added in `arbiter.py` so that unpenalized positions are not truncated by 1 share by `math.floor`.
2. **Other Test Suites**:
   - `tests/test_phase2_data_pipeline.py:445` contains an old test assertion `assert res["suggested_shares"] <= 500` written when `max_position_size_pct` was 10%. With the unchoked 16% cap, that test returns 800 shares. Since `test_phase2_data_pipeline.py` is outside M1's write ownership scope, it was left unmodified. Downstream integration workers can update that assertion threshold when consolidating.

---

## 4. Conclusion

1. Requirement R1 is **fully implemented and verified**:
   - `src/config/strategy.yaml` updated with `max_pct_stop: 8.0`, `max_position_size_pct: 16.0`, `max_portfolio_heat_pct: 5.0`, `risk_per_trade_pct: 1.0`, `risk_per_trade_neutral_pct: 0.5`, `max_open_positions: 6`, `max_positions_per_sector: 2`, and `atr_multiplier: 2.5`.
   - `src/risk/arbiter.py` refactored with structural stop formula, 8.0% max stop distance rejection, 1.0% risk parity sizing unchoked to 16.0% position value, and 5.0% aggregate portfolio heat ceiling regulation and blocking.
   - All contract keys (`shares_to_buy`, `position_value_rupees`, `risk_rupees`, `risk_per_trade_pct`, `stop_distance_pct`, `portfolio_heat_pct_after`) and legacy keys are fully populated.
   - `tests/test_risk_parity_unchoked.py` created and passing 100%.
   - All 17 unit tests in the targeted test suites pass with zero failures.

---

## 5. Verification Method

To independently verify Worker M1 deliverables:

1. **Run Targeted Pytest Suite**:
   ```powershell
   python -m pytest tests/test_risk_arbiter_and_agents.py tests/test_layer4_risk_agents.py tests/test_financial_logic_fixes.py tests/test_risk_parity_unchoked.py -v
   ```
   *Expected Result*: 17 passed in under 45 seconds.

2. **Verify Configuration Values**:
   ```powershell
   python -c "import yaml; cfg = yaml.safe_load(open('src/config/strategy.yaml'))['risk']; print('max_pos:', cfg['max_position_size_pct'], 'max_stop:', cfg['stop_loss']['max_pct_stop'], 'max_heat:', cfg['max_portfolio_heat_pct'])"
   ```
   *Expected Result*: `max_pos: 16.0 max_stop: 8.0 max_heat: 5.0`

3. **Verify Sizing Unchoking (1.0% risk on 6.0% stop)**:
   ```powershell
   python -c "from src.risk.arbiter import calculate_deterministic_risk_and_position; res = calculate_deterministic_risk_and_position('TEST', 100.0, 100.0, 2.4, None, 1.0, 20.0, {'target_cash_exposure_pct': 0.0}, 1000000.0, 50000000.0, '', 'LARGE', []); print('Shares:', res['suggested_shares'], 'Alloc%:', res['portfolio_allocation_pct'], 'RiskRupees:', res['risk_rupees'])"
   ```
   *Expected Result*: `Shares: 1600 Alloc%: 16.0 RiskRupees: 9600.0`
