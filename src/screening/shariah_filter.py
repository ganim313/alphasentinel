"""
Shariah Compliance Gate Module.
Screens out non-compliant business activities and non-compliant financial structures
using strict quantitative ratios according to the Fatwa of Justice Mufti Muhammad Taqi Usmani
and the authoritative benchmark: 'Copy of halal stock 2.0.xlsx'.
"""

import re
from typing import Dict, Any, Tuple

# Prohibited industry keywords based on strict Shariah mandate
PROHIBITED_SECTORS = [
    "bank", "banking", "finance", "nbfc", "insurance", "bfsi", "broker",
    "alcohol", "distillery", "brewery", "wine", "beer", "liquor",
    "tobacco", "cigarette", "cigar",
    "casino", "gambling", "betting", 
    "hotel", "resort", "entertainment", "media", "television", "music", "disco", "club",
    "porn", "advertising", "advertisement",
    "pork", "cloning", "tattoo", "photography", "videography"
]


def check_shariah_compliance(fundamentals: Dict[str, Any], sector_name: str = "") -> Tuple[bool, str]:
    """
    Evaluates Shariah compliance based on business sector and 5 strict quantitative conditions
    per the Fatwa of Justice Mufti Muhammad Taqi Usmani:
    1. Primary business activity must be permissible (Halal).
    2. Debt / Total Assets <= 33.0%.
    3. Impure Income / Total Sales <= 5.0%.
    4. Illiquid Assets / Total Assets >= 20.0%.
    5. Net Liquid Assets <= Market Capitalization (F78 <= F80).
    """
    # 1. Sector & Qualitative Screen (Regex word boundary with plural support)
    sector_lower = sector_name.lower()
    for prohibited in PROHIBITED_SECTORS:
        if prohibited.endswith("y"):
            pattern = rf'\b{prohibited[:-1]}(?:y|ies)\b'
        else:
            pattern = rf'\b{prohibited}(?:s|es)?\b'
        if re.search(pattern, sector_lower):
            return False, f"NON_COMPLIANT_SECTOR_{prohibited.upper()}"

    # 2. Quantitative Financial Ratio Screens (Fail closed on missing or non-positive asset data)
    total_assets = fundamentals.get("total_assets")
    if total_assets is None or total_assets <= 0:
        return False, "INVALID_OR_ZERO_TOTAL_ASSETS"

    has_debt_data = ("debt_to_assets" in fundamentals and fundamentals["debt_to_assets"] is not None) or ("borrowings" in fundamentals and fundamentals["borrowings"] is not None)
    has_income_data = ("interest_income_ratio" in fundamentals and fundamentals["interest_income_ratio"] is not None) or ("sales" in fundamentals and fundamentals["sales"] is not None)

    if not (has_debt_data and has_income_data):
        return False, "MISSING_FUNDAMENTAL_DATA"

    # Rule 2: Debt / Total Assets <= 33%
    debt_to_assets = fundamentals.get("debt_to_assets")
    if debt_to_assets is None:
        borrowings = fundamentals.get("borrowings")
        total_assets = fundamentals.get("total_assets")
        if borrowings is not None and total_assets and total_assets > 0:
            debt_to_assets = borrowings / total_assets

    if debt_to_assets is None or debt_to_assets > 0.33:
        pct_str = f"{debt_to_assets:.2%}" if debt_to_assets is not None else "N/A"
        return False, f"EXCESSIVE_DEBT_ASSETS_{pct_str}"

    # Rule 3: Interest or Non-Compliant Income / Total Sales <= 5%
    if "sales" in fundamentals and (fundamentals["sales"] is None or fundamentals["sales"] <= 0):
        return False, "INVALID_OR_ZERO_SALES_FOR_INCOME_CHECK"
        
    interest_income_ratio = fundamentals.get("interest_income_ratio")
    if interest_income_ratio is None:
        sales = fundamentals.get("sales")
        impure_income = fundamentals.get("impure_income") or fundamentals.get("interest_income")
        if sales and sales > 0 and impure_income is not None:
            interest_income_ratio = impure_income / sales
        else:
            return False, "MISSING_INCOME_RATIO_DATA"

    if interest_income_ratio is None or interest_income_ratio > 0.05:
        pct_str = f"{interest_income_ratio:.2%}" if interest_income_ratio is not None else "N/A"
        return False, f"EXCESSIVE_INTEREST_INCOME_{pct_str}"

    # Rule 4: Illiquid Assets / Total Assets >= 20%
    illiquid_ratio = fundamentals.get("illiquid_ratio")
    if illiquid_ratio is None:
        total_assets = fundamentals.get("total_assets")
        if total_assets and total_assets > 0:
            illiquid_sum = (
                (fundamentals.get("fixed_assets") or 0.0) +
                (fundamentals.get("cwip") or 0.0) +
                (fundamentals.get("inventories") or 0.0) +
                (fundamentals.get("intangible_assets") or 0.0)
            )
            illiquid_ratio = illiquid_sum / total_assets

    if illiquid_ratio is None or illiquid_ratio < 0.20:
        pct_str = f"{illiquid_ratio:.2%}" if illiquid_ratio is not None else "N/A"
        return False, f"INSUFFICIENT_ILLIQUID_ASSETS_{pct_str}"

    # Rule 4B: AAOIFI Standard 21 Receivables Screen (Accounts Receivables / Total Assets <= 49%)
    receivables = fundamentals.get("accounts_receivable") or fundamentals.get("trade_receivables")
    total_assets = fundamentals.get("total_assets")
    if receivables is not None and total_assets and total_assets > 0:
        rec_ratio = receivables / total_assets
        if rec_ratio > 0.49:
            return False, f"EXCESSIVE_RECEIVABLES_{rec_ratio:.2%}"

    # Rule 5: Net Liquid Assets <= Market Capitalization (Mufti Taqi Usmani 5th Condition)
    net_liquid_assets = fundamentals.get("net_liquid_assets_crores")
    market_cap = fundamentals.get("market_cap_crores")

    if net_liquid_assets is None or market_cap is None:
        return False, "MISSING_NET_LIQUID_OR_MARKET_CAP_DATA"
        
    if market_cap <= 0:
        return False, "INVALID_OR_ZERO_MARKET_CAP"
        
    if net_liquid_assets > market_cap:
        return False, f"EXCESSIVE_NET_LIQUID_ASSETS (Net Liquid ₹{net_liquid_assets:.2f} Cr > Market Cap ₹{market_cap:.2f} Cr)"

    return True, "PASSED_SHARIAH_GATE"
