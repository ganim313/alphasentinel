import json

notebook_path = r"c:\Users\Md Ganim\Desktop\trading agents\notebooks\alpha_factory_evolution.ipynb"

stratified_stocks = [
    # Large Cap (Nifty 50)
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "ITC.NS", "SBIN.NS", 
    "BHARTIARTL.NS", "HINDUNILVR.NS", "BAJFINANCE.NS", "LT.NS", "KOTAKBANK.NS", "AXISBANK.NS", 
    "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "TATASTEEL.NS", 
    "NTPC.NS", "POWERGRID.NS", "TATAMOTORS.NS", "M&M.NS", "WIPRO.NS", "NESTLEIND.NS", 
    "HCLTECH.NS", "TECHM.NS", "BAJAJFINSV.NS", "INDUSINDBK.NS", "GRASIM.NS", "HINDALCO.NS", 
    "ONGC.NS", "COALINDIA.NS", "CIPLA.NS", "BRITANNIA.NS", "EICHERMOT.NS", "DIVISLAB.NS", 
    "APOLLOHOSP.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "TATASTLLP.NS", "ADANIPORTS.NS", 
    "ADANIENT.NS", "DRREDDY.NS", "TATACONSUM.NS", "UPL.NS", "SBILIFE.NS", "HDFCLIFE.NS",
    
    # Mid Cap (Nifty Midcap 150)
    "TRENT.NS", "TVSMOTOR.NS", "CUMMINSIND.NS", "FEDERALBNK.NS", "DIXON.NS", "LUPIN.NS", 
    "BSE.NS", "PERSISTENT.NS", "POLYCAB.NS", "ASTRAL.NS", "COFORGE.NS", "IDFCFIRSTB.NS", 
    "ASHOKLEY.NS", "MRF.NS", "PIIND.NS", "CONCOR.NS", "JUBLFOOD.NS", "VOLTAS.NS", 
    "OBEROIRLTY.NS", "GODREJPROP.NS", "AUBANK.NS", "ABCAPITAL.NS", "APOLLOTYRE.NS", 
    "BALKRISIND.NS", "BANDHANBNK.NS", "BANKINDIA.NS", "BHARATFORG.NS", "CANBK.NS", 
    "CHOLAFIN.NS", "COROMANDEL.NS", "CROMPTON.NS", "DALBHARAT.NS", "ESCORTS.NS", 
    "EXIDEIND.NS", "GMRINFRA.NS", "GUJGASLTD.NS", "HAL.NS", "HINDPETRO.NS", "IGL.NS", 
    "INDIANB.NS", "INDHOTEL.NS", "IPCALAB.NS", "JSWENERGY.NS", "L&TFH.NS", "LICHSGFIN.NS", 
    "MAXHEALTH.NS", "MFSL.NS", "MGL.NS", "MUTHOOTFIN.NS", "NAUKRI.NS", "PAGEIND.NS",
    
    # Small Cap (Nifty Smallcap 250)
    "SUZLON.NS", "CDSL.NS", "ANGELONE.NS", "RADICO.NS", "PNBHOUSING.NS", "CYIENT.NS", 
    "KALYANKJIL.NS", "CAMS.NS", "SONACOMS.NS", "KPITTECH.NS", "UTIAMC.NS", "RVNL.NS", 
    "IRFC.NS", "MAZDOCK.NS", "COCHINSHIP.NS", "RAYMOND.NS", "BEML.NS", "CENTURYTEX.NS", 
    "CESC.NS", "CHAMBLFERT.NS", "EQUITASBNK.NS", "GLENMARK.NS", "GNFC.NS", "GRANULES.NS", 
    "GSPL.NS", "HFCL.NS", "HINDCOPPER.NS", "JBCHEPHARM.NS", "JINDALSAW.NS", "LATENTVIEW.NS", 
    "LXCHEM.NS", "MCX.NS", "METROPOLIS.NS", "NATCOPHARM.NS", "NBCC.NS", "PRAJIND.NS", 
    "PRINCEPIPE.NS", "PVRINOX.NS", "REDINGTON.NS", "RENUKA.NS", "ROUTE.NS", "SYNGENE.NS", 
    "TEJASNET.NS", "TIDEL.NS", "TRIDENT.NS", "UCOBANK.NS", "VIPIND.NS", "WELCORP.NS", 
    "ZENSARTECH.NS", "ZYDUSWELL.NS"
]

new_cell_source = [
    "import pandas as pd\n",
    "import logging\n",
    "\n",
    "logger.info(\"Loading strictly stratified universe (Large, Mid, Small Caps)...\")\n",
    "NIFTY_UNIVERSE = [\n",
    "    " + ", ".join(f'"{sym}"' for sym in stratified_stocks) + "\n",
    "]\n",
    "logger.info(f\"Successfully loaded {len(NIFTY_UNIVERSE)} stratified stocks!\")\n"
]

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb.get('cells', []):
    if cell.get('cell_type') == 'code':
        source = cell.get('source', [])
        if any("Scraping Nifty 50 and Nifty Next 50 lists from Wikipedia" in line for line in source):
            cell['source'] = new_cell_source
            break

with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)

print("Successfully updated alpha_factory_evolution.ipynb with a stratified stock universe.")
