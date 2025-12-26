# Sistema de Follow-Up - Diagramas de Fluxo

**Versão:** 1.0
**Data:** 2025-12-24
**Objetivo:** Visualização dos fluxos do sistema de follow-up

---

## 📊 Diagrama 1: Fluxo Completo de Follow-Up

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PATIENT RESPONSE RECEIVED                        │
│                  (WhatsApp/SMS/Web Interface)                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ResponseProcessor                                │
│  - Extract structured data from message                             │
│  - Analyze sentiment                                                │
│  - Detect medical concerns                                          │
│  - Determine escalation needs                                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│            FollowUpSystemService.process_response_follow_up()       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
            ┌────────────┴──────────────┬─────────────────┬──────────┐
            ▼                           ▼                 ▼          ▼
    ┌──────────────┐          ┌──────────────┐   ┌──────────┐  ┌─────────┐
    │ Context      │          │ Empathy      │   │ Medical  │  │Escalation│
    │ Manager      │          │ Generator    │   │ Concern  │  │ Manager │
    │              │          │              │   │Generator │  │         │
    │ - Update     │          │ - Generate   │   │          │  │- Create │
    │   conversa-  │          │   empathetic │   │- Analyze │  │  alerts │
    │   tion ctx   │          │   response   │   │  concerns│  │- Notify │
    │ - Store in   │          │ - AI-powered │   │- Suggest │  │  staff  │
    │   Redis      │          │   content    │   │  actions │  │         │
    └──────────────┘          └──────┬───────┘   └────┬─────┘  └────┬────┘
                                     │                │             │
                                     ▼                ▼             ▼
                            ┌─────────────────────────────────────────┐
                            │        FollowUpAction Objects           │
                            │  - EMPATHETIC_RESPONSE                  │
                            │  - MEDICAL_CLARIFICATION                │
                            │  - ESCALATION_NOTIFICATION              │
                            │  - PROVIDER_ALERT                       │
                            └─────────────┬───────────────────────────┘
                                          │
                                          ▼
                            ┌─────────────────────────────────────────┐
                            │        ActionScheduler                  │
                            │  - Store action in Redis                │
                            │  - Set TTL (30 days)                    │
                            │  - Queue for execution                  │
                            └─────────────┬───────────────────────────┘
                                          │
                    ┌─────────────────────┴──────────────────┐
                    ▼                                        ▼
        ┌────────────────────────┐              ┌────────────────────────┐
        │ MessageScheduler       │              │ EscalationScheduler    │
        │  - Schedule message    │              │  - Notify providers    │
        │  - Set send time       │              │  - Create tickets      │
        │  - Add to queue        │              │  - Track status        │
        └────────────┬───────────┘              └────────────┬───────────┘
                     │                                       │
                     │         ┌─────────────────────────────┘
                     │         │
                     ▼         ▼
        ┌─────────────────────────────────────────┐
        │         REDIS STORE                     │
        │  Key: follow_up:action:{action_id}      │
        │  TTL: 30 days                           │
        │  Backup: In-Memory Fallback             │
        └─────────────────┬───────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │     CELERY BEAT (every 5 minutes)       │
        │  execute_pending_follow_ups()           │
        └─────────────────┬───────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │       MessageExecutor                   │
        │  - Get actions due for execution        │
        │  - Send messages via UnifiedWhatsApp    │
        │  - Update action status                 │
        │  - Handle failures/retries              │
        └─────────────────┬───────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────────────┐
        │      MESSAGE SENT TO PATIENT            │
        │   (WhatsApp/SMS/Notification)           │
        └─────────────────────────────────────────┘
