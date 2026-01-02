# Guia de Arquivamento de Logs de Auditoria

> **Última Atualização:** 2025-11-26
> **Versão:** 1.0

## Visão Geral

A tabela `audit_logs` cresce continuamente conforme o sistema é usado, registrando todas as operações que envolvem dados de pacientes para conformidade com LGPD e HIPAA. Este documento descreve a política de retenção e procedimentos de arquivamento para manter performance do banco de dados.

## Política de Retenção

### Por Tipo de Log

| Tipo de Log | Retenção Online | Retenção Total | Base Legal |
|-------------|-----------------|----------------|------------|
| **Acesso a dados de paciente** | 90 dias | 6 anos | LGPD Art. 16 |
| **Alterações de dados (CREATE/UPDATE)** | 90 dias | 6 anos | LGPD Art. 16 |
| **Exclusão de dados (DELETE)** | 180 dias | 10 anos | Código Civil Art. 205 |
| **Login/Logout** | 30 dias | 2 anos | Segurança da Informação |
| **Erros de sistema** | 30 dias | 1 ano | Troubleshooting |
| **Tentativas de acesso negado** | 90 dias | 2 anos | Segurança da Informação |

### Definições

- **Retenção Online:** Dados mantidos em `audit_logs` (tabela principal, performance otimizada)
- **Retenção Total:** Dados movidos para `audit_logs_archive` (particionada, consulta menos frequente)
- **Após Retenção Total:** Dados são permanentemente destruídos (export para S3 opcional)

## Estrutura de Tabelas

