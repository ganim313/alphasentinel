import json

file_path = 'notebooks/alpha_factory_evolution.ipynb'
with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source_str = "".join(cell['source'])
        
        # Replace the large-cap only universe with a stratified universe
        if "NIFTY_UNIVERSE = [" in source_str:
            new_universe = """# A Stratified Universe: 10 Large Caps, 10 Mid Caps, 10 Small Caps
NIFTY_UNIVERSE = [
    # Large Caps (Nifty 50) - Institutional, low volatility
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", 
    "LT.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS",
    
    # Mid Caps (Nifty Midcap 150) - Higher growth, higher volatility
    "TRENT.NS", "TVSMOTOR.NS", "CUMMINSIND.NS", "FEDERALBNK.NS", "DIXON.NS",
    "LUPIN.NS", "BSE.NS", "PERSISTENT.NS", "POLYCAB.NS", "ASTRAL.NS",
    
    # Small Caps (Nifty Smallcap 250) - Retail driven, explosive momentum
    "ANGELONE.NS", "CDSL.NS", "SUZLON.NS", "RADICO.NS", "BEML.NS",
    "SONACOMS.NS", "APARINDS.NS", "CHALET.NS", "WELSPUNLIV.NS", "NATCOPHARM.NS"
]"""
            import re
            source_str = re.sub(
                r"# We use a representative sample.*?\]", 
                new_universe, 
                source_str, 
                flags=re.DOTALL
            )
            cell['source'] = [line + '\n' for line in source_str.split('\n')]
            cell['source'][-1] = cell['source'][-1].strip('\n')

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)