```

---

## 📊 Diagrama 2: Integração Flow Service ↔ Follow-Up

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CELERY BEAT (Daily 08:00)                        │
│              send_daily_flow_questions()                            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  FlowService.process_daily_flows()                  │
│  - Get all active flow states                                      │
│  - Filter by scheduled time                                         │
│  - Process batch                                                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│            FlowService._process_patient_daily_flow()                │
│                                                                     │
│  1. Get patient flow state                                         │
│  2. Load message template for current day                          │
│  3. Generate AI personalized content                               │
│  4. Calculate optimal send time                                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│      MessageHandler.create_and_schedule_flow_message()              │
│                                                                     │
│  ┌─────────────────────────────────────────────────┐               │
│  │ ✅ NEW: MessageDeduplicationService             │               │
│  │  - Check if similar message sent recently       │               │
│  │  - Block duplicates within 2-hour window        │               │
│  │  - Use content hash for detection               │               │
│  └─────────────────────────────────────────────────┘               │
│                                                                     │
│  1. Create Message object                                          │
│  2. db.flush() → Get message ID                                    │
│  3. Schedule message via MessageScheduler                          │
│  4. db.commit() ONLY if scheduling succeeds                        │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ✅ NEW: FlowService.register_flow_message_for_followup()           │
│                                                                     │
│  Create FollowUpAction:                                            │
│  - Type: CONVERSATION_CONTINUATION                                 │
│  - Scheduled: +24 hours from now                                   │
│  - Parameters: {message_id, flow_day, flow_type}                   │
│  - Purpose: Check if patient responded                             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│          FollowUpSystemService._schedule_action_by_type()           │
│  - Store in Redis                                                   │
│  - Store in in-memory fallback                                     │
│  - Queue for execution                                             │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS PERSISTENCE                              │
│  Key: follow_up:action:{action_id}                                 │
│  TTL: 30 days                                                       │
└─────────────────────────────────────────────────────────────────────┘

                   [24 HOURS LATER]

┌─────────────────────────────────────────────────────────────────────┐
│           CELERY BEAT → execute_pending_follow_ups()                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              MessageExecutor.execute_pending_actions()              │
│                                                                     │
│  IF patient responded:                                             │
│    ✅ Mark action as completed                                      │
│    ✅ No message sent (patient already engaged)                     │
│                                                                     │
│  IF patient NOT responded:                                         │
│    ⚠️  Send gentle reminder                                         │
│    ⚠️  "Olá! Como você está se sentindo hoje?"                      │
│    ⚠️  Update action status                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Diagrama 3: Redis Sync Bidirecional (NOVO)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     SYSTEM STARTUP                                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │    FollowUpSystemService.__init__()        │
        │  - Initialize Redis connection             │
        │  - Initialize in-memory dicts              │
        │    • pending_actions: {}                   │
        │    • active_alerts: {}                     │
        │    • conversation_contexts: {}             │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │  rehydrate_from_redis()                    │
        │  (called on startup & before each task)    │
        │                                            │
        │  FOR EACH action in Redis:                 │
        │    → Convert to FollowUpAction object      │
        │    → Store in pending_actions dict         │
        │                                            │
        │  FOR EACH alert in Redis:                  │
        │    → Convert to EscalationAlert object     │
        │    → Store in active_alerts dict           │
        │                                            │
        │  Redis → In-Memory (LOAD)                  │
        └────────────────┬───────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────┐
        │         NORMAL OPERATION                   │
        │                                            │
        │  New Action Created:                       │
        │    1. Add to pending_actions (memory)      │
        │    2. Store in Redis                       │
        │                                            │
        │  Action Executed:                          │
        │    1. Update in pending_actions            │
        │    2. Update in Redis                      │
        │                                            │
        │  ✅ Both stores stay in sync               │
        └────────────────┬───────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    [Redis Fails]              [Redis Healthy]
            │                         │
            ▼                         │
┌────────────────────────┐            │
│  IN-MEMORY FALLBACK    │            │
│                        │            │
│  New Action:           │            │
│   → Store ONLY in      │            │
│     pending_actions    │            │
│                        │            │
│  ⚠️  Not in Redis!     │            │
│      Data at risk!     │            │
└────────┬───────────────┘            │
         │                            │
         │ [Redis Recovers]           │
         ▼                            ▼
┌─────────────────────────────────────────────┐
│  ✅ NEW: sync_memory_to_redis()              │
│  (called after rehydration)                 │
│                                             │
│  FOR EACH action in pending_actions:        │
│    IF NOT exists in Redis:                  │
│      → Store in Redis                       │
│      → Persist with proper TTL              │
│                                             │
│  FOR EACH alert in active_alerts:           │
│    IF NOT exists in Redis:                  │
│      → Store in Redis                       │
│                                             │
│  In-Memory → Redis (SAVE)                   │
└─────────────────────────────────────────────┘

                  RESULT: No Data Loss!
```

