"""
Shariah Compliance Gate Module.
Screens out non-compliant business activities and non-compliant financial structures
using strict quantitative ratios according to the Fatwa of Justice Mufti Muhammad Taqi Usmani
and the authoritative benchmark: 'Copy of halal stock 2.0.xlsx'.
"""

import re
from typing import Dict, Any, Tuple

# Prohibited industry keywords based on strict Shariah mandate and 'Copy of halal stock 2.0.xlsx'
PROHIBITED_SECTORS = [
    "bank", "banking", "finance", "financial", "fincorp", "finserv", "financier",
    "nbfc", "insurance", "assurance", "reinsurance", "bfsi",
    "broker", "broking", "stockbroking", "lending", "microfinance", "wealth", "leasing", "securities", "mutual fund",
    "alcohol", "distillery", "brewery", "wine", "winery", "vineyard", "beer", "liquor", "spirits", "malt", "molasses", "sugar",
    "tobacco", "cigarette", "cigar",
    "casino", "gambling", "betting",
    "hotel", "resort", "hospitality", "entertainment", "cinema", "multiplex",
    "media", "broadcasting", "television", "music", "disco", "club",
    "porn", "advertising", "advertisement", "advertisment",
    "pork", "cloning", "tattoo", "photography", "videography", "photo", "video"
]

# Explicit prohibited symbols from 'Copy of halal stock 2.0.xlsx' (list, Sheet19 sugar-mill molasses distilleries, nse stock)
PROHIBITED_SYMBOLS = {
    # Excel 'list' sheet explicit exclusions
    "AGI", "ATULAUTO", "PRAJIND", "GULPOLY",
    # Sugar mills operating commercial molasses alcohol distilleries (Sheet19 / NSE sugar distilleries)
    "BALRAMCHIN", "TRIVENI", "DWARKESH", "DALMIASUG", "RENUKA", "BAJAJHIND",
    "EIDPARRY", "ANDHRSUGAR", "DHAMPURSUG", "UTTAMSUGAR", "AVADHSUGAR", "MAGADHSUGAR", "PICCADIL", "INDIAGLYCO",
    # Alcohol, Breweries, Distilleries & Wineries
    "UBL", "UNITDSPR", "RADICO", "SULA", "GLOBUSSPR", "ASALCBR", "TI", "SOMDIST", "GMBREW",
    # Tobacco & Cigarettes
    "ITC", "VSTIND", "GODFRYPHLP",
    # Conventional Banks, NBFCs, Broking, Insurance & Financial Intermediaries
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK", "BANKBARODA", "PNB",
    "CANBK", "UNIONBANK", "IOB", "UCOBANK", "CENTRALBK", "INDIANB", "BANKINDIA", "MAHABANK",
    "IDBI", "IDFCFIRSTB", "FEDERALBNK", "AUBANK", "BANDHANBNK", "YESBANK", "RBLBANK", "KARURVYSYA",
    "CUB", "J&KBANK", "EQUITASBNK", "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "CHOLAHLDNG",
    "MUTHOOTFIN", "MANAPPURAM", "SHRIRAMFIN", "POONAWALLA", "ABCAPITAL", "LTF", "M&MFIN", "MFSL",
    "PFC", "RECLTD", "IRFC", "IREDA", "HUDCO", "LICHSGFIN", "PNBHOUSING", "AAVAS", "APTUS",
    "REPCOHOME", "GICHSGFIN", "AADHARHFC", "INDIASHLTR", "CREDITACC", "FIVESTAR", "MASFIN",
    "ARMANFIN", "NORTHARC", "HDBFS", "PIRAMALFIN", "JIOFIN", "BAJAJHLDNG", "TATAINVEST", "PILANIINVS",
    "BFINVEST", "NSIL", "IITL", "CGCL", "INDOSTAR", "FINKURVE", "MANCREDIT",
    "CHOICEIN", "360ONE", "ANGELONE", "5PAISA", "MOTILALOFS", "IIFL", "JMFINANCIL", "NUVAMA",
    "ANANDRATHI", "PRUDENT", "GEOJITFSL", "INDOTHAI", "MONARCH", "MASTERTR", "ARSSBL", "DOLATALGO",
    "ALGOQUANT", "SHAREINDIA", "SBILIFE", "HDFCLIFE", "ICICIPRULI", "ICICIGI", "LICI", "GICRE",
    "STARHEALTH", "NIACL", "POLICYBZR", "MEDIASSIST", "TURTLEMINT", "UTIAMC", "HDFCAMC", "NAM-INDIA",
    "ABSLAMC", "CAMS", "KFINTECH", "CDSL", "BSE", "MCX", "CRISIL", "ICRA", "CARERATING",
    # Hotels, Hospitality, Casinos, Media, Entertainment & Advertising
    "INDHOTEL", "EIHOTEL", "CHALET", "LEMONTREE", "MHRIL", "ITCHOTELS", "ADVENTHTL", "BRIGHOTEL",
    "JUNIPER", "THELEELA", "PARKHOTELS", "SAMHI", "VENTIVE", "DELTACORP", "PVRINOX", "IMAGICAA",
    "ZEEL", "ZEEMEDIA", "SUNTV", "NETWORK18", "NDTV", "DBCORP", "AFFLE", "PRAVEG", "OPTIMYSTIX", "AMAGI",
    # Defense, Aerospace Weapons & Munitions
    "HAL", "BEL", "BDL", "MAZDOCK", "COCHINSHIP", "GRSE", "PARAS", "DATAPATTNS", "ZENTEC", "ASTRAMICRO"
}


