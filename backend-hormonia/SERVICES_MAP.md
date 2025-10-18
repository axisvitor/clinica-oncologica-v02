# 🗺️ Backend Services Map - Guia de Referência Rápida

**Última Atualização:** Janeiro 2025  
**Total de Services:** 127 (em processo de consolidação para ~35)  
**Status:** 🟡 Em Refatoração

---

## 📋 Como Usar Este Mapa

Este documento é seu **guia rápido** para saber **qual service usar** para cada necessidade.

**Regra de Ouro:** Se você está criando um novo service, **PARE** e verifique se já existe algo similar aqui primeiro!

---

## 🎯 Core Services (Use SEMPRE)

### 1. PatientService 🏥
**Arquivo:** `app/services/patient.py`

**Responsável por:**
- ✅ CRUD de pacientes (Create, Read, Update, Delete)
- ✅ Validação de CPF, email, telefone
- ✅ Busca e filtros de pacientes
- ✅ Histórico de alterações de pacientes
- ✅ Integração com flows de onboarding

**NÃO é responsável por:**
- ❌ Envio de mensagens → use `MessageService`
- ❌ Geração de relatórios → use `ReportService`
- ❌ Analytics de pacientes → use `AnalyticsService`

**Uso:**
```python
from app.services.patient import PatientService

service = PatientService(db)
patient = await service.create(patient_data)
patient = await service.get_by_id(patient_id)
patients = await service.list_patients(filters)
```

**Classes principais:**
- `PatientService` - Serviço principal

---

### 2. MessageService 💬
**Arquivo:** `app/services/message.py`

**Responsável por:**
- ✅ CRUD de mensagens
- ✅ Histórico de conversas
- ✅ Status de mensagens (sent, delivered, read, failed)
- ✅ Busca de mensagens

**NÃO é responsável por:**
- ❌ Envio via WhatsApp → use `MessageSender`
- ❌ Templates de mensagens → use `TemplateLoader`
- ❌ Scheduling de mensagens → use `MessageScheduler`

**Uso:**
```python
from app.services.message import MessageService

service = MessageService(db)
message = await service.create_message(message_data)
history = await service.get_conversation_history(patient_id)
```

---

### 3. MessageSender 📤
**Arquivo:** `app/services/message_sender.py` ou `app/services/idempotent_message_sender.py`

**Responsável por:**
- ✅ Envio de mensagens via WhatsApp (Evolution API)
- ✅ Retry logic em caso de falha
- ✅ Idempotência (evitar duplicatas)
- ✅ Queue management

**NÃO é responsável por:**
- ❌ Criação de mensagens no DB → use `MessageService`
- ❌ Conteúdo das mensagens → use `TemplateLoader`

**Uso:**
```python
from app.services.idempotent_message_sender import IdempotentMessageSender

sender = IdempotentMessageSender(db, redis_client)
await sender.send_message(patient_phone, content, message_id)
```

**⚠️ NOTA:** Existe duplicação entre `message_sender.py` e `idempotent_message_sender.py`. Use a versão idempotent.

---

### 4. FlowEngine 🔄
**Arquivo:** `app/services/enhanced_flow_engine.py` (em consolidação)

**Responsável por:**
- ✅ Gerenciamento de flows de onboarding/acompanhamento
- ✅ Transições de estado (boas-vindas → quiz → acompanhamento)
- ✅ Triggers automáticos baseados em tempo/eventos
- ✅ Tracking de progresso de pacientes

**NÃO é responsável por:**
- ❌ Envio de mensagens → use `MessageSender`
- ❌ Analytics de flows → use `FlowAnalytics`

**Uso:**
```python
from app.services.enhanced_flow_engine import get_enhanced_flow_engine, FlowType

engine = get_enhanced_flow_engine(db)
await engine.start_flow(patient_id, FlowType.ONBOARDING)
await engine.progress_flow(patient_id, "welcome_completed")
```

**⚠️ NOTA:** Existem 15+ arquivos de flow. Use APENAS `enhanced_flow_engine.py` por enquanto.

---

### 5. QuizService 📝
**Arquivo:** `app/services/quiz.py`

**Responsável por:**
- ✅ Gerenciamento de templates de quiz
- ✅ Criação de sessões de quiz
- ✅ Registro de respostas
- ✅ Cálculo de scores

**NÃO é responsável por:**
- ❌ Envio de quiz via WhatsApp → use `QuizFlowIntegration`
- ❌ Geração de relatórios → use `QuizReportGenerator`
- ❌ Humanização de perguntas → use AI service

**Uso:**
```python
from app.services.quiz import QuizTemplateService, QuizSessionService

template_service = QuizTemplateService(db)
session_service = QuizSessionService(db)

template = await template_service.get_template("monthly_followup")
session = await session_service.create_session(patient_id, template.id)
```

**⚠️ NOTA:** Existem 12+ arquivos de quiz. Planejamento de consolidação em andamento.

---

