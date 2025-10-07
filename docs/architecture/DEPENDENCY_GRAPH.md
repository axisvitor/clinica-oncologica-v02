# Flow Engine Dependency Graph

## Legacy FlowEngine Dependencies

```mermaid
graph TB
    subgraph "Legacy Pipeline"
        FE[FlowEngine]
        FE --> FSR[FlowStateRepository]
        FE --> FTS[FlowTemplateService]
        FE --> MS[MessageService]
        FE --> QSS[QuizSessionService]
        FE --> QRS[QuizResponseService]
        FE --> SM[StateMachine]
        FE --> FC[FlowContext]
        FE --> AFEB[AsyncFlowEngineBase]
    end

    subgraph "Callers"
        PS[PatientService] --> FE
        WP[WebhookProcessor] --> FE
        FA[FlowAutomation] --> FE
        SP[ServiceProvider] --> FE
        TSS[ThreadSafeServices] --> FE
    end

    subgraph "Database"
        FSR --> DB[(PostgreSQL)]
        FTS --> DB
        MS --> DB
        QSS --> DB
    end
```

## New FlowEngineIntegrationService Dependencies

```mermaid
graph TB
    subgraph "New Pipeline"
        FEIS[FlowEngineIntegrationService]
        FEIS --> EFE[EnhancedFlowEngine]
        FEIS --> MSCH[MessageScheduler]
        FEIS --> UWS[UnifiedWhatsAppService]
        FEIS --> FAS[FlowAnalyticsService]
        FEIS --> FEB[FlowEventBroadcaster]
        FEIS --> PS_SYNC[PlatformSync]

        EFE --> FCORE[FlowCore]
        EFE --> GC[GeminiClient]
        EFE --> CM[ConversationMemory]

        FCORE --> TL[TemplateLoader]
        FCORE --> FSR2[FlowStateRepository]
    end

    subgraph "Callers"
        API[REST Endpoints] --> FEIS
        SD[ServiceDependencies] --> FEIS
    end

    subgraph "External Services"
        GC --> GEMINI[Google Gemini AI]
        CM --> REDIS[(Redis)]
        PS_SYNC --> PLATFORM[External Platform]
    end

    subgraph "Database"
        FSR2 --> DB[(PostgreSQL)]
        FAS --> DB
    end
```

## Post-Migration Architecture

```mermaid
graph TB
    subgraph "Unified Pipeline"
        FEA[FlowEngineAdapter]
        FEA --> FEIS[FlowEngineIntegrationService]

        FEIS --> EFE[EnhancedFlowEngine]
        FEIS --> MSCH[MessageScheduler]
        FEIS --> UWS[UnifiedWhatsAppService]
        FEIS --> FAS[FlowAnalyticsService]

        EFE --> FCORE[FlowCore]
        EFE --> GC[GeminiClient]
        EFE --> CM[ConversationMemory]
    end

    subgraph "All Callers"
        PS[PatientService] --> FEA
        WP[WebhookProcessor] --> FEA
        FA[FlowAutomation] --> FEA
        API[REST Endpoints] --> FEIS
    end

    subgraph "External Services"
        GC --> GEMINI[Google Gemini AI]
        CM --> REDIS[(Redis)]
    end

    subgraph "Database"
        FCORE --> DB[(PostgreSQL)]
        FAS --> DB
    end

    style FEA fill:#90EE90
    style FEIS fill:#87CEEB
```

## Key Changes

### Removed Components
- ❌ FlowEngine (legacy)
- ❌ FlowContext (legacy, replaced by FlowCore methods)
- ❌ Direct MessageService usage (replaced by MessageScheduler)

### Added Components
- ✅ FlowEngineAdapter (compatibility layer)
- ✅ Unified message scheduling via MessageScheduler
- ✅ AI integration (Gemini, Redis)
- ✅ Analytics and monitoring

### Shared/Retained Components
- ✅ FlowStateRepository
- ✅ FlowCore (base class)
- ✅ Database models
- ✅ Template system
