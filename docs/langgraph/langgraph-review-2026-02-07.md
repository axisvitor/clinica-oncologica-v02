# LangGraph Technical Review - 2026-02-07 (LG5)

## 1) Scope and Context
- Version: `v2026.02.07`
- Scope reviewed:
  - `backend-hormonia/app/ai/langgraph/`
  - Direct LangGraph integrations in backend services and agents
  - LangGraph-focused tests under `backend-hormonia/tests/`
- Planning context:
  - `LG2`, `LG3`, `LG4`, `LG5` and `LG6` are tracked in `final-plan.md`.

## 2) Executive Summary
- Architecture is clear and centralized: graph builders and nodes are consolidated in `backend-hormonia/app/ai/langgraph/graphs.py` and `backend-hormonia/app/ai/langgraph/nodes.py`.
- Hardening is partially in place: per-graph runtime wrappers exist (`backend-hormonia/app/ai/langgraph/runtime.py:23`, `backend-hormonia/app/ai/langgraph/runtime.py:47`) and are wired into graph compilation/instrumentation (`backend-hormonia/app/ai/langgraph/graphs.py:30`, `backend-hormonia/app/ai/langgraph/graphs.py:37`, `backend-hormonia/app/ai/langgraph/consensus.py:21`, `backend-hormonia/app/ai/langgraph/consensus.py:266`).
- Highest residual risks are operational consistency and test coverage gaps: mixed `thread_id` usage across call sites and side-effect-heavy nodes with múltiplos commits no caminho do fluxo.

## 3) Architecture Map
```text
[Service/Agent callers]
  |-- SequentialMessageHandler -> flow_message_graph / flow_response_graph
  |     (backend-hormonia/app/services/flow/sequential_message_handler.py:111, :142)
  |
  |-- GeminiClient + AI services -> humanization/sentiment/generation/etc graphs
  |     (backend-hormonia/app/ai/client.py:582, :639, :683, :726)
  |
  |-- ConsensusManager -> consensus_graph
        (backend-hormonia/app/agents/patient/flow_coordinator/consensus_manager.py:57)

[Graph factories]
  backend-hormonia/app/ai/langgraph/graphs.py
  backend-hormonia/app/ai/langgraph/consensus.py
    -> runtime.compile_graph + runtime.instrument_node
       (backend-hormonia/app/ai/langgraph/runtime.py:35, :47)

[Nodes]
  backend-hormonia/app/ai/langgraph/nodes.py
    -> DB + flow handler methods + Gemini client calls

[State contracts]
  backend-hormonia/app/ai/langgraph/state.py
  backend-hormonia/app/ai/langgraph/ai_state.py
```

## 4) Evidence by File
| File | Evidence |
|---|---|
| `backend-hormonia/app/ai/langgraph/graphs.py` | Unified flow + AI graph builders with cached compiled instances (`:75`, `:116`, `:140`, `:163`, `:186`, `:209`, `:232`); node instrumentation wrapper applied via `_add_node` (`:33`); runtime compiler abstraction used (`:37`). |
| `backend-hormonia/app/ai/langgraph/consensus.py` | Consensus graph has explicit loop routing and compile through runtime (`:201`, `:215`, `:266`); defaults include `max_poll_attempts=1` (`:61`). |
| `backend-hormonia/app/ai/langgraph/runtime.py` | Per-graph in-memory checkpointer cache (`:23`, `:27`, `:31`); node start/end/error logging with duration (`:59`, `:67`, `:76`). |
| `backend-hormonia/app/ai/langgraph/state.py` | Runtime validator `validate_flow_message_state` com checagem de chaves obrigatórias e normalização de UUID/tipos (`:51`). |
| `backend-hormonia/app/ai/langgraph/ai_state.py` | Runtime validator `validate_ai_state` com checagem de chaves obrigatórias e tipos críticos (`:59`). |
| `backend-hormonia/app/ai/langgraph/nodes.py` | Flow nodes rely on required runtime config (`_require_handler`, `:27`); flow and response nodes mutate and commit state (`:525`, `:572`); AI nodes call Gemini directly (`:601`, `:622`, `:680`). |
| `backend-hormonia/app/services/flow/sequential_message_handler.py` | Flow graph invoked with handler config only (`:112`, `:118`, `:143`, `:145`); idempotency key present (`:243`); outbound message commit and repeated state commits (`:305`, `:810`). |
| `backend-hormonia/app/ai/client.py` | AI graph calls consistently pass `thread_id` (`:593`, `:649`, `:685`, `:733`). |
| `backend-hormonia/app/services/enhanced_flow_engine.py` | AI graph calls also pass `thread_id` in core flow engine paths (`:367`, `:456`). |
| `backend-hormonia/app/agents/communication/message_composer/composer.py` | Multiple generation graph invocations without `thread_id` (`:79`, `:141`, `:194`, `:249`, `:310`). |
| `backend-hormonia/app/domain/agents/quiz/response_handler.py` | Generation graph invoked without `thread_id` (`:141`). |
| `backend-hormonia/app/services/follow_up_system/generators/empathy.py` | Empathetic follow-up graph invoked without `thread_id` (`:132`). |
| `backend-hormonia/app/services/analytics/data_extraction/service.py` | Sentiment graph health-check call invoked without `thread_id` (`:442`). |
| `backend-hormonia/tests/langgraph/test_langgraph_real_flows.py` | Real graph smoke tests exist but are optional (`pytest.importorskip`, `:12`; três fluxos principais). |
| `backend-hormonia/tests/langgraph/test_consensus_logic.py` | Matriz negativa para consenso (defaults, polling, falhas de envio/coleta, filtros e decisão final). |
| `backend-hormonia/tests/langgraph/test_state_validation.py` | Matriz de validação de estado e erros de entrada em nós (`load_flow_context`, `load_response_context`, nós de IA). |
| `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` | Unit tests rely on graph stubs, not compiled LangGraph runtime (`:89` to `:98`). |
| `backend-hormonia/tests/api/v2/test_ai.py` | API tests force simulation fallback, reducing runtime LangGraph coverage (`:50` to `:56`). |