### 6. AIService 🤖
**Arquivo:** `app/services/ai.py`

**Responsável por:**
- ✅ Integração com Google Gemini AI
- ✅ Humanização de texto
- ✅ Análise de sentimento
- ✅ Geração de conteúdo personalizado
- ✅ Context building para prompts

**NÃO é responsável por:**
- ❌ Cache de respostas → use `CacheService`
- ❌ Batch processing → use Celery tasks

**Uso:**
```python
from app.services.ai import AIHumanizer, SentimentAnalyzer

humanizer = AIHumanizer()
humanized = await humanizer.humanize(text, patient_context)

analyzer = SentimentAnalyzer()
sentiment = await analyzer.analyze(message_text)
```

**⚠️ NOTA:** Existem 6 arquivos AI. Consolidação planejada para 1 único service.

---

### 7. AuthService 🔐
**Arquivo:** `app/services/auth.py`

**Responsável por:**
- ✅ Login/Logout
- ✅ JWT token generation/validation
- ✅ Firebase authentication integration
- ✅ Session management
- ✅ Password reset

**NÃO é responsável por:**
- ❌ User CRUD → use `UserService`
- ❌ Permissions → use middleware

**Uso:**
```python
from app.services.auth import AuthService

service = AuthService(db)
token = await service.login(email, password)
user = await service.verify_token(token)
await service.logout(user_id)
```

---

### 8. CacheService 💾
**Arquivo:** `app/services/unified_cache.py` (recomendado)

**Responsável por:**
- ✅ Cache de dados em Redis
- ✅ Invalidação de cache
- ✅ TTL management
- ✅ Cache warming

**NÃO é responsável por:**
- ❌ Business logic → isso é responsabilidade dos services

**Uso:**
```python
from app.utils.unified_cache import get_cache, set_cache, invalidate_cache

# Get
data = await get_cache(f"patient:{patient_id}")

# Set
await set_cache(f"patient:{patient_id}", patient_data, ttl=3600)

# Invalidate
await invalidate_cache(f"patient:{patient_id}")
```

**⚠️ NOTA:** Existem 6 implementações de cache. Use `unified_cache` até consolidação.

---

### 9. AnalyticsService 📊
**Arquivo:** `app/services/analytics.py`

**Responsável por:**
- ✅ Métricas de uso do sistema
- ✅ KPIs de engagement de pacientes
- ✅ Relatórios de performance
- ✅ Dashboards de dados

**NÃO é responsável por:**
- ❌ Coleta de métricas técnicas → use `MetricsCollector`
- ❌ Alertas → use `AlertService`

**Uso:**
```python
from app.services.analytics import AnalyticsService

service = AnalyticsService(db)
metrics = await service.get_patient_engagement_metrics(date_range)
kpis = await service.get_system_kpis()
```

---

### 10. ReportService 📄
**Arquivo:** `app/services/report.py`

**Responsável por:**
- ✅ Geração de relatórios médicos
- ✅ PDFs de acompanhamento
- ✅ Exportação de dados
- ✅ Relatórios customizados

**NÃO é responsável por:**
- ❌ Analytics → use `AnalyticsService`
- ❌ Envio de relatórios → use `MessageService`

**Uso:**
```python
from app.services.report import ReportService

service = ReportService(db)
pdf = await service.generate_patient_report(patient_id, report_type)
await service.export_to_csv(data, filename)
```

---

## 🔧 Utility Services (Use quando necessário)

### TemplateLoader 📋
**Arquivo:** `app/services/template_loader.py`

**Responsável por:**
- ✅ Carregamento de templates de mensagens
- ✅ Interpolação de variáveis
- ✅ Templates multi-idioma

**Uso:**
```python
from app.services.template_loader import EnhancedTemplateLoader

loader = EnhancedTemplateLoader()
template = await loader.load_template("welcome_message", patient_data)
```

---

### WebSocketManager 🔌
**Arquivo:** `app/services/enhanced_websocket_manager.py`

**Responsável por:**
- ✅ Gerenciamento de conexões WebSocket
- ✅ Broadcasting de eventos em tempo real
- ✅ Heartbeat/keep-alive

**Uso:**
```python
from app.services.enhanced_websocket_manager import get_websocket_manager

manager = get_websocket_manager()
await manager.broadcast(event_type, data)
await manager.send_to_user(user_id, message)
```

---

### AlertService 🚨
**Arquivo:** `app/services/alert.py`

**Responsável por:**
- ✅ Criação de alertas do sistema
- ✅ Notificações para admins/médicos
- ✅ Escalation de alertas críticos

**Uso:**
```python
from app.services.alert import AlertService

service = AlertService(db)
await service.create_alert("CRITICAL", "System error", details)
```

---

### AuditService 📝
**Arquivo:** `app/services/audit_service.py`

**Responsável por:**
- ✅ Log de ações de usuários
- ✅ Trilha de auditoria
- ✅ Compliance logs (LGPD)

