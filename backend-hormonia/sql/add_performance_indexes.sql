-- Performance Indexes for Production Optimization
-- Created: 2025-01-12
-- Purpose: Add indexes for frequently queried alert fields

-- Index for alerts acknowledged status (frequent filter)
CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);

-- Index for quiz session filtering via JSONB expression
-- This allows efficient queries like: WHERE data->>'quiz_session_id' = 'some-uuid'
CREATE INDEX IF NOT EXISTS idx_alerts_quiz_session ON alerts ((data->>'quiz_session_id'));

-- Alternative: GIN index for general JSONB queries (more flexible but larger)
-- Uncomment if you need complex JSONB queries beyond quiz_session_id
-- CREATE INDEX IF NOT EXISTS idx_alerts_data_gin ON alerts USING GIN (data);

-- Index for alerts by patient and acknowledgment status (common query pattern)
CREATE INDEX IF NOT EXISTS idx_alerts_patient_ack ON alerts(patient_id, acknowledged);

-- Index for alerts by severity and creation time (for priority sorting)
CREATE INDEX IF NOT EXISTS idx_alerts_severity_time ON alerts(severity, created_at);

-- Index for recent unacknowledged alerts (dashboard queries)
CREATE INDEX IF NOT EXISTS idx_alerts_recent_unack ON alerts(acknowledged, created_at) 
WHERE acknowledged = false;

-- Analyze tables to update statistics after index creation
ANALYZE alerts;