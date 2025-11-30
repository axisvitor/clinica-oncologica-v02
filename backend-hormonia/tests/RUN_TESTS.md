# Guia de Execução de Testes - LGPD & Idempotency

## 🚀 Comandos Rápidos

### Executar Todos os Testes Novos
```bash
# Todos os testes LGPD e Idempotency
pytest tests/services/test_encryption_lgpd.py \
       tests/api/v2/test_idempotency.py \
       tests/services/test_saga_compensation.py \
       tests/middleware/test_lgpd_middleware.py -v
```

### Executar por Categoria

#### 1. Testes de Criptografia LGPD
```bash
pytest tests/services/test_encryption_lgpd.py -v
```

**Casos de teste**: 25
- CPF encryption/decryption
- Email encryption/decryption
- Phone encryption/decryption
- Hash consistency
- Edge cases

#### 2. Testes de Idempotência
```bash
pytest tests/api/v2/test_idempotency.py -v
```

**Casos de teste**: 18
- Patient creation idempotency
- Update idempotency
- Webhook deduplication
- Cache management

#### 3. Testes de Saga Compensation
```bash
pytest tests/services/test_saga_compensation.py -v
```

**Casos de teste**: 15
- Rollback scenarios
- Error recovery
- State persistence
- Logging and metrics

#### 4. Testes de Middleware LGPD
```bash
pytest tests/middleware/test_lgpd_middleware.py -v
```

**Casos de teste**: 18
- Access logging
- Data deletion
- Data portability
- Consent management

### Executar por Marker

```bash
# Testes LGPD
pytest -m lgpd -v

# Testes de Idempotency
pytest -m idempotency -v

# Testes de Saga
pytest -m saga -v

# Testes de Encryption
pytest -m encryption -v

# Apenas Unit Tests
pytest -m unit -v

# Apenas Integration Tests
pytest -m integration -v

# Excluir testes lentos
pytest -m "not slow" -v
```

### Executar Testes Específicos

```bash
# Uma classe específica
pytest tests/services/test_encryption_lgpd.py::TestCPFEncryption -v

# Um teste específico
pytest tests/services/test_encryption_lgpd.py::TestCPFEncryption::test_cpf_is_encrypted -v

# Múltiplas classes
pytest tests/api/v2/test_idempotency.py::TestPatientCreateIdempotency \
       tests/api/v2/test_idempotency.py::TestWebhookIdempotency -v
```

## 📊 Relatórios de Cobertura

### Cobertura HTML
```bash
# Gerar relatório HTML de cobertura
pytest tests/ --cov=app --cov-report=html --cov-report=term

# Abrir relatório
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Cobertura por Módulo
```bash
# Cobertura do módulo de encryption
pytest tests/services/test_encryption_lgpd.py \
       --cov=app.services.encryption_service \
       --cov-report=term-missing

# Cobertura do módulo de idempotency
pytest tests/api/v2/test_idempotency.py \
       --cov=app.services.idempotency_service \
       --cov=app.middleware.idempotency_middleware \
       --cov-report=term-missing

# Cobertura do saga orchestrator
pytest tests/services/test_saga_compensation.py \
       --cov=app.orchestration.saga_orchestrator \
       --cov-report=term-missing

# Cobertura do middleware LGPD
pytest tests/middleware/test_lgpd_middleware.py \
       --cov=app.middleware.lgpd_middleware \
       --cov-report=term-missing
```

## 🎯 Testes com Filtros

### Por Palavra-chave
```bash
# Todos os testes de encryption
pytest -k "encryption" -v

# Todos os testes de idempotency
pytest -k "idempotency" -v

# Todos os testes de rollback
pytest -k "rollback" -v

# Todos os testes de delete
pytest -k "delete" -v
```

### Por Status
```bash
# Apenas testes que falharam na última execução
pytest --lf

# Apenas testes que falharam primeiro
pytest --ff

# Parar no primeiro erro
pytest -x

# Parar após N falhas
pytest --maxfail=3
```

## 🔍 Debugging

### Modo Verbose
```bash
# Muito verbose
pytest tests/services/test_encryption_lgpd.py -vv

# Com print statements
pytest tests/services/test_encryption_lgpd.py -v -s

