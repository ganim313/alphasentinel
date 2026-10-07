-- Migration 003: Settlement Tracking & Holdings Guardian Log
-- Aligns with Mufti Taqi Usmani Bay' qabl al-Qabd prohibition and FYERS T1 GTT rejection guard

ALTER TABLE positions ADD COLUMN settlement_status VARCHAR DEFAULT 'SETTLING_T0_T1';
ALTER TABLE positions ADD COLUMN can_exit BOOLEAN DEFAULT FALSE;
ALTER TABLE positions ADD COLUMN gtt_placed BOOLEAN DEFAULT FALSE;
ALTER TABLE positions ADD COLUMN gtt_placed_at TIMESTAMPTZ;
ALTER TABLE positions ADD COLUMN purification_due_inr DOUBLE DEFAULT 0.0;

CREATE TABLE IF NOT EXISTS guardian_log (
    id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMPTZ,
    symbol VARCHAR,
    action VARCHAR,
    rule VARCHAR,
    details JSON,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
