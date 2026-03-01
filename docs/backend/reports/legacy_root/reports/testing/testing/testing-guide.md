# Guia Completo de Testes - Backend Hormonia

**Versao:** 1.0.0
**Atualizado:** 2025-12-26
**Cobertura Atual:** ~45%
**Meta de Cobertura:** 85%

---

## Indice

1. [Estrutura de Testes](#1-estrutura-de-testes)
2. [Comandos pytest](#2-comandos-pytest)
3. [Marcadores (@pytest.mark.*)](#3-marcadores-pytestmark)
4. [Fixtures Principais](#4-fixtures-principais)
5. [Mocks (Firebase, Redis, Evolution API)](#5-mocks-firebase-redis-evolution-api)
6. [Cobertura de Testes](#6-cobertura-de-testes)
7. [CI/CD Integration](#7-cicd-integration)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Estrutura de Testes

### 1.1 Organizacao dos Diretorios

```
backend-hormonia/tests/
├── api/                          # Testes de endpoints API
│   ├── critical/                 # Testes criticos (auth, quiz, pacientes)
│   │   ├── conftest.py          # Fixtures especificas para testes criticos
│   │   ├── test_auth_login.py   # Testes de autenticacao
│   │   ├── test_quiz_session.py # Testes de sessao de quiz
│   │   └── test_quiz_submit.py  # Testes de envio de quiz
│   └── v2/                       # Testes da API v2 (35+ arquivos)
│       ├── test_patients.py
│       ├── test_enhanced_quiz.py
│       ├── test_flows.py
│       └── ...
├── services/                     # Testes de camada de servicos (45+ arquivos)
│   ├── alerts/
│   ├── audit/
│   ├── flow/
│   ├── patient/
│   └── webhook/
├── repositories/                 # Testes de repositorios (10 arquivos)
│   ├── test_patient.py
│   └── test_patient_lgpd_queries.py
├── domain/                       # Testes de logica de dominio
│   └── patient/
│       └── onboarding/          # Fluxo de onboarding (5 arquivos)
├── integration/                  # Testes de integracao (30+ arquivos)
│   ├── conftest.py              # Fixtures com banco real
│   ├── test_patient_saga.py
│   └── test_circuit_breaker.py
├── security/                     # Testes de seguranca (20 arquivos)
│   ├── test_csrf_comprehensive.py
│   ├── test_cors_comprehensive.py
│   └── test_sql_injection_fixes.py
├── performance/                  # Testes de performance
│   └── test_async_compliance.py
├── e2e/                          # Testes End-to-End (Playwright)
│   ├── test_patient_journey.py
│   └── test_webhook_ai_flow.py
├── unit/                         # Testes unitarios isolados
├── conftest.py                   # Fixtures globais
└── pytest.ini                    # Configuracao do pytest
```

### 1.2 Estatisticas Atuais

| Categoria | Arquivos de Teste | Cobertura |
|-----------|-------------------|-----------|
| **Servicos** | 62 de 252 | 24.6% |
| **Repositorios** | 2 de 21 | 9.5% |
| **API Routers** | 49 de 128 | 38.3% |
| **Dominio** | ~24 de ~40 | ~60% |
| **Total** | ~137 de ~441 | **31.1%** |

### 1.3 Piramide de Testes Recomendada

```
          /\
         /  \
        / E2E \          10% - Testes End-to-End (Playwright)
       /------\
      /        \
     /Integracao\        30% - Testes de Integracao
    /------------\
   /              \
  /   Unitarios    \     60% - Testes Unitarios
 /------------------\
```

---

## 2. Comandos pytest

### 2.1 Comandos Basicos

```bash
# Executar todos os testes (exceto integration por padrao)
pytest

# Executar com output verboso
pytest -v

# Executar testes especificos
pytest tests/api/v2/test_patients.py -v

# Executar funcao especifica
pytest tests/api/v2/test_patients.py::TestPatientCreate::test_create_patient_success -v

# Executar testes em paralelo (4 workers)
pytest -n 4

# Executar com output minimo
pytest -q
```

### 2.2 Filtrar por Marcadores

```bash
# Apenas testes unitarios
pytest -m unit

# Apenas testes de integracao
pytest -m integration

# Apenas testes de seguranca
pytest -m security

# Testes rapidos (excluir lentos)
pytest -m "not slow"

# Testes de API
pytest -m api

# Testes de saga
pytest -m saga

# Testes de Firebase
pytest -m firebase
```

### 2.3 Cobertura de Codigo

```bash
# Executar com relatorio de cobertura
pytest --cov=app --cov-report=term

# Gerar relatorio HTML
pytest --cov=app --cov-report=html

# Gerar relatorio com linhas faltantes
pytest --cov=app --cov-report=term-missing

# Falhar se cobertura abaixo de 70%
pytest --cov=app --cov-fail-under=70

# Relatorio completo (terminal + HTML + XML)
pytest --cov=app \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml
```

### 2.4 Debugging e Troubleshooting

```bash
# Parar no primeiro erro
pytest -x

# Parar apos N erros
pytest --maxfail=3

# Mostrar traceback completo
pytest --tb=long

# Mostrar traceback curto
pytest --tb=short

# Mostrar apenas linha de erro
pytest --tb=line

# Debug com pdb (parar no erro)
pytest --pdb

# Mostrar prints/logs
pytest -s

# Re-executar apenas testes que falharam
pytest --lf

# Re-executar testes que falharam primeiro
pytest --ff

# Executar testes mais lentos primeiro
pytest --durations=10
```

### 2.5 Testes Async

```bash
# Todos os testes async sao suportados automaticamente
# Configurado em pytest.ini: asyncio_mode = auto

# Executar testes async especificos
pytest tests/services/test_unified_whatsapp_service.py -v
```

### 2.6 Testes E2E (Playwright)

```bash
# Executar testes E2E
pytest tests/e2e/ -v

# Com browser visivel
pytest tests/e2e/ --headed

# Browser especifico
pytest tests/e2e/ --browser=chromium
pytest tests/e2e/ --browser=firefox
pytest tests/e2e/ --browser=webkit

# Com screenshots em falha
pytest tests/e2e/ --screenshot=only-on-failure

# Com gravacao de video
pytest tests/e2e/ --video=retain-on-failure
```

---

## 3. Marcadores (@pytest.mark.*)

### 3.1 Marcadores Configurados

```python
# pytest.ini
markers =
    integration: Testes de integracao (requer banco real)
    unit: Testes unitarios (isolados)
    slow: Testes lentos (> 5 segundos)
    api: Testes de endpoints de API
    database: Testes que requerem banco de dados
    saga: Testes de pattern Saga
    firebase: Testes de integracao Firebase
    e2e: Testes End-to-End
    security: Testes de seguranca
    performance: Testes de performance
```

### 3.2 Uso dos Marcadores

```python
import pytest

# Marcar teste como lento
@pytest.mark.slow
def test_batch_processing():
    """Teste que demora mais de 5 segundos."""
    pass

# Marcar teste de integracao
@pytest.mark.integration
def test_real_database_connection():
    """Teste com banco de dados real."""
    pass

# Marcar teste de seguranca
@pytest.mark.security
def test_sql_injection_prevention():
    """Teste de prevencao de SQL Injection."""
    pass

# Marcar teste async
@pytest.mark.asyncio
async def test_async_operation():
    """Teste assincrono."""
    pass

# Combinar marcadores
@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_saga_flow():
    """Teste completo do fluxo saga."""
    pass

# Pular teste condicionalmente
@pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="Redis nao configurado"
)
def test_redis_integration():
    pass

# Pular teste
@pytest.mark.skip(reason="Feature ainda nao implementada")
def test_future_feature():
    pass

# Timeout para teste
@pytest.mark.timeout(60)
def test_with_timeout():
    pass
```

---

## 4. Fixtures Principais

### 4.1 Fixtures de Banco de Dados

```python
# tests/conftest.py

@pytest.fixture(scope="session")
def test_engine():
    """
    Engine de banco de dados para testes (session-scoped).
    Usa SQLite com camada de compatibilidade JSONB/INET.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine):
    """
    Sessao de banco com transacao (function-scoped).
    Rollback automatico apos cada teste.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """TestClient com dependencias injetadas."""
    app.dependency_overrides[get_db] = lambda: db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
```

### 4.2 Fixtures de Autenticacao

```python
@pytest.fixture
def test_user(db_session):
    """Cria usuario de teste com credenciais."""
    from app.models.user import User, UserRole

    user = User(
        email="test@example.com",
        name="Test User",
        password_hash=get_password_hash("Test@1234"),
        role=UserRole.DOCTOR,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def authenticated_client(client, test_user):
    """Client pre-autenticado com token JWT."""
    login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": test_user.email,
            "password": "Test@1234"
        }
    )
    token = login_response.json()["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    return client

@pytest.fixture
def auth_headers(test_user):
    """Headers de autenticacao para requests."""
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}
```

### 4.3 Fixtures de Paciente

```python
@pytest.fixture
def test_patient(db_session, test_user):
    """Cria paciente de teste associado ao medico."""
    from app.models.patient import Patient

    patient = Patient(
        name="Test Patient",
        email="patient@example.com",
        phone="+5511999999999",
        cpf_hash="hashed_cpf_value",
        birth_date=date(1990, 1, 1),
        doctor_id=test_user.id,
        is_active=True
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient

@pytest.fixture
def patient_factory(db_session, test_user):
    """Factory para criar multiplos pacientes."""
    created_patients = []

    def _create_patient(**kwargs):
        defaults = {
            "name": f"Patient {len(created_patients)}",
            "email": f"patient{len(created_patients)}@test.com",
            "phone": f"+551199999{len(created_patients):04d}",
            "doctor_id": test_user.id,
            "is_active": True
        }
        defaults.update(kwargs)

        patient = Patient(**defaults)
        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)
        created_patients.append(patient)
        return patient

    yield _create_patient

    # Cleanup
    for patient in created_patients:
        db_session.delete(patient)
    db_session.commit()
```

### 4.4 Fixtures de Quiz

```python
@pytest.fixture
def quiz_template(db_session):
    """Template de quiz para testes."""
    from app.models.quiz import QuizTemplate

    template = QuizTemplate(
        name="Test Quiz Template",
        description="Template para testes",
        questions=[
            {
                "id": "q1",
                "text": "Como voce esta se sentindo?",
                "type": "scale",
                "options": [1, 2, 3, 4, 5]
            },
            {
                "id": "q2",
                "text": "Descreva seus sintomas",
                "type": "text"
            }
        ],
        is_active=True
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template

@pytest.fixture
def quiz_session(db_session, test_patient, quiz_template):
    """Sessao de quiz ativa para testes."""
    from app.models.quiz import QuizSession

    session = QuizSession(
        patient_id=test_patient.id,
        template_id=quiz_template.id,
        status="active",
        expires_at=now_sao_paulo() + timedelta(hours=24)
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session
```

### 4.5 Fixtures para Integracao

```python
# tests/integration/conftest.py

@pytest.fixture(scope="function")
def real_db_session():
    """
    Sessao com banco PostgreSQL real.
    NAO usa rollback - requer cleanup manual.
    """
    from app.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()

@pytest.fixture
def cleanup_patients(real_db_session):
    """Rastreia e limpa pacientes criados."""
    created_ids = []

    class PatientCleaner:
        def track(self, patient_id):
            created_ids.append(patient_id)

    yield PatientCleaner()

    # Cleanup em ordem reversa (respeita FK)
    for patient_id in reversed(created_ids):
        # Delete cascata de dados relacionados
        real_db_session.execute(
            "DELETE FROM quiz_sessions WHERE patient_id = :id",
            {"id": patient_id}
        )
        real_db_session.execute(
            "DELETE FROM patients WHERE id = :id",
            {"id": patient_id}
        )
    real_db_session.commit()

@pytest.fixture
def unique_phone():
    """Gera telefone unico para evitar conflitos."""
    timestamp = int(datetime.now().timestamp())
    return f"+5511{timestamp % 1000000000:09d}"
```

---

## 5. Mocks (Firebase, Redis, Evolution API)

### 5.1 Mock do Firebase

```python
# tests/conftest.py

@pytest.fixture
def mock_firebase(mocker):
    """Mock completo do Firebase Auth."""
    firebase_mock = mocker.MagicMock()

    # Mock de criacao de usuario
    firebase_mock.create_user.return_value = mocker.MagicMock(
        uid="firebase_uid_123",
        email="test@example.com"
    )

    # Mock de verificacao de token
    firebase_mock.verify_id_token.return_value = {
        "uid": "firebase_uid_123",
        "email": "test@example.com"
    }

    # Mock de obtencao de usuario
    firebase_mock.get_user.return_value = mocker.MagicMock(
        uid="firebase_uid_123",
        email="test@example.com",
        disabled=False
    )

    # Aplicar patch
    mocker.patch(
        "app.services.firebase_auth_service.auth",
        firebase_mock
    )

    return firebase_mock

@pytest.fixture
def mock_firebase_create_failure(mock_firebase):
    """Mock Firebase com falha na criacao."""
    from firebase_admin.exceptions import FirebaseError

    mock_firebase.create_user.side_effect = FirebaseError(
        code="auth/user-not-found",
        message="User not found"
    )
    return mock_firebase

# Uso em teste
def test_patient_creation_with_firebase(mock_firebase, client, auth_headers):
    response = client.post(
        "/api/v2/patients",
        json={"name": "Test", "email": "test@test.com"},
        headers=auth_headers
    )

    assert response.status_code == 201
    mock_firebase.create_user.assert_called_once()
```

### 5.2 Mock do Redis

```python
@pytest.fixture
def mock_redis(mocker):
    """Mock do cliente Redis."""
    redis_mock = mocker.MagicMock()

    # Comportamentos basicos
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.incr.return_value = 1
    redis_mock.expire.return_value = True
    redis_mock.exists.return_value = 0
    redis_mock.ttl.return_value = 3600

    # Mock de pipeline
    pipeline_mock = mocker.MagicMock()
    pipeline_mock.execute.return_value = [True, True]
    redis_mock.pipeline.return_value = pipeline_mock

    # Aplicar patch
    mocker.patch(
        "app.core.cache.redis_client",
        redis_mock
    )

    return redis_mock

@pytest.fixture
def mock_redis_with_data(mock_redis):
    """Mock Redis com dados pre-populados."""
    cache_data = {}

    def mock_get(key):
        return cache_data.get(key)

    def mock_set(key, value, **kwargs):
        cache_data[key] = value
        return True

    mock_redis.get.side_effect = mock_get
    mock_redis.set.side_effect = mock_set

    return mock_redis

# Uso com fakeredis (alternativa)
@pytest.fixture
def fake_redis():
    """Redis fake em memoria."""
    import fakeredis

    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server)

    return client
```

### 5.3 Mock da Evolution API (WhatsApp)

```python
@pytest.fixture
def mock_evolution_api(mocker):
    """Mock da Evolution API para WhatsApp."""
    evolution_mock = mocker.MagicMock()

    # Mock de envio de mensagem
    evolution_mock.send_text.return_value = {
        "key": {
            "remoteJid": "5511999999999@s.whatsapp.net",
            "fromMe": True,
            "id": "MESSAGE_ID_123"
        },
        "status": "PENDING"
    }

    # Mock de envio de template
    evolution_mock.send_template.return_value = {
        "key": {
            "remoteJid": "5511999999999@s.whatsapp.net",
            "fromMe": True,
            "id": "TEMPLATE_MSG_123"
        },
        "status": "PENDING"
    }

    # Mock de status de conexao
    evolution_mock.get_instance_status.return_value = {
        "instance": {
            "instanceName": "test-instance",
            "state": "open"
        }
    }

    mocker.patch(
        "app.services.unified_whatsapp_service.evolution_client",
        evolution_mock
    )

    return evolution_mock

@pytest.fixture
def mock_whatsapp_failure(mock_evolution_api):
    """Mock WhatsApp com falha no envio."""
    from app.services.whatsapp.exceptions import WhatsAppSendError

    mock_evolution_api.send_text.side_effect = WhatsAppSendError(
        "Failed to send message"
    )
    return mock_evolution_api

# Fixture para rastrear mensagens enviadas
@pytest.fixture
def mock_whatsapp_tracker(mock_evolution_api):
    """Mock que rastreia todas as mensagens enviadas."""
    sent_messages = []

    def track_send(*args, **kwargs):
        sent_messages.append({
            "args": args,
            "kwargs": kwargs,
            "timestamp": now_sao_paulo()
        })
        return {"status": "PENDING", "key": {"id": f"MSG_{len(sent_messages)}"}}

    mock_evolution_api.send_text.side_effect = track_send
    mock_evolution_api.sent_messages = sent_messages

    return mock_evolution_api
```

### 5.4 Mock do Gemini AI

```python
@pytest.fixture
def mock_gemini(mocker):
    """Mock da API Gemini para IA."""
    gemini_mock = mocker.MagicMock()

    # Resposta padrao
    gemini_mock.generate_content.return_value = mocker.MagicMock(
        text="Esta e uma resposta gerada pela IA para o paciente.",
        candidates=[{
            "content": {
                "parts": [{"text": "Resposta IA"}]
            }
        }]
    )

    mocker.patch(
        "app.services.ai.ai_service.genai.GenerativeModel",
        return_value=gemini_mock
    )

    return gemini_mock

@pytest.fixture
def mock_gemini_responses(mock_gemini):
    """Mock com respostas configuradas."""
    responses = []

    def setup_response(text):
        mock_gemini.generate_content.return_value.text = text
        responses.append(text)

    mock_gemini.setup_response = setup_response
    mock_gemini.responses = responses

    return mock_gemini
```

### 5.5 Chaos Engineering Mocks

```python
@pytest.fixture
def chaos_monkey(mocker):
    """Mock para injecao de falhas controladas."""

    class ChaosMonkey:
        def __init__(self):
            self.failures = {}
            self.failure_counts = {}

        def fail_next(self, service: str, times: int = 1, exception=None):
            """Configura falha para proximas N chamadas."""
            self.failures[service] = {
                "times": times,
                "exception": exception or Exception(f"{service} failed")
            }
            self.failure_counts[service] = 0

        def should_fail(self, service: str) -> bool:
            """Verifica se deve falhar."""
            if service not in self.failures:
                return False

            self.failure_counts[service] += 1
            return self.failure_counts[service] <= self.failures[service]["times"]

        def get_exception(self, service: str):
            """Retorna excecao configurada."""
            return self.failures[service]["exception"]

    return ChaosMonkey()

# Uso em teste de resiliencia
@pytest.mark.integration
async def test_saga_retry_on_firebase_failure(chaos_monkey, mock_firebase):
    """Testa retry do saga quando Firebase falha."""
    # Configurar 2 falhas antes do sucesso
    chaos_monkey.fail_next("firebase_create_user", times=2)

    # ... executar saga
    # Deve fazer retry e eventualmente ter sucesso
```

---

## 6. Cobertura de Testes

### 6.1 Metricas Atuais

| Camada | Cobertura Atual | Meta | Gap |
|--------|-----------------|------|-----|
| **Repositorios** | 25% | 90% | -65% |
| **Servicos** | 35% | 80% | -45% |
| **API Endpoints** | 60% | 85% | -25% |
| **Logica de Dominio** | 70% | 90% | -20% |
| **Overall** | **45%** | **85%** | **-40%** |

### 6.2 Testes Faltantes por Prioridade

#### Prioridade 1 - CRITICA (Semana 1-2)

**Repositorios (5 arquivos):**
- `test_user.py` - Autenticacao, autorizacao
- `test_patient.py` - Entidade core (melhorar)
- `test_medication.py` - Seguranca medica
- `test_treatment.py` - Registros medicos
- `test_appointment.py` - Agendamento

**Servicos (10 arquivos):**
- `test_firebase_auth_service.py` - Autenticacao
- `test_quiz_service.py` - Fluxo de quiz
- `test_ai_service.py` - Features de IA
- `test_patient_creation_service.py` - Criacao de paciente
- `test_consent_service.py` - LGPD compliance

**APIs (5 arquivos):**
- `test_monthly_quiz_operations.py` - Automacao de quiz
- `test_medications.py` - Seguranca medica
- `test_treatments.py` - Gestao de tratamento
- `test_appointments.py` - Agendamento

#### Prioridade 2 - ALTA (Semana 3-4)

**Repositorios (14 arquivos):**
- `test_message.py`, `test_quiz.py`, `test_notification.py`
- `test_consent.py`, `test_flow.py`, `test_flow_template.py`
- E outros...

**Servicos (15 arquivos):**
- Analytics, reporting, flow engine, audit

### 6.3 Testes Pulados (Skipped)

**Total atual: 56 testes pulados**

| Categoria | Quantidade | Acao |
|-----------|------------|------|
| Dados faltantes (fixtures) | 30 | Criar fixtures adequadas |
| Modelo incorreto | 7 | Refatorar para PatientFlowState |
| Path/Environment | 5 | Corrigir caminhos |
| Redis integration | 4 | Usar mock_redis |
| Implementacao faltante | 1 | Implementar metodo |
| Integracao real | 1 | Manter em suite separada |
| Testes time-dependent | 8 | Usar freezegun |

### 6.4 Comandos de Cobertura

```bash
# Gerar relatorio de cobertura
pytest --cov=app --cov-report=html

# Ver cobertura por modulo
pytest --cov=app --cov-report=term-missing

# Relatorio XML para CI
pytest --cov=app --cov-report=xml:coverage.xml

# Falhar se cobertura < 70%
pytest --cov=app --cov-fail-under=70

# Cobertura apenas de areas criticas
pytest --cov=app.services --cov=app.repositories --cov-report=term
```

---

## 7. CI/CD Integration

### 7.1 GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  unit-tests:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: hormonia_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
        ports:
          - 5432:5432

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run unit tests
        run: pytest -m "not integration" --cov=app --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/hormonia_test
          REDIS_URL: redis://localhost:6379

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: coverage.xml

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Run integration tests
        run: pytest -m integration --tb=short
        env:
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

  security-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Run security tests
        run: pytest -m security -v
```

### 7.2 Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        args: ['-m', 'not integration', '-x', '-q', '--tb=short']
        language: system
        types: [python]
        pass_filenames: false
        stages: [commit]
```

### 7.3 E2E Tests Workflow

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  e2e:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Playwright
        run: |
          pip install pytest-playwright
          playwright install chromium

      - name: Start application
        run: |
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 10

      - name: Run E2E tests
        run: pytest tests/e2e/ --browser=chromium

      - name: Upload artifacts
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-artifacts
          path: test-results/
```

---

## 8. Troubleshooting

### 8.1 Erros Comuns

#### Import Error: Circular Import

**Sintoma:**
```
ImportError: cannot import name 'get_db' from 'app.core.database_config'
```

**Solucao:**
```python
# Verificar caminho correto do import
from app.database import get_db  # Caminho padrao FastAPI
```

#### Erro de Timeout em Testes Async

**Sintoma:**
```
asyncio.TimeoutError: timed out
```

**Solucao:**
```python
# Aumentar timeout no marcador
@pytest.mark.timeout(120)
@pytest.mark.asyncio
async def test_slow_async():
    pass

# Ou via linha de comando
pytest --timeout=120
```

#### Transacao Orfã (Saga Tests)

**Sintoma:**
```
sqlalchemy.exc.InvalidRequestError: This Session's transaction has been rolled back
```

**Solucao:**
```python
# Usar fixture mock_saga_patient ao inves de criar paciente real
def test_saga_operation(mock_saga_patient, db_session):
    # mock_saga_patient ja lida com conflitos de transacao
    pass
```

#### Fixture Nao Encontrada

**Sintoma:**
```
fixture 'authenticated_client' not found
```

**Solucao:**
```bash
# Verificar se conftest.py esta no diretorio correto
# Verificar imports no conftest.py
# Executar pytest com --fixtures para listar disponiveis
pytest --fixtures | grep authenticated
```

### 8.2 Testes Flakey

#### Testes Dependentes de Tempo

```python
# RUIM - dependente de tempo real
def test_token_expiration():
    token = create_token(expires_in=1)
    time.sleep(2)  # Flaky!
    assert is_expired(token)

# BOM - usar freezegun
from freezegun import freeze_time

@freeze_time("2025-01-01 12:00:00")
def test_token_expiration():
    token = create_token(expires_in=3600)

    with freeze_time("2025-01-01 13:00:01"):
        assert is_expired(token)
```

#### Testes com Dados Aleatorios

```python
# RUIM - dados aleatorios sem seed
def test_with_random():
    patient = create_random_patient()  # Nao reproduzivel

# BOM - usar Faker com seed
from faker import Faker

@pytest.fixture
def fake():
    return Faker('pt_BR')
    Faker.seed(12345)  # Seed para reprodutibilidade

def test_with_faker(fake):
    patient_name = fake.name()  # Reproduzivel
```

### 8.3 Debug de Testes

```bash
# Modo debug verbose
pytest tests/api/v2/test_patients.py -vvv -s

# Com breakpoint no erro
pytest --pdb-trace

# Mostrar warnings
pytest -W always

# Mostrar log level DEBUG
pytest --log-cli-level=DEBUG

# Capturar output
pytest --capture=no
```

### 8.4 Performance de Testes

```bash
# Identificar testes mais lentos
pytest --durations=20

# Executar em paralelo
pytest -n auto  # Usa todos os cores

# Profile de testes
pytest --profile
```

### 8.5 Validacao de Ambiente

```bash
# Verificar instalacao de dependencias de teste
pip list | grep pytest

# Verificar configuracao do pytest
pytest --version
pytest --co  # Coletar sem executar

# Verificar banco de dados de teste
python -c "from app.database import engine; print(engine.url)"
```

---

## Anexo A: Templates de Teste

### Template de Teste de Repositorio

```python
"""
Testes para [Model] repository.

Cobertura:
- Operacoes CRUD
- Queries com filtros
- Carregamento de relacionamentos
- Validacao de constraints
- Tratamento de transacoes
"""
import pytest
from uuid import uuid4

from app.models.[model] import [Model]
from app.repositories.[repository] import [Repository]


class Test[Model]Repository:
    """Testes do repositorio [Model]."""

    @pytest.fixture
    def repo(self, db_session):
        """Cria instancia do repositorio."""
        return [Repository](db_session)

    def test_create_success(self, repo, sample_data):
        """Testa criacao com dados validos."""
        result = repo.create(**sample_data)

        assert result.id is not None
        assert result.created_at is not None

    def test_find_by_id(self, repo, sample_data):
        """Testa busca por ID."""
        created = repo.create(**sample_data)
        found = repo.find_by_id(created.id)

        assert found.id == created.id

    def test_update(self, repo, sample_data):
        """Testa atualizacao."""
        created = repo.create(**sample_data)
        updated = repo.update(created.id, name="Updated")

        assert updated.name == "Updated"

    def test_delete(self, repo, sample_data):
        """Testa exclusao (soft delete)."""
        created = repo.create(**sample_data)
        repo.delete(created.id)

        found = repo.find_by_id(created.id)
        assert found.deleted_at is not None
```

### Template de Teste de API

```python
"""
Testes para [Router] API endpoints.

Cobertura:
- Sucesso (200, 201, 204)
- Erros (400, 401, 403, 404, 500)
- Validacao de input
- Autenticacao/autorizacao
"""
import pytest
from fastapi.testclient import TestClient


class Test[Router]API:
    """Testes da API [Router]."""

    def test_requires_authentication(self, client):
        """Endpoint requer autenticacao."""
        response = client.get("/api/v2/[endpoint]")
        assert response.status_code == 401

    def test_list_success(self, authenticated_client):
        """Lista recursos com sucesso."""
        response = authenticated_client.get("/api/v2/[endpoint]")

        assert response.status_code == 200
        assert "items" in response.json()

    def test_create_success(self, authenticated_client, valid_data):
        """Cria recurso com sucesso."""
        response = authenticated_client.post(
            "/api/v2/[endpoint]",
            json=valid_data
        )

        assert response.status_code == 201
        assert "id" in response.json()

    def test_create_validation_error(self, authenticated_client):
        """Retorna erro de validacao."""
        response = authenticated_client.post(
            "/api/v2/[endpoint]",
            json={"invalid": "data"}
        )

        assert response.status_code == 422

    def test_not_found(self, authenticated_client):
        """Retorna 404 para recurso inexistente."""
        response = authenticated_client.get(
            f"/api/v2/[endpoint]/{uuid4()}"
        )

        assert response.status_code == 404
```

---

## Anexo B: Referencias

### Documentacao

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Playwright Python](https://playwright.dev/python/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

### Arquivos de Referencia

- `tests/conftest.py` - Fixtures globais
- `tests/api/critical/conftest.py` - Fixtures avancadas
- `tests/integration/conftest.py` - Fixtures de integracao

---

**Documento consolidado de:** MISSING_TESTS_INVENTORY.md, SKIPPED_TESTS_ANALYSIS.md, TEST_ACTION_PLAN.md, TEST_COVERAGE_ANALYSIS.md, TEST_EXECUTION_REPORT_REAL_ENV.md, TEST_STRATEGY_API_CLIENT.md, TEST_STRATEGY_SUMMARY.md, TEST_SUITE_VALIDATION_REPORT.md, TESTER_AGENT_DELIVERABLES.md, E2E_TEST_GUIDE.md, WEBSOCKET_TESTING_GUIDE.md