### Tabela Principal: `audit_logs`

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,     -- CREATE, READ, UPDATE, DELETE
    user_id UUID,
    resource_type VARCHAR(100),           -- patient, user, message, etc
    resource_id UUID,
    changes_before JSONB,
    changes_after JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Índices
    INDEX ix_audit_logs_created_at (created_at),
    INDEX ix_audit_logs_resource (resource_type, resource_id),
    INDEX ix_audit_logs_user (user_id, created_at)
);
```

### Tabela de Arquivo: `audit_logs_archive`

```sql
-- Tabela particionada por mês
CREATE TABLE audit_logs_archive (
    LIKE audit_logs INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Criar partições mensais automaticamente
CREATE TABLE audit_logs_archive_2024_01
    PARTITION OF audit_logs_archive
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE audit_logs_archive_2024_02
    PARTITION OF audit_logs_archive
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- ... e assim por diante
```

### Script de Criação de Partições

```python
# scripts/create_audit_partitions.py
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from app.database import async_session_maker

async def create_partition(year: int, month: int):
    """Create monthly partition for audit_logs_archive."""

    start_date = datetime(year, month, 1)
    end_date = (start_date + timedelta(days=32)).replace(day=1)

    partition_name = f"audit_logs_archive_{year}_{month:02d}"

    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {partition_name}
        PARTITION OF audit_logs_archive
        FOR VALUES FROM ('{start_date.date()}') TO ('{end_date.date()}');
    """

    async with async_session_maker() as db:
        await db.execute(text(create_sql))
        await db.commit()
        print(f"✅ Partição criada: {partition_name}")

async def create_partitions_for_year(year: int):
    """Create all monthly partitions for a year."""
    for month in range(1, 13):
        await create_partition(year, month)

if __name__ == "__main__":
    # Criar partições para 2024 e 2025
    asyncio.run(create_partitions_for_year(2024))
    asyncio.run(create_partitions_for_year(2025))
```

## Procedimento de Arquivamento

### Arquivamento Automático via Cron

#### Configuração do Cron

```bash
# /etc/cron.d/hormonia-audit-archival
# Executar todo dia 1 do mês às 2h da manhã
0 2 1 * * postgres /opt/hormonia/scripts/archive_audit_logs.sh >> /var/log/hormonia/archival.log 2>&1
```

#### Script de Arquivamento

```bash
#!/bin/bash
# /opt/hormonia/scripts/archive_audit_logs.sh

set -e  # Exit on error

# Variáveis
DB_HOST="hormonia-db.cluster-xyz.sa-east-1.rds.amazonaws.com"
DB_NAME="hormonia"
DB_USER="postgres"
CUTOFF_DATE=$(date -d "90 days ago" +%Y-%m-%d)
LOG_FILE="/var/log/hormonia/archival.log"

echo "=== Arquivamento iniciado em $(date -Iseconds) ===" | tee -a $LOG_FILE

# Contar registros a serem arquivados
COUNT=$(psql -h $DB_HOST -U $DB_USER -d $DB_NAME -tA -c "
    SELECT COUNT(*) FROM audit_logs WHERE created_at < '$CUTOFF_DATE';
")

echo "Registros a arquivar: $COUNT" | tee -a $LOG_FILE

if [ "$COUNT" -eq 0 ]; then
    echo "Nenhum registro para arquivar. Saindo." | tee -a $LOG_FILE
    exit 0
fi

# Executar arquivamento em transação
psql -h $DB_HOST -U $DB_USER -d $DB_NAME <<EOF
BEGIN;

-- Mover logs antigos para arquivo
INSERT INTO audit_logs_archive
SELECT * FROM audit_logs
WHERE created_at < '$CUTOFF_DATE';

-- Contar registros inseridos
DO \$\$
DECLARE
    archived_count INTEGER;
BEGIN
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RAISE NOTICE 'Registros arquivados: %', archived_count;
END \$\$;

-- Remover do online
DELETE FROM audit_logs
WHERE created_at < '$CUTOFF_DATE';

COMMIT;

-- Atualizar estatísticas
ANALYZE audit_logs;
ANALYZE audit_logs_archive;

-- Verificar tamanhos
SELECT
    pg_size_pretty(pg_total_relation_size('audit_logs')) as online_size,
    pg_size_pretty(pg_total_relation_size('audit_logs_archive')) as archive_size;
EOF

echo "=== Arquivamento concluído em $(date -Iseconds) ===" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE
```

### Arquivamento Manual (Ad-hoc)

```sql
-- Para arquivar logs de período específico
BEGIN;

-- Verificar antes
SELECT
    COUNT(*) as total_to_archive,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM audit_logs
WHERE created_at < '2024-08-01';

-- Executar arquivamento
INSERT INTO audit_logs_archive
SELECT * FROM audit_logs
WHERE created_at < '2024-08-01';

-- Verificar inserção
SELECT COUNT(*) FROM audit_logs_archive
WHERE created_at < '2024-08-01';

-- Se OK, deletar do online
DELETE FROM audit_logs
WHERE created_at < '2024-08-01';

COMMIT;
```

## Consulta de Logs

### Consulta Unificada (Online + Arquivo)

```sql
-- Buscar logs em ambas tabelas
SELECT * FROM (
    SELECT * FROM audit_logs WHERE patient_id = '550e8400-e29b-41d4-a716-446655440000'
    UNION ALL
    SELECT * FROM audit_logs_archive WHERE patient_id = '550e8400-e29b-41d4-a716-446655440000'
) combined_logs
ORDER BY created_at DESC;
```

### View para Simplificar Consultas

```sql
-- Criar view unificada
CREATE OR REPLACE VIEW v_audit_logs_complete AS
SELECT * FROM audit_logs
UNION ALL
SELECT * FROM audit_logs_archive;

-- Usar view
SELECT * FROM v_audit_logs_complete
WHERE resource_type = 'patient'
  AND created_at >= '2024-01-01'
ORDER BY created_at DESC;
```

### Consulta por Período Específico

```sql
-- Logs do último ano (otimizado)
SELECT
    event_type,
    resource_type,
    COUNT(*) as total
FROM v_audit_logs_complete
WHERE created_at >= NOW() - INTERVAL '1 year'
GROUP BY event_type, resource_type
ORDER BY total DESC;
```

## Backup e Destruição

### Backup Antes de Destruir (6+ anos)

#### Script de Backup e Destruição

```bash
#!/bin/bash
# /opt/hormonia/scripts/destroy_old_audit_logs.sh

YEAR_TO_DESTROY=2018
BACKUP_DIR="/opt/hormonia/backups/audit"
S3_BUCKET="s3://hormonia-backups/audit-logs"

mkdir -p $BACKUP_DIR

echo "=== Destruindo logs de $YEAR_TO_DESTROY ==="

# 1. Exportar para arquivo
pg_dump -h $DB_HOST -U $DB_USER -d $DB_NAME \
    -t "audit_logs_archive_${YEAR_TO_DESTROY}_*" \
    > $BACKUP_DIR/audit_${YEAR_TO_DESTROY}.sql

# 2. Comprimir
gzip $BACKUP_DIR/audit_${YEAR_TO_DESTROY}.sql

# 3. Upload para S3
aws s3 cp $BACKUP_DIR/audit_${YEAR_TO_DESTROY}.sql.gz $S3_BUCKET/

# 4. Verificar upload
if aws s3 ls $S3_BUCKET/audit_${YEAR_TO_DESTROY}.sql.gz; then
    echo "✅ Backup confirmado no S3"

    # 5. Destruir partições
    for month in {01..12}; do
        partition="audit_logs_archive_${YEAR_TO_DESTROY}_${month}"
        psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "DROP TABLE IF EXISTS $partition;"
        echo "Partição destruída: $partition"
    done

    echo "✅ Logs de $YEAR_TO_DESTROY destruídos"
else
    echo "❌ ERRO: Backup não encontrado no S3. Abortando destruição."
    exit 1
fi
```

### Cronograma de Destruição

| Ano | Data de Destruição | Arquivo de Backup |
|-----|-------------------|-------------------|
| 2018 | 2025-01-01 | `s3://hormonia-backups/audit-logs/audit_2018.sql.gz` |
| 2019 | 2026-01-01 | `s3://hormonia-backups/audit-logs/audit_2019.sql.gz` |
| 2020 | 2027-01-01 | `s3://hormonia-backups/audit-logs/audit_2020.sql.gz` |

## Monitoramento

### Métricas para Alertas

| Métrica | Threshold | Ação |
|---------|-----------|------|
| **Tamanho `audit_logs`** | > 10 GB | Executar archival |
| **Registros por dia** | > 100k | Revisar verbosidade de logs |
| **Queries lentas (audit_logs)** | > 5 segundos | Adicionar/otimizar indexes |
| **Falha no cron de archival** | 2 execuções consecutivas | Notificar DevOps |
| **Tamanho `audit_logs_archive`** | > 100 GB | Planejar destruição de partições antigas |

### Query de Monitoramento

```sql
-- Monitoramento diário
SELECT
    'audit_logs' as table_name,
    pg_size_pretty(pg_total_relation_size('audit_logs')) as size,
    (SELECT COUNT(*) FROM audit_logs) as row_count,
    (SELECT MIN(created_at) FROM audit_logs) as oldest_record,
    (SELECT MAX(created_at) FROM audit_logs) as newest_record
UNION ALL
SELECT
    'audit_logs_archive' as table_name,
    pg_size_pretty(pg_total_relation_size('audit_logs_archive')) as size,
    (SELECT COUNT(*) FROM audit_logs_archive) as row_count,
    (SELECT MIN(created_at) FROM audit_logs_archive) as oldest_record,
    (SELECT MAX(created_at) FROM audit_logs_archive) as newest_record;
```

### Script de Monitoramento (Python)

```python
# scripts/monitor_audit_logs.py
import asyncio
from sqlalchemy import text, func
from app.database import async_session_maker

async def monitor_audit_logs():
    """Monitor audit logs size and performance."""

    async with async_session_maker() as db:
        # Tamanhos
        sizes = await db.execute(text("""
            SELECT
                pg_size_pretty(pg_total_relation_size('audit_logs')) as online_size,
                pg_size_pretty(pg_total_relation_size('audit_logs_archive')) as archive_size
        """))
        online_size, archive_size = sizes.fetchone()

        # Contagens
        online_count = await db.scalar(
            text("SELECT COUNT(*) FROM audit_logs")
        )
        archive_count = await db.scalar(
            text("SELECT COUNT(*) FROM audit_logs_archive")
        )

        # Período online
        period = await db.execute(text("""
            SELECT
                MIN(created_at) as oldest,
                MAX(created_at) as newest
            FROM audit_logs
        """))
        oldest, newest = period.fetchone()

        # Relatório
        print("=== AUDIT LOGS MONITORING ===")
        print(f"Online:")
        print(f"  Size: {online_size}")
        print(f"  Count: {online_count:,}")
        print(f"  Period: {oldest} to {newest}")
        print(f"\nArchive:")
        print(f"  Size: {archive_size}")
        print(f"  Count: {archive_count:,}")

        # Alertas
        if online_count > 1_000_000:
            print("\n⚠️  ALERTA: Mais de 1M registros online. Considerar archival.")

        if (newest - oldest).days > 120:
            print("\n⚠️  ALERTA: Logs online com mais de 120 dias. Executar archival.")

if __name__ == "__main__":
    asyncio.run(monitor_audit_logs())
```

## Recuperação de Dados Arquivados

### Restaurar Logs de S3

```bash
# Download do backup
aws s3 cp s3://hormonia-backups/audit-logs/audit_2018.sql.gz .

# Descomprimir
gunzip audit_2018.sql.gz

# Restaurar em banco temporário
createdb hormonia_audit_2018
psql -d hormonia_audit_2018 -f audit_2018.sql

# Consultar
psql -d hormonia_audit_2018 -c "
    SELECT * FROM audit_logs_archive_2018_06
    WHERE resource_id = '550e8400-e29b-41d4-a716-446655440000'
    ORDER BY created_at DESC;
"
```

### Mover de Volta para Produção (se necessário)

```sql
-- Conectar bancos via postgres_fdw
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

CREATE SERVER audit_2018_server
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host 'localhost', dbname 'hormonia_audit_2018', port '5432');

CREATE USER MAPPING FOR current_user
    SERVER audit_2018_server
    OPTIONS (user 'postgres', password 'password');

-- Consultar remotamente
SELECT * FROM dblink('audit_2018_server',
    'SELECT * FROM audit_logs_archive_2018_06'
) AS t(id UUID, event_type VARCHAR, ...);
```

## Checklist de Arquivamento Mensal

### Executado Automaticamente (Cron)
- [ ] Identificar logs com mais de 90 dias
- [ ] Mover para `audit_logs_archive`
- [ ] Deletar de `audit_logs`
- [ ] Atualizar estatísticas (ANALYZE)
- [ ] Registrar log de execução

### Verificação Manual (Primeiro dia útil do mês)
- [ ] Verificar execução do cron
- [ ] Conferir tamanhos das tabelas
- [ ] Validar contagens de registros
- [ ] Revisar logs de erro
- [ ] Atualizar dashboard de monitoramento

### Trimestral
- [ ] Criar partições para próximos 3 meses
- [ ] Revisar política de retenção
- [ ] Testar restauração de backup

### Anual
- [ ] Destruir logs com 6+ anos
- [ ] Exportar backup para S3 antes
- [ ] Atualizar documentação
- [ ] Auditar acesso a logs arquivados

## Contato e Suporte

**DBA (Database Administrator):**
- Email: dba@hormonia.com.br
- Slack: #database-ops

**DevOps:**
- Email: devops@hormonia.com.br
- Slack: #devops-alerts

**Emergência 24/7:**
- Telefone: +55 (11) XXXX-XXXX
- PagerDuty: hormonia-database

---

**Última Revisão:** 2025-11-26
**Próxima Revisão:** 2026-02-26
**Responsável:** Equipe de Infraestrutura de Dados
