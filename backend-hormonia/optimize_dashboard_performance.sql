-- Índices otimizados para performance do dashboard
-- Execute com CONCURRENTLY em produção para evitar locks

-- Messages por direção e data (para contagens diárias/trends)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_direction_created_opt
ON messages(direction, created_at DESC);

-- Messages por paciente e data (para gráficos de engajamento)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_created_opt
ON messages(patient_id, created_at DESC);

-- Messages por paciente, direção e data (para filtros combinados)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_patient_direction_created_opt
ON messages(patient_id, direction, created_at DESC);

-- Alerts por status e data (para contagens de alertas pendentes)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_alerts_status_created_opt
ON alerts(status, created_at DESC);

-- Messages por data apenas (para contagens rápidas por período)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_created_date_opt
ON messages(DATE(created_at), created_at DESC);

-- Patients por doctor_id (se não existir)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_doctor_id_opt
ON patients(doctor_id);

-- Analyze tables após criação dos índices
ANALYZE messages;
ANALYZE alerts;
ANALYZE patients;