## 5) Risk Register
| ID | Severity | Risk | Why it matters | Evidence |
|---|---|---|---|---|
| R1 | High | Inconsistent `thread_id` discipline across call sites | Mixed persistence context can cause non-determinism, state bleed, or runtime incompatibility depending on LangGraph checkpointer behavior. | `backend-hormonia/app/agents/communication/message_composer/composer.py:79`, `backend-hormonia/app/domain/agents/quiz/response_handler.py:141`, `backend-hormonia/app/services/follow_up_system/generators/empathy.py:132`, vs `backend-hormonia/app/ai/client.py:593` |
| R2 | Medium | Validação runtime ainda não cobre 100% dos pontos de entrada externos | Há validação em nós críticos, mas chamadas indiretas e integrações futuras ainda podem bypassar a camada se não seguirem os nós padrão. | `backend-hormonia/app/ai/langgraph/nodes.py:271`, `backend-hormonia/app/ai/langgraph/nodes.py:515`, `backend-hormonia/app/ai/langgraph/nodes.py:665` |
| R3 | Medium-High | In-memory checkpointing only | No durable recovery across process restarts; replay/time-travel value is limited operationally. | `backend-hormonia/app/ai/langgraph/runtime.py:23`, `backend-hormonia/app/ai/langgraph/runtime.py:31` |
| R4 | High | Side effects are interleaved inside graph execution path | Replays/retries/concurrency can still produce state drift even with outbound message idempotency. | `backend-hormonia/app/ai/langgraph/nodes.py:525`, `backend-hormonia/app/ai/langgraph/nodes.py:572`, `backend-hormonia/app/services/flow/sequential_message_handler.py:305`, `backend-hormonia/app/services/flow/sequential_message_handler.py:810` |
| R5 | Medium | Consensus guardrails são conservadores por padrão | Mesmo com testes novos, `max_poll_attempts=1` continua podendo elevar taxa de `pending` em cenários degradados. | `backend-hormonia/app/ai/langgraph/consensus.py:61`, `backend-hormonia/app/ai/langgraph/consensus.py:215`, `backend-hormonia/tests/langgraph/test_consensus_logic.py` |
| R6 | Medium | Observability is log-only and low-cardinality | Troubleshooting remains manual; SLOs and alerting are hard to enforce without metrics/traces. | `backend-hormonia/app/ai/langgraph/runtime.py:59`, `backend-hormonia/app/ai/langgraph/runtime.py:76` |
| R7 | Medium | Cobertura LangGraph ainda é limitada para runtime real com dependência instalada | A matriz negativa foi criada, mas testes reais continuam opcionais e dependem da instalação de `langgraph`. | `backend-hormonia/tests/langgraph/test_langgraph_real_flows.py:12`, `backend-hormonia/tests/langgraph/test_consensus_logic.py`, `backend-hormonia/tests/langgraph/test_state_validation.py` |

