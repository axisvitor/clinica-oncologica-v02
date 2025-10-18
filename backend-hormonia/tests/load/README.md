# 🚀 Testes de Carga - Sistema Hormonia

Testes de performance e escalabilidade usando **Locust**.

## 📋 Índice

- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Arquivos](#arquivos)
- [Execução](#execução)
- [Cenários Disponíveis](#cenários-disponíveis)
- [Métricas Alvo](#métricas-alvo)
- [Análise de Resultados](#análise-de-resultados)
- [Troubleshooting](#troubleshooting)

---

## 🔧 Pré-requisitos

- Python 3.11+
- Locust 2.x
- Sistema Hormonia rodando (backend)
- Banco de dados com dados de teste
- Redis ativo

## 📦 Instalação

```bash
# Instalar Locust
pip install locust

# Verificar instalação
locust --version
```

## 📁 Arquivos

```
tests/load/
├── README.md           # Este arquivo
├── locustfile.py       # Testes gerais de carga
├── scenarios.py        # Cenários específicos
└── results/            # Resultados dos testes (gerado)
```

## 🚀 Execução

### Modo Interativo (com UI Web)

```bash
# Básico
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Abrir navegador em http://localhost:8089
# Configurar número de usuários e taxa de spawn
```

### Modo Headless (sem UI)

```bash
# 100 usuários, spawn rate 10/s, duração 5 minutos
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  -u 100 \
  -r 10 \
  -t 5m \
  --headless
```

### Com Exportação de Resultados

```bash
# Exportar para CSV
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  -u 100 \
  -r 10 \
  -t 5m \
  --headless \
  --csv=results/test_$(date +%Y%m%d_%H%M%S)

# Exportar para HTML
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  -u 100 \
  -r 10 \
  -t 5m \
  --headless \
  --html=results/report_$(date +%Y%m%d_%H%M%S).html
```

## 🎯 Cenários Disponíveis

### Cenário 1: Cadastro Massivo de Pacientes

**Objetivo**: Validar cadastro simultâneo de 100 pacientes

```bash
locust -f tests/load/scenarios.py \
  Scenario1MassivePatientRegistration \
  --host=http://localhost:8000 \
  -u 100 \
  -r 10 \
  -t 3m \
  --headless \
  --csv=results/scenario1
```

**Valida**:
- Saga Pattern funcionando
- Pool de conexões adequado
- Transações distribuídas

### Cenário 2: Processamento de Mensagens

**Objetivo**: Validar agendamento de 1000 mensagens

```bash
locust -f tests/load/scenarios.py \
  Scenario2MessageProcessing \
  --host=http://localhost:8000 \
  -u 50 \
  -r 5 \
  -t 5m \
  --headless \
  --csv=results/scenario2
```

**Valida**:
- Idempotência (sem duplicatas)
- Rate limiting
- Fila de mensagens

### Cenário 3: Flood de Webhooks

**Objetivo**: Validar processamento de 500 webhooks simultâneos

```bash
locust -f tests/load/scenarios.py \
  Scenario3WebhookFlood \
  --host=http://localhost:8000 \
  -u 500 \
  -r 50 \
  -t 2m \
  --headless \
  --csv=results/scenario3
```

**Valida**:
- HMAC validation
- Processamento assíncrono
- DLQ funcionando

### Cenário 4: Dashboard sob Carga

**Objetivo**: Validar dashboard com 200 médicos simultâneos

```bash
locust -f tests/load/scenarios.py \
  Scenario4DashboardLoad \
  --host=http://localhost:8000 \
  -u 200 \
  -r 20 \
  -t 5m \
  --headless \
  --csv=results/scenario4
```

**Valida**:
- Cache Redis funcionando
- Queries otimizadas (sem N+1)
- Eager loading

### Cenário 5: Stress Test

**Objetivo**: Encontrar limites do sistema

```bash
# ATENÇÃO: Pode derrubar o sistema!
locust -f tests/load/scenarios.py \
  Scenario5StressTest \
  --host=http://localhost:8000 \
  -u 1000 \
  -r 100 \
  --headless \
  --csv=results/scenario5
```

**Valida**:
- Limite máximo de throughput
- Comportamento sob stress
- Degradação graciosa

## 📊 Métricas Alvo

### Obrigatórias (Devem Passar)

| Métrica | Alvo | Crítico |
|---------|------|---------|
| P95 Response Time | < 500ms | < 1000ms |
| Taxa de Erro | < 0.1% | < 1% |
| Pool Conexões | < 80% | < 95% |
| Redis Memory | < 70% | < 90% |
| CPU | < 70% | < 90% |

### Desejáveis

| Métrica | Alvo |
|---------|------|
| P50 Response Time | < 200ms |
| P99 Response Time | < 1000ms |
| Throughput | > 100 RPS |
| Concorrência | > 500 usuários |

## 📈 Análise de Resultados

### Arquivos Gerados

Após execução com `--csv=results/test`:

```
results/
├── test_stats.csv           # Estatísticas de requisições
├── test_stats_history.csv   # Histórico temporal
├── test_failures.csv        # Falhas detalhadas
└── test.html                # Relatório visual (se --html)
```

### Analisando CSV

```bash
# Ver estatísticas gerais
cat results/test_stats.csv | column -t -s ','

# Ver P95 por endpoint
awk -F',' 'NR>1 {print $1, $10}' results/test_stats.csv | sort -k2 -n

# Ver taxa de erro
awk -F',' 'NR>1 {print $1, $3/$2*100"%"}' results/test_stats.csv
```

### Visualização com Grafana

Se tiver Prometheus+Grafana configurado:

```bash
# Executar teste enquanto monitora Grafana
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  -u 100 -r 10 -t 5m --headless

# Queries úteis no Grafana:
# - rate(http_requests_total[1m])
# - histogram_quantile(0.95, http_request_duration_seconds_bucket)
# - pg_stat_activity_count
# - redis_memory_used_bytes
```

## 🔍 Monitoramento Durante Testes

### Backend Metrics

```bash
# Terminal 1: Logs do backend
tail -f logs/app.log

# Terminal 2: Métricas Prometheus
curl http://localhost:8000/metrics | grep -E "(http_|db_|redis_)"

# Terminal 3: PostgreSQL
psql -U postgres -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# Terminal 4: Redis
redis-cli INFO memory | grep used_memory_human
redis-cli INFO stats | grep total_connections_received
```

### System Resources

```bash
# CPU e Memória
htop

# Network
iftop

# Disk I/O
iotop
```

## 🐛 Troubleshooting

### Erro: "Max retries exceeded"

**Causa**: Pool de conexões esgotado

**Solução**:
```python
# Aumentar pool no .env
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

### Erro: "Redis connection timeout"

**Causa**: Redis sobrecarregado

**Solução**:
```bash
# Aumentar maxclients no Redis
redis-cli CONFIG SET maxclients 10000

# Verificar conexões ativas
redis-cli CLIENT LIST | wc -l
```

### P95 > 1000ms

**Causa**: Queries lentas ou N+1

**Solução**:
```bash
# Identificar queries lentas
tail -f logs/app.log | grep "slow query"

# Analisar com pgBadger
pgbadger /var/log/postgresql/postgresql.log -o report.html
```

### Taxa de Erro > 5%

**Causa**: Sistema colapsando

**Solução**:
1. Reduzir número de usuários
2. Verificar logs de erro
3. Identificar gargalo (DB, Redis, CPU)
4. Escalar recursos ou otimizar código

## 📝 Checklist de Teste

Antes de executar testes de carga:

- [ ] Backup do banco de dados
- [ ] Sistema em ambiente de teste (não produção!)
- [ ] Dados de teste carregados
- [ ] Monitoramento ativo (Prometheus/Grafana)
- [ ] Logs habilitados
- [ ] Recursos de infra adequados

Durante os testes:

- [ ] Monitorar CPU/Memória/Disk
- [ ] Observar logs de erro
- [ ] Verificar métricas do Locust em tempo real
- [ ] Anotar comportamentos anormais

Após os testes:

- [ ] Analisar resultados CSV/HTML
- [ ] Comparar com métricas alvo
- [ ] Identificar gargalos
- [ ] Documentar findings
- [ ] Criar issues para otimizações

## 🎓 Boas Práticas

### Antes de Testar

1. **Isolar Ambiente**: Use ambiente dedicado, nunca produção
2. **Dados Realistas**: Use volume similar ao esperado em produção
3. **Monitoramento**: Configure observability antes de testar
4. **Baseline**: Execute teste inicial para ter baseline

### Durante Teste

1. **Aumentar Gradualmente**: Não comece com carga máxima
2. **Observar Constantemente**: Monitore métricas em tempo real
3. **Documentar**: Anote tudo que observar
4. **Parar se Necessário**: Se sistema colapsar, pare o teste

### Após Teste

1. **Analisar Completamente**: Não olhe apenas P95 e erro rate
2. **Correlacionar Métricas**: Backend + DB + Redis + System
3. **Priorizar Fixes**: Foque nos gargalos críticos primeiro
4. **Re-testar**: Após otimizações, teste novamente

## 🔗 Links Úteis

- [Locust Documentation](https://docs.locust.io/)
- [Prometheus Queries](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [PostgreSQL Performance](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Redis Performance](https://redis.io/docs/management/optimization/)

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs: `logs/app.log`
2. Consulte este README
3. Abra issue no repositório
4. Contate o time de DevOps

---

**Última Atualização**: Janeiro 2025  
**Versão**: 1.0.0