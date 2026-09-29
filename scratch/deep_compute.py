import json

file_path = 'notebooks/alpha_factory_evolution.ipynb'
with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source_str = "".join(cell['source'])
        
        # 1. Update the Universe to automatically scrape Nifty 50 + Nifty Next 50 from Wikipedia
        if "NIFTY_UNIVERSE =" in source_str:
            new_universe = """import pandas as pd
import logging

logger.info("Scraping Nifty 50 and Nifty Next 50 lists from Wikipedia...")
try:
    # Nifty 50
    nifty_50_df = pd.read_html("https://en.wikipedia.org/wiki/NIFTY_50")[2]
    nifty_50 = nifty_50_df['Symbol'].astype(str) + ".NS"
    
    # Nifty Next 50
    nifty_next_50_df = pd.read_html("https://en.wikipedia.org/wiki/NIFTY_Next_50")[3]
    nifty_next_50 = nifty_next_50_df['Symbol'].astype(str) + ".NS"
    
    NIFTY_UNIVERSE = list(set(nifty_50.tolist() + nifty_next_50.tolist()))
    logger.info(f"Successfully loaded {len(NIFTY_UNIVERSE)} Nifty 100 stocks!")
except Exception as e:
    logger.error(f"Failed to scrape Wikipedia, falling back to hardcoded list: {e}")
    NIFTY_UNIVERSE = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ITC.NS", 
        "LT.NS", "BAJFINANCE.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS",
        "TRENT.NS", "TVSMOTOR.NS", "CUMMINSIND.NS", "FEDERALBNK.NS", "DIXON.NS",
        "LUPIN.NS", "BSE.NS", "PERSISTENT.NS", "POLYCAB.NS", "ASTRAL.NS"
    ]
"""
            import re
            source_str = re.sub(
                r"# A Stratified Universe.*?\]", 
                new_universe, 
                source_str, 
                flags=re.DOTALL
            )
            cell['source'] = [line + '\n' for line in source_str.split('\n')]
            cell['source'][-1] = cell['source'][-1].strip('\n')
            
        # 2. Scale up the Genetic Programming compute significantly
        elif "gp = SymbolicTransformer(" in source_str:
            source_str = source_str.replace("generations=25", "generations=60")
            source_str = source_str.replace("population_size=3000", "population_size=8000")
            
            cell['source'] = [line + '\n' for line in source_str.split('\n')]
            cell['source'][-1] = cell['source'][-1].strip('\n')

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)
