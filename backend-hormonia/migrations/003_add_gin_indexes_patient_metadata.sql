-- ============================================================================
-- Migration: 003_add_gin_indexes_patient_metadata.sql
-- Data: 2025-01-15
-- Descrição: Adiciona índices GIN (Generalized Inverted Index) nas colunas 
--            JSONB da tabela patients para otimizar queries de flags de 
--            paciente (no_ai_messages, critical_condition, etc.)
-- ============================================================================
--
-- OBJETIVO:
-- Melhorar performance de queries JSONB em 10-250x para tabelas grandes
-- Suportar operadores PostgreSQL: @>, ?, ?&, ?| para queries JSONB
--
-- IMPACTO ESPERADO:
-- - 1.000 pacientes:   ~50ms → ~5ms   (10x mais rápido)
-- - 10.000 pacientes:  ~500ms → ~10ms  (50x mais rápido)
-- - 100.000 pacientes: ~5s → ~20ms     (250x mais rápido)
--
-- SEGURANÇA:
-- - Usa CREATE INDEX CONCURRENTLY para não bloquear a tabela
-- - Idempotente (IF NOT EXISTS) - pode ser executado múltiplas vezes
-- - Sem impacto em dados existentes (apenas adiciona índices)
--
-- REQUISITOS:
-- - PostgreSQL 9.4+ (suporte a índices GIN em JSONB)
-- - Permissões de CREATE INDEX na tabela patients
--
-- TEMPO DE EXECUÇÃO ESTIMADO:
-- - Tabela vazia: ~1 segundo
-- - 1.000 registros: ~2-3 segundos
-- - 10.000 registros: ~5-10 segundos
-- - 100.000 registros: ~30-60 segundos
--
-- ESPAÇO EM DISCO:
-- - Aproximadamente 10-20% do tamanho das colunas JSONB
--
-- ============================================================================

-- ----------------------------------------------------------------------------
-- IMPORTANTE: CREATE INDEX CONCURRENTLY não pode ser executado em transação
-- ----------------------------------------------------------------------------
-- Se estiver usando psql, execute este script FORA de um bloco BEGIN/COMMIT
-- Se estiver usando pgAdmin, execute cada comando separadamente
-- ----------------------------------------------------------------------------

-- Índice 1: GIN na coluna 'metadata'
-- Esta coluna é acessada via patient.patient_data no modelo SQLAlchemy
-- Usado para flags de IA: no_ai_messages, critical_condition, etc.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_metadata_gin 
ON patients USING GIN (metadata);

-- Índice 2: GIN na coluna 'patient_metadata' (coluna legacy)
-- Mantida para compatibilidade com código antigo
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_patient_metadata_gin 
ON patients USING GIN (patient_metadata);

-- Adicionar comentários para documentação
COMMENT ON INDEX idx_patients_metadata_gin IS 
'GIN index for JSONB queries on patient metadata (AI flags, preferences, etc.). Created: 2025-01-15';

COMMENT ON INDEX idx_patients_patient_metadata_gin IS 
'GIN index for JSONB queries on legacy patient_metadata column. Created: 2025-01-15';

-- ============================================================================
-- VERIFICAÇÃO PÓS-EXECUÇÃO
-- ============================================================================
-- Execute as queries abaixo para verificar que os índices foram criados:

-- 1. Listar índices criados
-- SELECT indexname, indexdef 
-- FROM pg_indexes 
-- WHERE tablename = 'patients' 
-- AND indexname LIKE '%gin%';

-- 2. Verificar uso do índice em query
-- EXPLAIN ANALYZE 
-- SELECT id, name FROM patients 
-- WHERE metadata @> '{"no_ai_messages": true}';
-- 
-- Resultado esperado: "Index Scan using idx_patients_metadata_gin"

-- 3. Verificar tamanho dos índices
-- SELECT 
--     indexname,
--     pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
-- FROM pg_indexes 
-- WHERE tablename = 'patients' 
-- AND indexname LIKE '%gin%';

-- ============================================================================
-- EXEMPLOS DE USO DOS ÍNDICES
-- ============================================================================

-- Exemplo 1: Buscar pacientes com opt-out de IA (operador @>)
-- SELECT id, name, phone FROM patients 
-- WHERE metadata @> '{"no_ai_messages": true}';

-- Exemplo 2: Buscar pacientes em condição crítica
-- SELECT id, name, phone FROM patients 
-- WHERE metadata @> '{"critical_condition": true}';

-- Exemplo 3: Verificar se campo existe (operador ?)
-- SELECT id, name FROM patients 
-- WHERE metadata ? 'no_ai_messages';

-- Exemplo 4: Verificar múltiplos campos (operador ?&)
-- SELECT id, name FROM patients 
-- WHERE metadata ?& array['no_ai_messages', 'critical_condition'];

-- Exemplo 5: Verificar qualquer um dos campos (operador ?|)
-- SELECT id, name FROM patients 
-- WHERE metadata ?| array['no_ai_messages', 'critical_condition'];

-- ============================================================================
-- ROLLBACK (SE NECESSÁRIO)
-- ============================================================================
-- Para remover os índices criados, execute:
--
-- DROP INDEX CONCURRENTLY IF EXISTS idx_patients_metadata_gin;
-- DROP INDEX CONCURRENTLY IF EXISTS idx_patients_patient_metadata_gin;
--
-- ATENÇÃO: Remover os índices irá degradar a performance de queries JSONB
-- ============================================================================

