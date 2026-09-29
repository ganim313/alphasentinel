import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from src.db.session import get_read_connection
import logging

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "xgboost_global.pkl"

# Load globally into memory ONCE on process startup
try:
    with open(MODEL_PATH, "rb") as f:
        global_model = pickle.load(f)
except Exception:
    logger.warning("Global XGBoost model not found. ML Predictor will return 0.0.")
    global_model = None

def evaluate_xgboost_probability(symbol: str, conn, live_price: float = None, live_volume: int = None, as_of_date: str = None) -> float:
    """
    Infers the probability of an upward move using the pre-trained global XGBoost model.
    Sub-millisecond execution with enhanced 11-indicator quantitative feature set.
    """
    if global_model is None:
        return 0.0
        
    query = """
        SELECT trade_date, close_price, high_price, low_price, total_traded_qty as volume, split_multiplier
        FROM (
            SELECT trade_date, close_price, high_price, low_price, total_traded_qty, split_multiplier
            FROM bhavcopy_daily
            WHERE symbol = ?
    """
    params = [symbol]
    
    if as_of_date:
        query += " AND trade_date < ?"
        params.append(as_of_date)
        
    query += """
            ORDER BY trade_date DESC
            LIMIT 300
        ) sub
        ORDER BY trade_date ASC;
    """
    
    try:
        df = conn.execute(query, params).df()
    except Exception:
        df = pd.DataFrame()
        
    if df.empty:
        return 0.0
        
    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.date
    
    from src.screening.ml_features import engineer_live_tick, extract_quantitative_features
    df = engineer_live_tick(df, live_price, live_volume)

    if len(df) < 50:
        return 0.0
        
    df.set_index('trade_date', inplace=True)
    df = extract_quantitative_features(df)
    
    # Check what features the loaded model expects (adapt dynamically)
    expected_features = getattr(global_model, 'feature_names_in_', None)
    if expected_features is None:
        expected_features = ['sharpe_rank', 'dist_high', 'market_regime', 'rel_rsi', 'ema_dist', 'vol_cluster']
    
    try:
        latest_features = df.iloc[-1:][list(expected_features)]
        if latest_features.isna().values.any():
            return 0.0
            
        prob = global_model.predict_proba(latest_features)[0][1]
        return float(prob)
    except Exception as e:
        logger.error(f"Error in ML Predictor inference for {symbol}: {e}")
        return 0.0

def evaluate_ensemble_gate(symbol: str, conn, live_price: float = None, live_volume: int = None, as_of_date: str = None) -> float:
    """Unified Ensemble ML Gate: Now relies entirely on XGBoost, bypassing FinRL bloat."""
    return evaluate_xgboost_probability(symbol, conn, live_price, live_volume, as_of_date)

# Backward-compatible alias
evaluate_ml_probability = evaluate_xgboost_probability
