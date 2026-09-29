"""
Manual Overlord Export Module (Web UI Bridge).
Generates copy-paste markdown blocks and downloadable .txt payloads
for querying free web chat interfaces (Claude 3.5 Sonnet / ChatGPT-4o).
"""

import json
from typing import Dict, Any


def generate_web_ui_payload(candidate_state: Dict[str, Any]) -> str:
    """
    Generates a dense markdown block formatted for direct copy-paste into Web UI LLMs.
    """
    symbol = candidate_state.get("symbol", "UNKNOWN")
    fundamentals = candidate_state.get("fundamentals", {})
    
    payload_dict = {
        "symbol": symbol,
        "trigger_price": candidate_state.get('trigger_price'),
        "current_price": candidate_state.get('current_price'),
        "adtv_20d_rupees": candidate_state.get('adtv_20d'),
        "circuit_band_pct": candidate_state.get('circuit_band'),
        "fundamentals": {
            "pe_ratio": fundamentals.get('pe_ratio'),
            "sector_pe": fundamentals.get('sector_pe'),
            "debt_to_equity": fundamentals.get('debt_to_equity'),
            "roce_pct": fundamentals.get('roce_pct'),
            "promoter_holding_pct": fundamentals.get('promoter_holding_pct'),
            "promoter_pledged_pct": fundamentals.get('promoter_pledged_pct')
        },
        "algorithmic_bull_thesis": candidate_state.get('bull_thesis', ''),
        "algorithmic_bear_risks": candidate_state.get('bear_risks', ''),
        "deterministic_risk_calc": {
            "suggested_shares": candidate_state.get('suggested_shares', 0),
            "stop_loss": candidate_state.get('stop_loss_price', 0),
            "target_1": candidate_state.get('target_1_price', 0),
            "target_2": candidate_state.get('target_2_price', 0),
            "allocation_pct": candidate_state.get('portfolio_allocation_pct', 0)
        }
    }
    
    payload_json = json.dumps(payload_dict, indent=2, default=str)
    
    payload = f"""### ALPHASENTINEL DEEP-DIVE PAYLOAD: {symbol}

```json
{payload_json}
```

**Instruction for Web UI Model:**
Act as an elite Hedge Fund Portfolio Manager specializing in Indian small/micro-cap breakouts.
Analyze the JSON metrics above. Critique the algorithmic bull thesis against the bear risks. 
Give a decisive Final Verdict: **CONFIRM TRADE**, **REDUCE POSITION BY 50%**, or **VETO/ABORT**.
"""
    return payload
