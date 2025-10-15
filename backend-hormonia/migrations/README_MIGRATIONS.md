# Migrations SQL - Instruções de Execução

Este diretório contém scripts SQL para alterações de schema do banco de dados que devem ser executados **manualmente** no PostgreSQL.

## 📋 Migrations Disponíveis

| Arquivo | Data | Descrição | Status |
|---------|------|-----------|--------|
| `002_cleanup_test_data.sql` | - | Limpeza de dados de teste | ✅ Executado |
| `003_add_gin_indexes_patient_metadata.sql` | 2025-01-15 | Índices GIN para queries JSONB | ⏳ Pendente |

---

## 🚀 Como Executar Migrations

### Opção 1: Via `psql` (Linha de Comando)

```bash
# 1. Conectar ao banco de dados
psql -h <host> -U <usuario> -d <database>

# 2. Executar o script SQL
\i backend-hormonia/migrations/003_add_gin_indexes_patient_metadata.sql

# 3. Verificar que os índices foram criados
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'patients' 
AND indexname LIKE '%gin%';
```

**Exemplo com variáveis de ambiente:**
```bash
# Definir variáveis de conexão
export PGHOST=your-db-host.aws.com
export PGUSER=postgres
export PGDATABASE=hormonia_db
export PGPASSWORD=your-password

# Executar migration
psql -f backend-hormonia/migrations/003_add_gin_indexes_patient_metadata.sql
```

---

### Opção 2: Via pgAdmin (Interface Gráfica)

1. Abrir pgAdmin e conectar ao banco de dados
2. Navegar até: **Databases → hormonia_db → Schemas → public**
3. Clicar com botão direito em **public** → **Query Tool**
4. Abrir o arquivo `003_add_gin_indexes_patient_metadata.sql`
5. **IMPORTANTE:** Executar cada comando `CREATE INDEX CONCURRENTLY` **separadamente**
   - Selecionar apenas o comando `CREATE INDEX CONCURRENTLY...`
   - Clicar em **Execute/Run** (F5)
   - Aguardar conclusão antes de executar o próximo
6. Executar os comandos `COMMENT ON INDEX` normalmente

**⚠️ ATENÇÃO:** `CREATE INDEX CONCURRENTLY` não pode ser executado dentro de um bloco de transação (BEGIN/COMMIT).

---

### Opção 3: Via Supabase Dashboard (Se aplicável)

1. Acessar o dashboard do Supabase
2. Navegar até **SQL Editor**
3. Criar uma nova query
4. Copiar e colar o conteúdo de `003_add_gin_indexes_patient_metadata.sql`
5. **IMPORTANTE:** Executar cada comando `CREATE INDEX CONCURRENTLY` **separadamente**
6. Clicar em **Run** para executar

---

### Opção 4: Via Railway CLI (Se aplicável)

```bash
# 1. Conectar ao banco de dados via Railway
railway connect

# 2. Executar o script SQL
cat backend-hormonia/migrations/003_add_gin_indexes_patient_metadata.sql | railway run psql
```

---

## ✅ Verificação Pós-Execução

Após executar a migration, verifique que os índices foram criados corretamente:

### 1. Listar Índices GIN Criados

```sql
SELECT 
    indexname, 
    indexdef,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes 
WHERE tablename = 'patients' 
AND indexname LIKE '%gin%';
```

**Resultado Esperado:**
```
indexname                          | indexdef                                      | index_size
-----------------------------------+-----------------------------------------------+------------
idx_patients_metadata_gin          | CREATE INDEX ... USING gin (metadata)         | 128 kB
idx_patients_patient_metadata_gin  | CREATE INDEX ... USING gin (patient_metadata) | 64 kB
```

---

### 2. Verificar Uso do Índice em Query

```sql
EXPLAIN ANALYZE 
SELECT id, name FROM patients 
WHERE metadata @> '{"no_ai_messages": true}';
```

**Resultado Esperado:**
```
Index Scan using idx_patients_metadata_gin on patients  (cost=... rows=... width=...)
  Index Cond: (metadata @> '{"no_ai_messages": true}'::jsonb)
  Planning Time: 0.123 ms
  Execution Time: 2.456 ms
```

Se aparecer **"Seq Scan"** em vez de **"Index Scan"**, o índice não está sendo usado.

---

### 3. Comparar Performance Antes/Depois

```sql
-- Desabilitar índice temporariamente para comparação
SET enable_indexscan = off;

EXPLAIN ANALYZE 
SELECT id, name FROM patients 
WHERE metadata @> '{"no_ai_messages": true}';
-- Anotar o "Execution Time"

-- Reabilitar índice
SET enable_indexscan = on;

EXPLAIN ANALYZE 
SELECT id, name FROM patients 
WHERE metadata @> '{"no_ai_messages": true}';
-- Anotar o "Execution Time" (deve ser muito menor)
```

---

## 🔄 Rollback (Reverter Migration)

Se precisar remover os índices criados:

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_patients_metadata_gin;
DROP INDEX CONCURRENTLY IF EXISTS idx_patients_patient_metadata_gin;
```

**⚠️ ATENÇÃO:** Remover os índices irá degradar a performance de queries JSONB.

---

## 📊 Monitoramento de Performance

### Verificar Uso de Índices em Produção

```sql
-- Estatísticas de uso de índices
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename = 'patients'
AND indexname LIKE '%gin%'
ORDER BY idx_scan DESC;
```

### Verificar Tamanho dos Índices

```sql
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size,
    pg_size_pretty(pg_total_relation_size('patients'::regclass)) as table_size
FROM pg_indexes 
WHERE tablename = 'patients';
```

---

## 🛡️ Boas Práticas

1. **Sempre execute migrations em staging primeiro**
   - Teste a migration em ambiente de desenvolvimento/staging
   - Verifique que os índices foram criados corretamente
   - Meça a performance antes e depois

2. **Use CREATE INDEX CONCURRENTLY em produção**
   - Não bloqueia a tabela durante a criação do índice
   - Permite que a aplicação continue funcionando normalmente
   - Pode levar mais tempo, mas é mais seguro

3. **Execute em horário de baixo tráfego**
   - Mesmo com CONCURRENTLY, há overhead de CPU/IO
   - Prefira executar em horários de menor uso

4. **Monitore o progresso**
   ```sql
   -- Ver índices sendo criados
   SELECT 
       pid,
       now() - pg_stat_activity.query_start AS duration,
       query
   FROM pg_stat_activity
   WHERE query LIKE '%CREATE INDEX%';
   ```

5. **Faça backup antes de alterações críticas**
   ```bash
   pg_dump -h <host> -U <user> -d <database> -t patients > backup_patients.sql
   ```

---

## 📞 Suporte

Se encontrar problemas ao executar as migrations:

1. Verifique as permissões do usuário do banco de dados
2. Verifique se há locks na tabela `patients`
3. Verifique os logs do PostgreSQL para erros
4. Consulte a documentação em `docs/DATABASE_COMPATIBILITY_AI_HUMANIZATION.md`

---

## 📚 Referências

- [PostgreSQL GIN Indexes](https://www.postgresql.org/docs/current/gin.html)
- [CREATE INDEX CONCURRENTLY](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [JSONB Operators](https://www.postgresql.org/docs/current/functions-json.html)

