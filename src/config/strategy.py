"""
Strategy Configuration Loader.
Loads strategy.yaml and exposes configuration dictionaries for screening, risk, and alpha.
"""

import os
from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "strategy.yaml"

if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        strategy_config = yaml.safe_load(f) or {}
else:
    strategy_config = {}

SCREENING_CONFIG = strategy_config.get("screening", {})
MINERVINI_CONFIG = SCREENING_CONFIG.get("minervini", {})
VCP_CONFIG = SCREENING_CONFIG.get("vcp", {})
QUANT_ALPHA_CONFIG = SCREENING_CONFIG.get("quantitative_alpha", {})
RISK_CONFIG = strategy_config.get("risk", {})