## 6) Prioritized Backlog (Impact vs Effort)
| Priority | Backlog Item | Impact | Effort | Notes |
|---|---|---|---|---|
| P0 | Enforce graph invocation contract: always pass explicit `thread_id` for compiled graphs | High | Medium | Add shared invocation helper and migrate call sites currently missing config. |
| P0 | Expandir validação runtime para todos os entrypoints indiretos (além dos nós principais) | High | Medium | Guardar também adaptadores/callers que constroem estado dinamicamente. |
| P1 | Evoluir LG4 para cobrir também malformed sentiment JSON, poll timeout de integração e edge cases adicionais de send_mode/index em caminhos completos | High | Medium | Matriz base já foi criada com testes focais em consenso/validação. |
| P1 | Harden side-effect boundaries in flow graphs | High | High | Separate compute from commit where feasible; make replay behavior explicit in design/tests. |
| P1 | Add durable checkpointer option (Redis/Postgres) behind config for production profiles | Medium-High | Medium | Keep MemorySaver for local/dev only. |
| P2 | Add LangGraph metrics + tracing and error taxonomy | Medium | Medium | Build SLO dashboards and alert rules from standardized labels. |
| P2 | Document and drill operational runbooks | Medium | Low | Include on-call procedures and replay/recovery commands. |

## 7) Test Plan
- Unit tests:
  - Validate state schema enforcement for both state modules.
  - Validate router functions (`_route_after_load`, `_route_after_response_load`, `_route_after_collect`) for all branches.
  - Validate consensus defaults and poll loop behavior.
- Negative tests (LG4-focused):
  - Missing handler in flow graph config.
  - Invalid `FlowMessageState` and `AIState` payloads.
  - Malformed sentiment JSON from model.
  - Unknown/invalid `send_mode`, out-of-range message indexes, and duplicate/retry paths.
- Integration tests:
  - Real LangGraph invocation with dependency installed and explicit `thread_id`.
  - Concurrency test: simultaneous inbound response + flow progression for same patient.
  - Restart scenario to confirm behavior under non-durable vs durable checkpointer profiles.
- Regression gate suggestion:
  - `pytest backend-hormonia/tests/langgraph -q`
  - `pytest backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py -q`
  - New `tests/langgraph/test_consensus_graph.py` and `tests/langgraph/test_langgraph_runtime.py` suites.

## 8) Observability Plan
- Logging:
  - Keep `node_start/node_end/node_error`, add `thread_id`, `patient_id` (redacted/hash), `flow_kind`, `day_number`, `message_index`, and outcome code.
- Metrics:
  - `langgraph_graph_invocations_total{graph,status}`
  - `langgraph_graph_errors_total{graph,error_type}`
  - `langgraph_node_duration_ms{graph,node,outcome}` (histogram)
  - `langgraph_state_validation_failures_total{graph,state_type}`
  - `langgraph_checkpoint_backend{graph,backend}`
- Tracing:
  - Span per graph invocation, child span per node, include correlation to message/flow IDs.
- Alerting:
  - Error-rate alert per graph.
  - P95 node latency alert for critical nodes.
  - Consensus pending-rate alert when above threshold.

## 9) Operational Playbook Recommendations
- Playbook A: Graph execution failure in production flow
  - Identify failing graph/node via structured log keys.
  - Check idempotency key and message state before retry.
  - Retry through safe replay path with same `thread_id` when applicable.
- Playbook B: AI output contract break (invalid JSON/unsafe output)
  - Switch to fallback heuristic path.
  - Flag incident with prompt/profile metadata and model version.
  - Queue backlog item if repeated above threshold.
- Playbook C: Consensus pending or timeout
  - Capture vote fetch diagnostics and correlation IDs.
  - Escalate to manual decision path when poll attempts exceeded.
  - Record incident metrics to tune `max_poll_attempts` and delay.
- Playbook D: Worker restart/state loss
  - If using MemorySaver profile, treat thread memory as volatile.
  - Rebuild state from DB authoritative fields before re-invocation.

## 10) Maturity Snapshot vs Plan Board
- LG2 (checkpointer isolation + instrumentation): **Completed**.
- LG3 (error handling + runtime state validation): **Completed** para nós críticos.
- LG4 (negative matrix): **Completed** com suites dedicadas em `tests/langgraph/`.
- LG5 (this report): **Completed**.
