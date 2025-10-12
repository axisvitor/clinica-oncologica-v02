-- Performance indexes for dashboard analytics
-- Run these with CONCURRENTLY to avoid blocking production traffic

-- Index for patient-specific message queries (charts/responses)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_created
ON messages(patient_id, created_at DESC);

-- Index for direction-based message counts (daily/previous period trends)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_direction_created
ON messages(direction, created_at DESC);

-- Composite index for patient + direction queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_direction_created
ON messages(patient_id, direction, created_at DESC);

-- Index for alert status queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_status_created
ON alerts(status, created_at DESC);

-- Index for message status queries (if needed for dashboard)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_status_created
ON messages(status, created_at DESC);

-- Analyze tables after index creation
ANALYZE messages;
ANALYZE alerts;