def infer_sector_from_company_or_symbol(symbol: str, company_name: str = "") -> str:
    """
    Infers a deterministic sector/industry label from symbol and company name
    aligned with 'Copy of halal stock 2.0.xlsx' ('nse stock', 'list', 'Sheet19').
    """
    sym = (symbol or "").strip().upper()
    name_low = (company_name or "").strip().lower()

    if sym in {"BALRAMCHIN", "TRIVENI", "DWARKESH", "DALMIASUG", "RENUKA", "BAJAJHIND", "EIDPARRY", "ANDHRSUGAR", "DHAMPURSUG", "UTTAMSUGAR", "AVADHSUGAR", "MAGADHSUGAR"} or "sugar" in name_low:
        return "Sugar & Molasses Distillery"
    if sym in {"UBL", "UNITDSPR", "RADICO", "SULA", "GLOBUSSPR", "ASALCBR", "PICCADIL", "INDIAGLYCO", "TI", "SOMDIST", "GMBREW", "AGI", "PRAJIND", "GULPOLY"} or any(w in name_low for w in ("brewer", "distiller", "alcohol", "spirits", "vineyard", "winery", "wine", "liquor")):
        return "Beverages - Breweries & Distilleries"
    if sym in {"ITC", "VSTIND", "GODFRYPHLP"} or any(w in name_low for w in ("tobacco", "cigarette")):
        return "Tobacco & Cigarettes"
    if sym in {"HAL", "BEL", "BDL", "MAZDOCK", "COCHINSHIP", "GRSE", "PARAS", "DATAPATTNS", "ZENTEC", "ASTRAMICRO"} or any(w in name_low for w in ("defense", "defence", "weapons", "arms", "ammunition", "munitions")):
        return "Defense, Aerospace & Weapons"
    if sym in PROHIBITED_SYMBOLS and any(w in sym for w in ("HTL", "HOTEL", "LEELA", "CHALET", "JUNIPER", "SAMHI", "MHRIL", "VENTIVE")) or any(w in name_low for w in ("hotel", "resort", "hospitality")):
        return "Hospitality - Hotels & Resorts"
    if sym in {"PVRINOX", "IMAGICAA", "ZEEL", "ZEEMEDIA", "SUNTV", "NETWORK18", "NDTV", "DBCORP", "AFFLE", "PRAVEG", "OPTIMYSTIX", "AMAGI"} or any(w in name_low for w in ("entertainment", "media", "television", "broadcast", "advertising", "multiplex", "cinema")):
        return "Media, Entertainment & Advertising"
    if sym in PROHIBITED_SYMBOLS or any(w in name_low for w in ("bank", "finance", "financial", "fincorp", "finserv", "financier", "insurance", "assurance", "broking", "broker", "securities", "wealth", "capital", "investment", "credit", "housing finance", "leasing", "mutual fund", "fintech")):
        return "Financial Services - Banking, NBFC & Broking"
    if any(w in name_low for w in ("pharma", "drug", "biocon", "medic", "health", "hospital", "lifescience", "laborator", "diagnostic", "eye", "dental")):
        return "Pharmaceuticals & Healthcare"
    if any(w in name_low for w in ("software", "tech", "infosys", "wipro", "comput", "digital", "cyber", "info", "datamatic", "eclerx", "mastek", "persistent", "coforge", "cyient", "mphasis", "zensar", "sonata", "tanla", "intellect", "kpit")):
        return "Information Technology & Software"
    if any(w in name_low for w in ("chem", "fertiliz", "alkali", "amine", "nitrite", "fluoro", "organics", "pesticid", "agro", "crop", "paint", "pigment", "resin")):
        return "Chemicals, Agrochemicals & Paints"
    if any(w in name_low for w in ("auto", "motor", "tyre", "forge", "bearing", "axle", "castalloy", "fastener", "minda", "gabriel", "endurance", "subros", "lumax", "pricol", "fiem", "carraro", "hyundai")):
        return "Automobile & Auto Ancillaries"
    if any(w in name_low for w in ("cement", "infra", "construct", "realty", "brigade", "oberoi", "ceramic", "tiles", "sanitary", "ply", "panel", "housing")):
        return "Cement, Construction & Real Estate"
    if any(w in name_low for w in ("steel", "metal", "alumin", "copper", "zinc", "iron", "ispat", "ferro", "alloy", "wire", "pipe", "tube", "mining", "mineral", "gold", "coal")):
        return "Metals, Pipes & Mining"
    if any(w in name_low for w in ("power", "energy", "solar", "wind", "gas", "petrol", "oil", "electric", "cable", "volt", "transformer")):
        return "Power, Energy & Electrical Equipment"
    if any(w in name_low for w in ("textile", "apparel", "fashion", "cloth", "garment", "cotton", "spinning", "yarn", "fibre", "denim", "footwear")):
        return "Textiles, Apparel & Footwear"
    if any(w in name_low for w in ("food", "dairy", "snack", "tea", "coffee", "biscuit", "consumer", "fmcg", "sugar")):
        return "FMCG & Food Processing"
    return "Industrial Manufacturing & Capital Goods"


