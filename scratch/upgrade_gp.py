import json

file_path = 'notebooks/alpha_factory_evolution.ipynb'
with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source_str = "".join(cell['source'])
        
        # 1. Expand the feature engineering to give the AI more ingredients
        if "df['ret_1d'] = df['close'].pct_change(1)" in source_str:
            new_features = """    # Base Ingredients for the Alpha Factory
    df['ret_1d'] = df['close'].pct_change(1)
    df['ret_3d'] = df['close'].pct_change(3)
    df['ret_5d'] = df['close'].pct_change(5)
    df['ret_10d'] = df['close'].pct_change(10)
    df['ret_20d'] = df['close'].pct_change(20)
    
    # Moving Average Distances
    df['ma_5_dist'] = df['close'] / (df['close'].rolling(5).mean() + 1e-9) - 1
    df['ma_20_dist'] = df['close'] / (df['close'].rolling(20).mean() + 1e-9) - 1
    
    # Volatility and Spreads
    df['vol_norm_5d'] = df['volume'] / (df['volume'].rolling(5).mean() + 1e-9)
    df['vol_norm_20d'] = df['volume'] / (df['volume'].rolling(20).mean() + 1e-9)
    df['high_low_spread'] = (df['high'] - df['low']) / df['close']
    df['close_pos'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-9)
"""
            # Replace the old base ingredients with the new ones
            import re
            source_str = re.sub(
                r"    # Base Ingredients for the Alpha Factory.*?(?=    # The Ultimate Goal)", 
                new_features, 
                source_str, 
                flags=re.DOTALL
            )
            cell['source'] = [line + '\n' for line in source_str.split('\n')]
            cell['source'][-1] = cell['source'][-1].strip('\n')
            
        # 2. Update feature_cols in the split cell
        elif "feature_cols = ['ret_1d'" in source_str:
            source_str = source_str.replace(
                "feature_cols = ['ret_1d', 'ret_5d', 'ret_20d', 'vol_norm', 'high_low_spread', 'close_pos']",
                "feature_cols = ['ret_1d', 'ret_3d', 'ret_5d', 'ret_10d', 'ret_20d', 'ma_5_dist', 'ma_20_dist', 'vol_norm_5d', 'vol_norm_20d', 'high_low_spread', 'close_pos']"
            )
            
            # Also update the gp settings to be more rigorous
            source_str = source_str.replace("generations=15", "generations=25")
            source_str = source_str.replace("population_size=1000", "population_size=3000")
            source_str = source_str.replace("metric='pearson'", "metric='spearman'")
            source_str = source_str.replace("parsimony_coefficient=0.001", "parsimony_coefficient=0.005") # Punish lazy multiplication bloat
            
            cell['source'] = [line + '\n' for line in source_str.split('\n')]
            cell['source'][-1] = cell['source'][-1].strip('\n')

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)
