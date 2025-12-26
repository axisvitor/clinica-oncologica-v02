# Guia de Testes - Sistema Hormonia

**Versao:** 2.0
**Data:** 2025-12-26

---

## Metricas

| Metrica | Valor |
|---------|-------|
| Test Functions | 5,423 |
| Test Classes | 1,278 |
| Fixtures | 782 |
| Conftest Files | 47 |

---

## Estrutura

```
tests/
├── api/                    # Testes de API
│   ├── critical/          # Testes criticos
│   └── v2/                # Endpoints v2
├── integration/           # Integracao
├── security/              # Seguranca
├── unit/                  # Unitarios
│   ├── services/
│   ├── repositories/
│   └── domain/
├── e2e/                   # End-to-End
└── conftest.py            # Fixtures globais
```

---

## Comandos

### Todos os Testes

```bash
cd backend-hormonia
pytest
```

### Com Cobertura

```bash
pytest --cov=app --cov-report=html
```

### Testes Especificos

```bash
# Por marcador
pytest -m security
pytest -m api
pytest -m integration

# Por arquivo
pytest tests/security/test_csrf.py -v

# Por funcao
pytest tests/api/test_patients.py::test_create_patient -v
```

### Testes Paralelos

```bash
pytest -n auto  # Usa todos os cores
pytest -n 4     # 4 workers
```

---

## Marcadores

| Marcador | Descricao |
|----------|-----------|
| @pytest.mark.security | Testes de seguranca |
| @pytest.mark.api | Testes de API |
| @pytest.mark.integration | Integracao |
| @pytest.mark.slow | Testes lentos |
| @pytest.mark.critical | Testes criticos |

---

## Fixtures Principais

### Database

```python
@pytest.fixture
def db_session():
    """Sessao de banco isolada com rollback."""
    ...

@pytest.fixture
def test_patient(db_session):
    """Paciente de teste."""
    return PatientFactory.create()
```

### Auth

```python
@pytest.fixture
def authenticated_client(client):
    """Cliente com sessao autenticada."""
    ...

@pytest.fixture
def admin_user():
    """Usuario admin para testes."""
    ...
```

### Mocks

```python
@pytest.fixture
def mock_firebase():
    """Mock do Firebase Auth."""
    ...

@pytest.fixture
def mock_redis():
    """Mock do Redis."""
    ...
```

---

## Configuracao

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
markers =
    security: Security tests
    api: API tests
    slow: Slow tests
```

### conftest.py

```python
import pytest
from app.main import app

@pytest.fixture(scope="session")
def app_instance():
    return app

@pytest.fixture
def client(app_instance):
    from fastapi.testclient import TestClient
    return TestClient(app_instance)
```

---

## CI/CD

```yaml
# .github/workflows/tests.yml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
    - run: pip install -r requirements-test.txt
    - run: pytest --cov=app -n auto
```

---

**Ultima Atualizacao:** 2025-12-26