**Uso:**
```python
from app.services.audit_service import AuditService

service = AuditService(db)
await service.log_action(user_id, "patient.update", patient_id, changes)
```

**⚠️ NOTA:** Existem 3 arquivos de audit. Use `audit_service.py`.

---

## 🚫 Services em Depreciação (NÃO USE)

### ❌ ai_cache.py, ai_cache_service.py, ai_redis_cache.py
**Status:** DEPRECATED  
**Use:** `unified_cache.py` ou `cache_service.py`

### ❌ flow.py, flow_core.py, flow_engine.py
**Status:** DEPRECATED  
**Use:** `enhanced_flow_engine.py`

### ❌ websocket_manager.py
**Status:** DEPRECATED  
**Use:** `enhanced_websocket_manager.py`

### ❌ audit_log.py, audit_trail.py
**Status:** DEPRECATED  
**Use:** `audit_service.py`

---

## 🏗️ Arquitetura de Services

### Padrão Recomendado

```python
# 1. Imports
from sqlalchemy.orm import Session
from app.repositories.patient import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate

# 2. Service Class
class PatientService:
    """
    Service para gerenciamento de pacientes.
    
    Responsabilidades:
    - CRUD de pacientes
    - Validações de negócio
    - Orquestração de operações complexas
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.repo = PatientRepository(db)
    
    async def create(self, data: PatientCreate) -> Patient:
        """Cria novo paciente com validações."""
        # Validar
        await self._validate_cpf(data.cpf)
        
        # Criar
        patient = self.repo.create(data.dict())
        
        # Commit
        self.db.commit()
        self.db.refresh(patient)
        
        return patient
    
    async def _validate_cpf(self, cpf: str):
        """Valida CPF (método privado)."""
        # Lógica de validação
        pass
```

### Dependency Injection

```python
# app/dependencies.py
def get_patient_service(db: Session = Depends(get_db)) -> PatientService:
    return PatientService(db)

# No router
@router.post("/patients")
async def create_patient(
    data: PatientCreate,
    service: PatientService = Depends(get_patient_service)
):
    patient = await service.create(data)
    return patient
```

---

## 📊 Services por Domínio

### Domain: Pacientes
- **PatientService** - CRUD e gestão
- **FlowEngine** - Flows de onboarding/acompanhamento
- **ReportService** - Relatórios médicos

### Domain: Comunicação
- **MessageService** - Gerenciamento de mensagens
- **MessageSender** - Envio via WhatsApp
- **TemplateLoader** - Templates de mensagens
- **WebSocketManager** - Real-time updates

### Domain: Quiz/Questionários
- **QuizService** - Gerenciamento de quizzes
- **QuizFlowIntegration** - Integração com flows
- **QuizReportGenerator** - Relatórios de quiz

### Domain: AI/Automação
- **AIService** - IA generativa
- **SentimentAnalyzer** - Análise de sentimento
- **AIHumanizer** - Humanização de texto

### Domain: Autenticação
- **AuthService** - Login/logout
- **FirebaseAuthService** - Firebase integration
- **SessionService** - Gestão de sessões

### Domain: Monitoramento
- **MetricsCollector** - Coleta de métricas
- **AlertService** - Alertas
- **PerformanceMonitoring** - Performance

### Domain: Admin
- **UserAdminService** - Gestão de usuários
- **AdminStatsService** - Estatísticas admin
- **AuditService** - Auditoria

---

## 🚀 Próximos Passos (Consolidação)

### Fase 1: Quick Wins (Semana 1-2)
- [ ] Deletar services duplicados óbvios
- [ ] Documentar top 20 services mais usados
- [ ] Criar guia de migração para deprecated services

### Fase 2: Consolidação (Semana 3-6)
- [ ] AI: 6 → 1 service
- [ ] Cache: 6 → 1 service
- [ ] Flow: 15 → 3 services
- [ ] Quiz: 12 → 3 services
- [ ] Message: 8 → 2 services
- [ ] WebSocket: 5 → 1 service

### Fase 3: Limpeza (Semana 7-8)
- [ ] Remover services não usados
- [ ] Atualizar todos os imports
- [ ] Adicionar testes
- [ ] Atualizar documentação

---

## 📞 Precisa de Ajuda?

### Service não está nesta lista?
1. Verifique se ele é realmente necessário
2. Verifique se pode usar um service existente
3. Consulte o time antes de criar novo service

### Qual service usar?
1. Consulte a seção "Core Services"
2. Verifique a responsabilidade do service
3. Se em dúvida, pergunte no Slack #clinica-dev

### Encontrou um bug?
1. Crie issue no GitHub
2. Marque como bug
3. Referencie este documento

---

**Última Revisão:** Janeiro 2025  
**Próxima Revisão:** Após Fase 1 de Consolidação  
**Mantenedor:** Tech Lead / Arquiteto  
**Versão:** 1.0

---

**💡 Lembre-se:** Menos é mais! Antes de criar um novo service, verifique se já existe algo que atende sua necessidade.