# Com locals em falhas
pytest tests/services/test_encryption_lgpd.py -v -l
```

### Modo Debug
```bash
# Entrar em PDB em falhas
pytest tests/services/test_encryption_lgpd.py --pdb

# Entrar em PDB no início de cada teste
pytest tests/services/test_encryption_lgpd.py --trace
```

### Logs Detalhados
```bash
# Mostrar logs em tempo real
pytest tests/services/test_encryption_lgpd.py --log-cli-level=DEBUG

# Logs apenas de warnings
pytest tests/services/test_encryption_lgpd.py --log-cli-level=WARNING
```

## ⚡ Performance

### Execução Paralela
```bash
# Executar com 4 workers paralelos (requer pytest-xdist)
pytest tests/ -n 4

# Auto-detectar número de CPUs
pytest tests/ -n auto
```

### Testes Rápidos
```bash
# Apenas unit tests (mais rápidos)
pytest tests/ -m unit

# Excluir testes lentos
pytest tests/ -m "not slow"

# Com timeout de 5 segundos por teste (requer pytest-timeout)
pytest tests/ --timeout=5
```

## 📈 Análise de Qualidade

### Com Warnings
```bash
# Mostrar todos os warnings
pytest tests/ -v --strict-warnings

# Converter warnings em errors
pytest tests/ -v --strict-config
```

### Verificação de Types
```bash
# Com mypy (se configurado)
pytest tests/ --mypy

# Com type checking
mypy app/ --config-file mypy.ini
```

## 🎨 Formatação de Output

### JSON Output
```bash
# Gerar relatório JSON (requer pytest-json-report)
pytest tests/ --json-report --json-report-file=report.json
```

### JUnit XML
```bash
# Para CI/CD
pytest tests/ --junitxml=junit.xml
```

### HTML Report
```bash
# Relatório HTML (requer pytest-html)
pytest tests/ --html=report.html --self-contained-html
```

## 🔄 CI/CD Integration

### GitHub Actions
```yaml
- name: Run LGPD Tests
  run: |
    pytest tests/services/test_encryption_lgpd.py \
           tests/middleware/test_lgpd_middleware.py \
           --cov=app --cov-report=xml

- name: Run Idempotency Tests
  run: |
    pytest tests/api/v2/test_idempotency.py \
           tests/services/test_saga_compensation.py \
           --cov=app --cov-report=xml
```

### GitLab CI
```yaml
test:lgpd:
  script:
    - pytest tests/services/test_encryption_lgpd.py -v
    - pytest tests/middleware/test_lgpd_middleware.py -v

test:idempotency:
  script:
    - pytest tests/api/v2/test_idempotency.py -v
    - pytest tests/services/test_saga_compensation.py -v
```

## 📝 Exemplos de Uso

### Desenvolvimento Local
```bash
# Durante desenvolvimento - apenas o que mudou
pytest tests/services/test_encryption_lgpd.py -v -s

# Antes de commit
pytest tests/ -v --cov=app --cov-report=term-missing

# Verificação completa
pytest tests/ -v --cov=app --cov-report=html --strict-warnings
```

### Code Review
```bash
# Testes afetados por mudanças em encryption_service.py
pytest tests/services/test_encryption_lgpd.py \
       tests/middleware/test_lgpd_middleware.py -v

# Com cobertura de diff
pytest --cov=app --cov-report=diff:coverage.diff
```

### Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run fast tests
pytest tests/ -m "unit and not slow" -v -x

# Check coverage threshold
pytest tests/ --cov=app --cov-fail-under=80
```

## 🛠️ Troubleshooting

### Problemas Comuns

#### 1. Import Errors
```bash
# Adicionar diretório ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
```

#### 2. Async Tests Failing
```bash
# Verificar modo asyncio
pytest tests/ -v --asyncio-mode=auto
```

#### 3. Database Connection
```bash
# Com variáveis de ambiente
ENCRYPTION_KEY=test_key_32_characters_exactly! \
DATABASE_URL=postgresql://test:test@localhost/test_db \
pytest tests/ -v
```

#### 4. Redis Connection
```bash
# Com Redis mock
REDIS_URL=redis://localhost:6379/0 \
pytest tests/ -v
```

## 📚 Referências

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

---

**Total de Testes**: 76 casos de teste
**Arquivos**: 4 arquivos de teste
**Linhas de Código**: 1,424 linhas
**Cobertura Esperada**: >80%
