# 🔄 DIAGRAMA DE FLUXO - JORNADA DO PACIENTE
## Sistema Hormonia - Fluxo End-to-End

```mermaid
graph TD
    A[👨‍⚕️ Médico acessa Interface Web] --> B[📝 Preenche formulário do paciente]
    B --> C[🔐 Validação de dados]
    C --> D{✅ Dados válidos?}
    
    D -->|❌ Não| E[⚠️ Exibe erros de validação]
    E --> B
    
    D -->|✅ Sim| F[🚀 Inicia Saga de Onboarding]
    
    F --> G[📊 STEP 1: Criar Paciente no DB]
    G --> H{💾 Sucesso no DB?}
    
    H -->|❌ Não| I[🔄 Retry Logic]
    I --> G
    
    H -->|✅ Sim| J[🔥 STEP 2: Criar usuário Firebase]
    J --> K{🔐 Firebase OK?}
    
    K -->|❌ Não| L[⚠️ Log error + Continue]
    K -->|✅ Sim| M[⚙️ STEP 3: Inicializar Flow Engine]
    L --> M
    
    M --> N[📱 STEP 4: Enviar mensagem WhatsApp]
    N --> O{📲 WhatsApp enviado?}
    
    O -->|❌ Não| P[📥 Queue para retry]
    O -->|✅ Sim| Q[✅ SAGA COMPLETED]
    
    Q --> R[🔄 Flow Engine ativo]
    R --> S[⏰ Scheduler de mensagens]
    
    S --> T[📅 Mensagem diária]
    S --> U[📋 Quiz semanal]
    S --> V[📊 Avaliação mensal]
    
    T --> W[🤖 AI Humanization]
    U --> W
    V --> W
    
    W --> X[📱 Envio via WhatsApp]
    X --> Y[📈 Analytics & Tracking]
    
    Y --> Z[👨‍⚕️ Dashboard médico atualizado]
    
    %% Webhook flow
    AA[📲 Paciente responde WhatsApp] --> BB[🔗 Webhook Evolution API]
    BB --> CC[🔐 Validação de assinatura]
    CC --> DD[📝 Processamento da resposta]
    DD --> EE[💾 Salvar no banco]
    EE --> FF[🔔 Notificação real-time]
    FF --> Z
    
    %% Quiz flow
    GG[📋 Quiz link gerado] --> HH[🔐 JWT Token]
    HH --> II[📱 Link enviado via WhatsApp]
    II --> JJ[👤 Paciente acessa link]
    JJ --> KK[📝 Responde questionário]
    KK --> LL[💾 Respostas salvas]
    LL --> MM[📊 Analytics processadas]
    MM --> Z
    
    style A fill:#e1f5fe
    style Q fill:#c8e6c9
    style Z fill:#fff3e0
    style BB fill:#f3e5f5
    style GG fill:#e8f5e8
```

## 🏗️ ARQUITETURA DE COMPONENTES

```mermaid
graph LR
    subgraph "Frontend (React/TypeScript)"
        A1[🖥️ Web Interface]
        A2[🔐 Auth Context]
        A3[📊 Dashboard]
        A4[📱 Real-time Updates]
    end
    
    subgraph "Backend (FastAPI/Python)"
        B1[🌐 API Endpoints]
        B2[🔐 Authentication]
        B3[⚙️ Business Logic]
        B4[🔄 Saga Orchestrator]
        B5[🤖 Flow Engine]
        B6[📱 WhatsApp Service]
        B7[📊 Analytics Service]
    end
    
    subgraph "Database Layer"
        C1[🐘 PostgreSQL]
        C2[🔴 Redis Cache]
        C3[📊 Analytics DB]
    end
    
    subgraph "External Services"
        D1[🔥 Firebase Auth]
        D2[📱 Evolution API]
        D3[🤖 AI Services]
        D4[📧 Email Service]
    end
    
    A1 --> B1
    A2 --> B2
    A3 --> B7
    A4 --> B1
    
    B1 --> C1
    B2 --> D1
    B3 --> C1
    B4 --> C2
    B5 --> C2
    B6 --> D2
    B7 --> C3
    
    B5 --> D3
    B6 --> D4
    
    style A1 fill:#e3f2fd
    style B1 fill:#e8f5e8
    style C1 fill:#fff3e0
    style D1 fill:#fce4ec
```

## 📊 FLUXO DE DADOS

```mermaid
sequenceDiagram
    participant M as 👨‍⚕️ Médico
    participant W as 🖥️ Web App
    participant A as 🌐 API
    participant S as 🔄 Saga
    participant D as 💾 Database
    participant F as ⚙️ Flow Engine
    participant WA as 📱 WhatsApp
    participant P as 👤 Paciente
    
    M->>W: Cadastra paciente
    W->>A: POST /api/v1/patients
    A->>S: Inicia saga onboarding
    
    S->>D: 1. Cria paciente
    D-->>S: ✅ Paciente criado
    
    S->>A: 2. Cria usuário Firebase
    A-->>S: ✅ Usuário criado
    
    S->>F: 3. Inicializa flow
    F-->>S: ✅ Flow ativo
    
    S->>WA: 4. Envia boas-vindas
    WA-->>S: ✅ Mensagem enviada
    
    S-->>A: ✅ Saga completa
    A-->>W: ✅ Paciente cadastrado
    W-->>M: ✅ Confirmação
    
    loop Acompanhamento Diário
        F->>WA: Envia mensagem
        WA->>P: 📱 Recebe mensagem
        P->>WA: 💬 Responde
        WA->>A: 🔗 Webhook
        A->>D: 💾 Salva resposta
        A->>W: 🔔 Notificação
        W->>M: 📊 Atualiza dashboard
    end
    
    loop Quiz Mensal
        F->>A: Gera link quiz
        A->>WA: Envia link
        WA->>P: 📋 Recebe quiz
        P->>A: 📝 Responde quiz
        A->>D: 💾 Salva respostas
        A->>W: 📊 Analytics
        W->>M: 📈 Relatório
    end
```

## 🔧 COMPONENTES TÉCNICOS

### 🎯 Core Services
- **PatientService:** CRUD + business logic
- **SagaOrchestrator:** Distributed transactions
- **FlowEngine:** Message automation + AI
- **WhatsAppService:** Evolution API integration
- **QuizService:** Questionnaire management
- **AnalyticsService:** Metrics & reporting

### 🔄 Background Jobs
- **Message Scheduler:** Celery tasks
- **Flow Processor:** Daily/weekly flows
- **Analytics Aggregator:** Metrics calculation
- **Retry Handler:** Failed operations recovery

### 📊 Data Flow
1. **Input:** Web form → API validation
2. **Processing:** Saga pattern → Service layer
3. **Storage:** PostgreSQL + Redis cache
4. **Output:** WhatsApp + Dashboard updates
5. **Feedback:** Webhooks → Real-time updates

### 🔐 Security Layers
- **Authentication:** Firebase + JWT
- **Authorization:** RLS + role-based
- **Rate Limiting:** Redis-based
- **Input Validation:** Pydantic schemas
- **Audit Logging:** Comprehensive tracking

---

**Legenda:**
- 🟢 **Operacional:** Funcionando corretamente
- 🟡 **Atenção:** Necessita monitoramento
- 🔴 **Crítico:** Requer ação imediata
- ⚪ **Planejado:** Desenvolvimento futuro