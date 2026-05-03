-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Work Items (source of truth)
CREATE TABLE IF NOT EXISTS work_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id VARCHAR(100) NOT NULL,
    title VARCHAR(500) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED')),
    priority VARCHAR(5) NOT NULL DEFAULT 'P2'
        CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
    signal_count INTEGER NOT NULL DEFAULT 1,
    first_signal_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_signal_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    mttr_seconds INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RCA records (linked 1:1 to work items)
CREATE TABLE IF NOT EXISTS rca_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    incident_start TIMESTAMPTZ NOT NULL,
    incident_end TIMESTAMPTZ NOT NULL,
    root_cause_category VARCHAR(50) NOT NULL
        CHECK (root_cause_category IN (
            'HARDWARE_FAILURE', 'SOFTWARE_BUG', 'CONFIGURATION_ERROR',
            'CAPACITY_EXHAUSTION', 'NETWORK_ISSUE', 'HUMAN_ERROR',
            'THIRD_PARTY_DEPENDENCY', 'UNKNOWN'
        )),
    root_cause_description TEXT NOT NULL,
    fix_applied TEXT NOT NULL,
    prevention_steps TEXT NOT NULL,
    submitted_by VARCHAR(100) NOT NULL DEFAULT 'engineer',
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT rca_work_item_unique UNIQUE (work_item_id)
);

-- Time-series signal aggregations (TimescaleDB hypertable)
CREATE TABLE IF NOT EXISTS signal_metrics (
    time TIMESTAMPTZ NOT NULL,
    component_id VARCHAR(100) NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 0,
    error_rate FLOAT NOT NULL DEFAULT 0.0,
    avg_latency_ms FLOAT,
    p99_latency_ms FLOAT
);

SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_work_items_status ON work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_priority ON work_items(priority);
CREATE INDEX IF NOT EXISTS idx_work_items_component ON work_items(component_id);
CREATE INDEX IF NOT EXISTS idx_work_items_created ON work_items(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signal_metrics_component ON signal_metrics(component_id, time DESC);
