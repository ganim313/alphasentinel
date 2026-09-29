import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import accuracy_score

def run_ml_factor(close_df, high_df, low_df, volume_df):
    """
    XGBoost Factor Model.
    Features: RSI(14), Volume Change, SMA20/SMA50 ratio, Price Momentum(10).
    Target: 5-day forward return > 0.
    Since we can't peek into the future, we will train on a rolling window, 
    but for this quick shootout, we will train on first 50% of data, test on next 50%.
    We output 0s for the training period to make it a fair out-of-sample comparison.
    """
    signals = pd.DataFrame(index=close_df.index, columns=close_df.columns, data=0)
    
    for col in close_df.columns:
        if col == '^INDIAVIX':
            continue
            
        df = pd.DataFrame({'close': close_df[col], 'volume': volume_df[col]})
        
        # Features
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        df['vol_change'] = df['volume'].pct_change()
        df['sma20'] = df['close'].rolling(20).mean()
        df['sma50'] = df['close'].rolling(50).mean()
        df['sma_ratio'] = df['sma20'] / df['sma50']
        df['mom10'] = df['close'].pct_change(10)
        
        # Target: Next 5 days return
        df['fwd_ret'] = df['close'].shift(-5) / df['close'] - 1
        df['target'] = (df['fwd_ret'] > 0).astype(int)
        
        # Drop NAs
        df_clean = df.dropna()
        if len(df_clean) < 100:
            continue
            
        # Split (50% train, 50% test)
        split_idx = int(len(df_clean) * 0.5)
        train = df_clean.iloc[:split_idx]
        test = df_clean.iloc[split_idx:]
        
        features = ['rsi', 'vol_change', 'sma_ratio', 'mom10']
        
        X_train, y_train = train[features], train['target']
        X_test = test[features]
        
        model = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.05, random_state=42)
        model.fit(X_train, y_train)
        
        preds = model.predict(X_test)
        
        # Align predictions back to the original index
        # We set 1 if model predicts UP, else 0
        sig_series = pd.Series(index=df.index, data=0)
        sig_series.loc[X_test.index] = preds
        
        signals[col] = sig_series
        
    return signals