def check_shariah_compliance(fundamentals: Dict[str, Any], sector_name: str = "") -> Tuple[bool, str]:
    """
    Evaluates Shariah compliance based on business sector and 6 strict quantitative conditions
    per the Fatwa of Justice Mufti Muhammad Taqi Usmani and 'Copy of halal stock 2.0.xlsx':
    1. Primary business activity must be permissible (Halal).
    2. Debt / Total Assets <= 33.0%.
    3. Cash & Interest-Bearing Investments / Total Assets <= 33.0%.
    4. Impure Income / Total Revenue (Sales + Other Income) <= 5.0%.
    5. Illiquid Assets / Total Assets >= 20.0% (and Receivables / Total Assets <= 49.0%).
    6. Net Liquid Assets <= Market Capitalization (F78 <= F80).
    """
    # 0. Explicit Symbol Blacklist Check ('Copy of halal stock 2.0.xlsx' list & Sheet19)
    sym_upper = str(fundamentals.get("symbol") or "").strip().upper()
    if sym_upper and sym_upper in PROHIBITED_SYMBOLS:
        return False, f"NON_COMPLIANT_SECTOR_{sym_upper}"

    # 1. Sector & Qualitative Screen (Fail closed on missing/empty sector, regex word boundary with plural support)
    effective_sector = (sector_name or fundamentals.get("sector_name") or fundamentals.get("sector") or "").strip()
    if not effective_sector:
        return False, "FAIL_CLOSED_EMPTY_SECTOR_NAME"

    sector_lower = effective_sector.lower()
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

    # Rule 3: Cash & Interest-Bearing Investments / Total Assets <= 33%
    cash_to_assets = fundamentals.get("cash_to_assets")
    if cash_to_assets is None and ("cash_equivalents" in fundamentals or "investments" in fundamentals):
        cash_eq = float(fundamentals.get("cash_equivalents") or 0.0)
        invest = float(fundamentals.get("investments") or 0.0)
        if total_assets and total_assets > 0:
            cash_to_assets = (cash_eq + invest) / float(total_assets)
    if cash_to_assets is not None and cash_to_assets > 0.33:
        return False, f"EXCESSIVE_CASH_ASSETS_{cash_to_assets:.2%}"

    # Rule 4: Interest or Non-Compliant Income / Total Revenue (Sales + Other Income) <= 5%
    if "sales" in fundamentals and (fundamentals["sales"] is None or fundamentals["sales"] <= 0):
        return False, "INVALID_OR_ZERO_SALES_FOR_INCOME_CHECK"
        
    interest_income_ratio = fundamentals.get("interest_income_ratio")
    if interest_income_ratio is None:
        sales = fundamentals.get("sales")
        other_inc = float(fundamentals.get("other_income") or 0.0)
        impure_income = fundamentals.get("impure_income")
        if impure_income is None:
            impure_income = fundamentals.get("interest_income")
        if impure_income is None and "other_income" in fundamentals:
            impure_income = fundamentals.get("other_income")
        total_revenue = (float(sales) + max(0.0, other_inc)) if sales and sales > 0 else 0.0
        if total_revenue > 0 and impure_income is not None:
            interest_income_ratio = float(impure_income) / total_revenue
        else:
            return False, "MISSING_INCOME_RATIO_DATA"

    if interest_income_ratio is None or interest_income_ratio > 0.05:
        pct_str = f"{interest_income_ratio:.2%}" if interest_income_ratio is not None else "N/A"
        return False, f"EXCESSIVE_INTEREST_INCOME_{pct_str}"

    # Rule 5: Illiquid Assets / Total Assets >= 20%
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

    # Rule 5B: AAOIFI Standard 21 Receivables Screen (Accounts Receivables / Total Assets <= 49%)
    receivables = fundamentals.get("accounts_receivable") or fundamentals.get("trade_receivables")
    total_assets = fundamentals.get("total_assets")
    if receivables is not None and total_assets and total_assets > 0:
        rec_ratio = receivables / total_assets
        if rec_ratio > 0.49:
            return False, f"EXCESSIVE_RECEIVABLES_{rec_ratio:.2%}"

    # Rule 6: Net Liquid Assets <= Market Capitalization (Mufti Taqi Usmani 5th Condition)
    net_liquid_assets = fundamentals.get("net_liquid_assets_crores")
    market_cap = fundamentals.get("market_cap_crores")

    if net_liquid_assets is None or market_cap is None:
        return False, "MISSING_NET_LIQUID_OR_MARKET_CAP_DATA"
        
    if market_cap <= 0:
        return False, "INVALID_OR_ZERO_MARKET_CAP"
        
    if net_liquid_assets > market_cap:
        return False, f"EXCESSIVE_NET_LIQUID_ASSETS (Net Liquid ₹{net_liquid_assets:.2f} Cr > Market Cap ₹{market_cap:.2f} Cr)"

    return True, "PASSED_SHARIAH_GATE"
