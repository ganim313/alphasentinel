import json

file_path = 'notebooks/alpha_factory_evolution.ipynb'
with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find the last cell
last_cell = nb['cells'][-1]
source = "".join(last_cell['source'])

# Rewrite the last cell source
new_source = """print("\\n======================================================")
print("🏆 SURVIVAL OF THE FITTEST: THE 3 WINNING SUPER-FORMULAS 🏆")
print("======================================================\\n")

# We transform the untouched OOS test data using the evolved formulas to ensure they aren't noise
X_test = test_data[feature_cols].values
y_test = test_data['target'].values
transformed_test = gp.transform(X_test)

output_log = []
for i, formula in enumerate(gp): 
    res_str = f"Super Formula {i+1}:\\n{formula}\\n"
    
    # Check Rank Correlation (IC - Information Coefficient) on the Out-Of-Sample Data
    formula_values = transformed_test[:, i]
    ic_score = pd.Series(formula_values).corr(pd.Series(y_test), method='spearman')
    res_str += f"Out-Of-Sample Rank Correlation (IC): {ic_score:.4f}\\n"
    
    print(res_str)
    output_log.append(res_str)
    
print("======================================================")
print("To implement these in your live bot:")
print("1. Ensure the Out-Of-Sample IC score is solid (e.g., > 0.02 or < -0.02).")
print("2. Map X0 (ret_1d), X3 (vol_norm), etc., and write it in Python in src/screening/ml_factor.py.")
print("3. Retrain your XGBoost champion model to evaluate true contribution.")
print("======================================================")

# CRITICAL KAGGLE FIX: Save to a file so you don't lose the formulas when you close your browser!
with open("winning_formulas.txt", "w") as f:
    f.write("\\n".join(output_log))
print("✅ Saved formulas to winning_formulas.txt for easy download.")
"""

# Re-split into lines keeping newlines
last_cell['source'] = [line + '\n' for line in new_source.split('\n')]
# Remove the extra newline on the very last element
last_cell['source'][-1] = last_cell['source'][-1].strip('\n')

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=2)
