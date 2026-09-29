-- =============================================================================
-- AlphaSentinel DuckDB Core Database Schema
-- Version: 2.1.0 (Production Implementation)
-- Aligned with Master PRD (03_requirements_engineering.md) & HLD/LLD (04_system_design_architecture.md)
-- =============================================================================

-- 1. Daily Historical Bhavcopy (Point-in-Time Split-Adjusted EOD Data)
CREATE TABLE IF NOT EXISTS bhavcopy_daily (
    symbol VARCHAR NOT NULL,
    trade_date DATE NOT NULL,
    series VARCHAR DEFAULT 'EQ',
    open_price DOUBLE NOT NULL,
    high_price DOUBLE NOT NULL,
    low_price DOUBLE NOT NULL,
    close_price DOUBLE NOT NULL,
    last_price DOUBLE,
    prev_close DOUBLE,
    total_traded_qty BIGINT,
    total_traded_val DOUBLE,
    delivery_qty BIGINT,
    delivery_pct DOUBLE,
    split_multiplier DOUBLE DEFAULT 1.0,
    upper_circuit DOUBLE,
    lower_circuit DOUBLE,
    circuit_band_pct INTEGER,
    is_asm BOOLEAN DEFAULT FALSE,
    is_gsm BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
);

-- 2. Corporate Actions Register (Splits, Bonuses, Adjustments)
CREATE TABLE IF NOT EXISTS corporate_actions (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL, -- SPLIT, BONUS, RIGHTS
    ex_date DATE NOT NULL,
    ratio_from DOUBLE NOT NULL,
    ratio_to DOUBLE NOT NULL,
    adjustment_multiplier DOUBLE NOT NULL,
    is_applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Live & Paper Positions Portfolio
CREATE TABLE IF NOT EXISTS positions (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    candidate_id VARCHAR,
    sector VARCHAR,
    exchange VARCHAR DEFAULT 'NSE',
    entry_date DATE NOT NULL,
    entry_price DOUBLE NOT NULL,
    quantity INTEGER NOT NULL,
    current_ltp DOUBLE NOT NULL,
    peak_high DOUBLE,
    atr DOUBLE,
    unrealized_pnl DOUBLE DEFAULT 0.0,
    trailing_stop_loss DOUBLE NOT NULL,
    target_1 DOUBLE NOT NULL,
    target_2 DOUBLE NOT NULL,
    risk_rupees DOUBLE NOT NULL,
    portfolio_allocation_pct DOUBLE NOT NULL,
    status VARCHAR DEFAULT 'OPEN', -- OPEN, TARGET_1_TRIMMED, CLOSED, STOPPED_OUT, TARGET_REACHED, MARKED_FOR_CLOSURE
    execution_type VARCHAR DEFAULT 'PAPER', -- PAPER, LIVE, DHAN_SIMULATED
    exit_date DATE,
    exit_price DOUBLE,
    realized_pnl DOUBLE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 4. Shariah Dividend & Capital Gain Purification Log
CREATE TABLE IF NOT EXISTS purification_log (
    id VARCHAR PRIMARY KEY,
    trade_id VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    exit_date DATE NOT NULL,
    net_profit DOUBLE NOT NULL,
    impure_income_ratio DOUBLE NOT NULL,
    purification_amount DOUBLE NOT NULL,
    is_donated BOOLEAN DEFAULT FALSE,
    donation_date DATE,
    charity_recipient VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 5. Screener Candidates Register (Multi-Model Consensus)
CREATE TABLE IF NOT EXISTS screener_candidates (
    id VARCHAR PRIMARY KEY,
    scan_date DATE NOT NULL,
    symbol VARCHAR NOT NULL,
    sector VARCHAR,
    pattern_type VARCHAR NOT NULL, -- MINERVINI_VCP_STAGE2, MEAN_REVERSION, ML_MOMENTUM
    trigger_price DOUBLE NOT NULL,
    adtv_20d DOUBLE NOT NULL,
    market_cap_tier VARCHAR NOT NULL, -- LARGE, MID, SMALL, MICRO
    circuit_band DOUBLE NOT NULL,
    is_t2t BOOLEAN DEFAULT FALSE,
    delivery_pct DOUBLE,
    ml_probability DOUBLE DEFAULT 0.0,
    mr_signal BOOLEAN DEFAULT FALSE,
    pledge_trend_3m DOUBLE,
    shield_passed BOOLEAN DEFAULT FALSE,
    status VARCHAR DEFAULT 'PENDING', -- PENDING, PENDING_REVIEW, APPROVED, REJECTED, SIZING_REJECTED, EXECUTION_REJECTED
    rejection_reason VARCHAR,
    ab_group VARCHAR DEFAULT 'control',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. LangGraph Multi-Agent Debate Transcripts
CREATE TABLE IF NOT EXISTS debate_transcripts (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    debate_date DATE NOT NULL,
    macro_regime_score DOUBLE,
    bull_thesis TEXT,
    bear_risks TEXT,
    judge_synthesis TEXT,
    tv_technical_rating VARCHAR,
    conviction_score DOUBLE,
    risk_manager_verdict VARCHAR NOT NULL, -- APPROVE, APPROVE_WITH_WARNING, REDUCE_SIZE, REJECT
    suggested_shares INTEGER,
    stop_loss DOUBLE,
    target_1 DOUBLE,
    target_2 DOUBLE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 7. Agent Memory & Historical Feedback Loop
CREATE TABLE IF NOT EXISTS agent_memory (
    symbol VARCHAR NOT NULL,
    memory_date DATE NOT NULL,
    pattern_type VARCHAR NOT NULL,
    previous_verdict VARCHAR NOT NULL, -- APPROVE, REJECT
    rejection_reason TEXT,
    outcome_3d_pct DOUBLE,
    outcome_7d_pct DOUBLE,
    bear_flags_noted TEXT,
    kronos_score DOUBLE,
    conviction_score DOUBLE,
    content TEXT,
    outcome_label VARCHAR,
    triple_barrier_label INTEGER, -- 1: Hit Target, -1: Hit SL, 0: Time Out
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, memory_date)
);

-- 8. Fundamentals & Scraping Cache (7-Day TTL)
CREATE TABLE IF NOT EXISTS fundamentals_cache (
    symbol VARCHAR PRIMARY KEY,
    fundamentals_json TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 9. Promoter Pledge History
CREATE TABLE IF NOT EXISTS promoter_pledge_history (
    symbol VARCHAR NOT NULL,
    quarter_end_date DATE NOT NULL,
    pledge_pct DOUBLE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, quarter_end_date)
);

-- 10. Delisted Stocks Tracking (Survivorship Bias Guard)
CREATE TABLE IF NOT EXISTS delisted_stocks (
    symbol VARCHAR PRIMARY KEY,
    delisted_date DATE NOT NULL,
    reason VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 11. Automated Evaluator: Paper Portfolios
CREATE TABLE IF NOT EXISTS paper_portfolios (
    portfolio_id VARCHAR PRIMARY KEY,
    portfolio_name VARCHAR NOT NULL,
    initial_capital DOUBLE DEFAULT 1000000.0,
    cash_balance DOUBLE DEFAULT 1000000.0,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 12. Global Circuit Breakers & Emergency Kill-Switch State
CREATE TABLE IF NOT EXISTS circuit_breaker_state (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    is_halted BOOLEAN DEFAULT FALSE,
    halt_reason VARCHAR,
    monthly_drawdown_pct DOUBLE DEFAULT 0.0,
    high_water_mark DOUBLE DEFAULT 1000000.0,
    monthly_peak_equity DOUBLE DEFAULT 1000000.0,
    last_kill_switch_trigger TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Insert default circuit breaker state if empty
INSERT OR IGNORE INTO circuit_breaker_state (id, is_halted, halt_reason, monthly_drawdown_pct)
VALUES (1, FALSE, 'INITIALIZED', 0.0);

-- Indexes for sub-millisecond query performance
CREATE INDEX IF NOT EXISTS idx_bhavcopy_date_sym ON bhavcopy_daily(trade_date, symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol_status ON positions(symbol, status);
CREATE INDEX IF NOT EXISTS idx_candidates_scan_date ON screener_candidates(scan_date);
CREATE INDEX IF NOT EXISTS idx_purification_date ON purification_log(exit_date);
CREATE INDEX IF NOT EXISTS idx_purification_trade ON purification_log(trade_id);

-- 13. Instrument Master (Fyers/Dhan Mappings)
CREATE TABLE IF NOT EXISTS instrument_master (
    symbol VARCHAR PRIMARY KEY,
    fyers_token VARCHAR,
    dhan_security_id VARCHAR,
    exchange VARCHAR DEFAULT 'NSE',
    series VARCHAR DEFAULT 'EQ',
    lot_size INTEGER DEFAULT 1,
    tick_size DOUBLE DEFAULT 0.05,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_instrument_fyers ON instrument_master(fyers_token);
CREATE INDEX IF NOT EXISTS idx_instrument_dhan ON instrument_master(dhan_security_id);

CREATE TABLE IF NOT EXISTS nse_holiday_cache (
    cache_key VARCHAR PRIMARY KEY, 
    holidays_json TEXT, 
    fetched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 14. Macro Weather Cache
CREATE TABLE IF NOT EXISTS macro_weather (
    scan_date DATE PRIMARY KEY,
    us_vix DOUBLE,
    sp500_pct_change DOUBLE,
    crude_oil_price DOUBLE,
    crude_oil_pct_change DOUBLE,
    usdinr_price DOUBLE,
    usdinr_pct_change DOUBLE,
    polymarket_risk_score DOUBLE,
    market_regime VARCHAR,
    macro_weather_score DOUBLE,
    target_cash_exposure_pct DOUBLE,
    source VARCHAR,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 15. Historical Portfolio Equity Curve
CREATE TABLE IF NOT EXISTS equity_curve (
    trade_date DATE PRIMARY KEY,
    total_equity DOUBLE NOT NULL,
    core_equity DOUBLE,
    unrealized_pnl DOUBLE,
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 16. Strategy Versions & Parameter Trial Tracking (DSR / PBO)
CREATE TABLE IF NOT EXISTS strategy_version (
    id INTEGER PRIMARY KEY,
    strategy_name VARCHAR NOT NULL,
    parameters_hash VARCHAR UNIQUE NOT NULL,
    parameters_json TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Missing composite indexes identified in System Critic Audit
CREATE INDEX IF NOT EXISTS idx_positions_sector_status ON positions(sector, status);
CREATE INDEX IF NOT EXISTS idx_positions_status_exit ON positions(status, exit_date);
CREATE INDEX IF NOT EXISTS idx_candidates_status_scan ON screener_candidates(status, scan_date);
CREATE INDEX IF NOT EXISTS idx_corp_actions_applied ON corporate_actions(is_applied, ex_date);