---

## 📊 Diagrama 4: Message Deduplication Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│              Message Ready to Send                                  │
│  - patient_id: 123e4567-e89b-12d3-a456-426614174000                │
│  - message_type: "flow_message"                                    │
│  - content: "Como você está se sentindo hoje?"                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│     MessageDeduplicationService.should_send_message()               │
│                                                                     │
│  Step 1: Generate Content Hash                                     │
│    Input:  "Como você está se sentindo hoje?"                      │
│    Normalize: "como você está se sentindo hoje"                    │
│    Hash: MD5("como...") = "a1b2c3d4e5f6..."                        │
│                                                                     │
│  Step 2: Build Cache Key                                           │
│    Key: "msg_dedup:{patient_id}:flow_message:a1b2c3d4e5f6"         │
│                                                                     │
│  Step 3: Check Redis                                               │
│    await redis.exists(key)                                         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
    [Key EXISTS]               [Key NOT EXISTS]
            │                         │
            ▼                         ▼
┌────────────────────┐    ┌─────────────────────────┐
│  DUPLICATE!        │    │  NEW MESSAGE!           │
│                    │    │                         │
│  Return: False     │    │  1. Set cache key       │
│  (Don't send)      │    │     with TTL (2h)       │
│                    │    │                         │
│  Log:              │    │  2. Return: True        │
│  "Duplicate        │    │     (OK to send)        │
│   detected for     │    │                         │
│   patient {id}"    │    │  3. Message sent        │
└────────────────────┘    └─────────────────────────┘

                        CACHE STRUCTURE:
┌─────────────────────────────────────────────────────────────────────┐
│  Redis Key: msg_dedup:{patient_id}:{msg_type}:{content_hash}       │
│  Value: "1"                                                         │
│  TTL: 7200 seconds (2 hours)                                        │
│                                                                     │
│  After 2 hours → Key expires automatically                         │
│                → Same message can be sent again                     │
└─────────────────────────────────────────────────────────────────────┘

                      EDGE CASES:
┌─────────────────────────────────────────────────────────────────────┐
│  1. Redis Down:                                                     │
│     → Fail OPEN: Return True (allow send)                          │
│     → Better to risk duplicate than miss important message         │
│                                                                     │
│  2. Different Content:                                              │
│     → Different hash → Different cache key → Allowed               │
│     → "Como você está?" vs "Como está se sentindo?" → Both OK     │
│                                                                     │
│  3. Different Patients:                                             │
│     → Different patient_id → Different cache key → Allowed         │
│                                                                     │
│  4. Manual Clear:                                                   │
│     → clear_patient_cache(patient_id)                              │
│     → Deletes all msg_dedup:{patient_id}:* keys                    │
│     → Allows immediate resend                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Diagrama 5: FlowCoordinator Decision Engine

```
┌─────────────────────────────────────────────────────────────────────┐
│              FlowCoordinatorAgent.process_task()                    │
│  Input: {patient_id, current_day, flow_context}                    │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  StateManager.build_context()                       │
│                                                                     │
│  Collect comprehensive patient context:                            │
│   - Patient demographics                                           │
│   - Medical history                                                │
│   - Recent interactions (last 7 days)                              │
│   - Mood indicators                                                │
│   - Adherence metrics                                              │
│   - Risk factors                                                   │
│   - Knowledge graph context                                        │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│           DecisionEngine.analyze_flow_situation()                   │
│                                                                     │
│  Calculate Scores:                                                 │
│   ┌────────────────────────────────────────┐                       │
│   │ Progress Score (0.0 - 1.0):            │                       │
│   │  • Adherence:     30% weight           │                       │
│   │  • Mood trend:    25% weight           │                       │
│   │  • Engagement:    20% weight           │                       │
│   │  • Quiz rate:     25% weight           │                       │
│   └────────────────────────────────────────┘                       │
│                                                                     │
│   ┌────────────────────────────────────────┐                       │
│   │ Risk Level:                            │                       │
│   │  • High:   ≥ 3 risk factors            │                       │
│   │  • Medium: 1-2 risk factors            │                       │
│   │  • Low:    0 risk factors              │                       │
│   └────────────────────────────────────────┘                       │
│                                                                     │
│   ┌────────────────────────────────────────┐                       │
│   │ Engagement Score:                      │                       │
│   │  Interactions / Expected (daily)       │                       │
│   │  Normalized to 0.0 - 1.0               │                       │
│   └────────────────────────────────────────┘                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│            DecisionEngine.make_flow_decision()                      │
│                                                                     │
│  Decision Tree:                                                    │
│                                                                     │
│   IF risk_level == "high":                                         │
│     ├─> requires_consensus?                                        │
│     │   └─> YES: seek_consensus("intervention_decision")           │
│     │         └─> consensus_reached?                               │
│     │             └─> YES: ESCALATE_INTERVENTION                   │
│     └─> NO: ESCALATE_INTERVENTION (direct)                         │
│                                                                     │
│   ELSE IF engagement_score < 0.4:                                  │
│     └─> PERSONALIZE_CONTENT                                        │
│                                                                     │
│   ELSE IF current_day == 45:                                       │
│     ├─> requires_consensus?                                        │
│     │   └─> YES: seek_consensus("phase_transition")                │
│     │         └─> consensus_reached?                               │
│     │             └─> YES: ADVANCE_PHASE                           │
│     └─> NO: ADVANCE_PHASE (direct)                                 │
│                                                                     │
│   ELSE IF progress > 0.7 AND engagement < 0.6:                     │
│     └─> ADJUST_TIMING                                              │
│                                                                     │
│   ELSE IF 0.4 <= progress < 0.7:                                   │
│     └─> PERSONALIZE_CONTENT                                        │
│                                                                     │
│   ELSE:                                                             │
│     └─> CONTINUE_CURRENT                                           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FlowCoordinator.execute_decision()                     │
│                                                                     │
│  Based on decision:                                                │
│                                                                     │
│  ESCALATE_INTERVENTION:                                            │
│    → Create escalation alert                                       │
│    → Notify medical team                                           │
│    → Increase monitoring frequency                                 │
│                                                                     │
│  ADVANCE_PHASE:                                                     │
│    → TransitionHandler.transition_flow_phase()                     │
│    → Update flow_state.flow_type                                   │
│    → Log phase transition                                          │
│                                                                     │
│  ADJUST_TIMING:                                                     │
│    → TransitionHandler.optimize_timing()                           │
│    → Analyze response patterns                                     │
│    → Update preferred send times                                   │
│                                                                     │
│  PERSONALIZE_CONTENT:                                               │
│    → TransitionHandler.personalize_content()                       │
│    → Adjust tone (supportive/encouraging)                          │
│    → Adjust frequency (reduced/normal)                             │
│    → Focus on specific content areas                               │
│                                                                     │
│  CONTINUE_CURRENT:                                                  │
│    → No changes                                                    │
│    → Keep current flow settings                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Diagrama 6: Consensus Mechanism (Multi-Agent)

```
┌─────────────────────────────────────────────────────────────────────┐
│          Critical Decision Required                                 │
│  Example: Escalate intervention for high-risk patient              │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│       DecisionEngine.requires_consensus_decision()                  │
│                                                                     │
│  Critical decisions requiring consensus:                           │
│   • escalate_intervention                                          │
│   • advance_phase                                                   │
│   • pause_flow                                                      │
│                                                                     │
│  IF decision_type in critical_decisions:                           │
│    → Return True (consensus required)                              │
│  ELSE:                                                              │
│    → Return False (agent can decide alone)                         │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│         ConsensusManager.seek_consensus()                           │
│                                                                     │
│  Input:                                                            │
│   • decision_type: "intervention_decision"                         │
│   • context: {patient_id, risk_factors, analysis}                 │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Identify Voting Agents                                 │
│                                                                     │
│  Agents eligible to vote:                                          │
│   1. FlowCoordinatorAgent (initiator)         Weight: 2.0          │
│   2. PatientMonitorAgent                      Weight: 1.5          │
│   3. MedicalAnalysisAgent                     Weight: 2.0          │
│   4. CommunicationAgent                       Weight: 1.0          │
│                                                                     │
│  Total Weight: 6.5                                                 │
│  Consensus Threshold: 70% → Need 4.55 weight                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Collect Votes                                          │
│                                                                     │
│  FOR EACH agent:                                                   │
│    → Send decision proposal                                        │
│    → Agent analyzes context                                        │
│    → Agent returns vote + reasoning                                │
│                                                                     │
│  FlowCoordinatorAgent:                                             │
│    Vote: APPROVE (risk_level == "high")                            │
│    Weight: 2.0                                                     │
│    Reasoning: "3 risk factors detected"                            │
│                                                                     │
│  PatientMonitorAgent:                                              │
│    Vote: APPROVE (engagement dropping)                             │
│    Weight: 1.5                                                     │
│    Reasoning: "Engagement < 0.3 for 3 days"                        │
│                                                                     │
│  MedicalAnalysisAgent:                                             │
│    Vote: APPROVE (symptoms worsening)                              │
│    Weight: 2.0                                                     │
│    Reasoning: "Pain score increasing trend"                        │
│                                                                     │
│  CommunicationAgent:                                               │
│    Vote: ABSTAIN (insufficient data)                               │
│    Weight: 0.0                                                     │
│    Reasoning: "Recent msgs unclear"                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Calculate Consensus                                    │
│                                                                     │
│  Votes:                                                            │
│   APPROVE:  2.0 + 1.5 + 2.0 = 5.5 weight                           │
│   REJECT:   0.0 weight                                             │
│   ABSTAIN:  1.0 weight (not counted)                               │
│                                                                     │
│  Total Voting Weight: 5.5                                          │
│  Required (70%): 4.55                                              │
│                                                                     │
│  Result: 5.5 >= 4.55 → ✅ CONSENSUS REACHED                        │
│                                                                     │
│  Return:                                                           │
│   {                                                                │
│     "consensus_reached": true,                                     │
│     "decision": "APPROVE",                                         │
│     "confidence": 0.85,                                            │
│     "voting_details": [...]                                        │
│   }                                                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Execute Consensus Decision                             │
│                                                                     │
│  IF consensus_reached:                                             │
│    → Return FlowDecision.ESCALATE_INTERVENTION                     │
│    → Log consensus details                                         │
│    → Store voting history                                          │
│  ELSE:                                                              │
│    → Return FlowDecision.CONTINUE_CURRENT                          │
│    → Log rejection reasons                                         │
│    → Notify requester                                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Legenda de Símbolos

```
┌─────┐
│ Box │  = Component/Service/Process
└─────┘

   ↓    = Flow direction

  ✅    = New feature/fix implemented

  ⚠️    = Warning/Attention needed

  ❌    = Bug/Error/Problem

  [X]   = Conditional branch

  {...} = Data structure
```

---

## 📞 Próximos Passos

Para entender completamente o sistema:

1. **Ler:** `FOLLOW_UP_SYSTEM_DEBUG_REPORT.md` (análise completa)
2. **Implementar:** `FOLLOW_UP_QUICK_FIX_GUIDE.md` (correções)
3. **Visualizar:** Este documento (diagramas de fluxo)
4. **Testar:** Executar testes de integração
5. **Monitorar:** Configurar dashboards e alertas

---

**Última Atualização:** 2025-12-24
**Versão:** 1.0
**Status:** ✅ Documentação Completa
