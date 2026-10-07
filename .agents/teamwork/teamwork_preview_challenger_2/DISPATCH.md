## 2026-10-07T13:23:20Z

You are Challenger 2 for the Master Implementation of AlphaSentinel Shariah Indian CNC Swing Trading System.

Your identity: teamwork_preview_challenger_2
Your working directory: c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_challenger_2
Your parent: Orchestrator (fe9b6c0a-5651-4bc7-812f-d77697cb2e43)

You MUST read the authoritative user request first:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\ORIGINAL_REQUEST.md`

You MUST read the project architecture and feature inventory:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\PROJECT.md`
And the E2E readiness report:
`c:\Users\Md Ganim\Desktop\trading agents\TEST_READY.md`

Domain skill reference:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\skills\domain-quant-trading-finance\SKILL.md`

Mission:
Adversarially challenge and empirically stress-test the screening, regime, and signal infrastructure:
1. Market Regime & Bear Bypass:
   - Inject extreme market crash scenarios, verify screener produces zero buys.
   - Challenge universe breadth score under synthetic universe distributions.
2. Beta-Stripped Residual Momentum:
   - Benchmark matrix OLS calculation timing across 400 stocks x 60 bars (must be <100ms).
   - Verify banking index rally does NOT artificially depress non-banking Shariah momentum.
3. Real-World Production Workloads:
   - Run the full Tier 4 real-world workload simulation and master E2E test runner.

Execute verification:
```powershell
python tests/test_e2e_suite.py --tier 4
python tests/test_e2e_suite.py
```

Document your findings and record your explicit verdict (`APPROVE` or `REQUEST_CHANGES`) in:
`c:\Users\Md Ganim\Desktop\trading agents\.agents\teamwork\teamwork_preview_challenger_2\handoff.md`
Send your completion message with the verdict to the Orchestrator.
