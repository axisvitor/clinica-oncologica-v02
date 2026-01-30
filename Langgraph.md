# LangGraph - uso no projeto

## Escopo
Este arquivo documenta somente o uso de LangGraph no nosso sistema (backend-hormonia).

## Versao
- Dependencia: langgraph>=1.0.7,<2.0.0 (ver backend-hormonia/requirements.txt)

## Documentacao essencial (LangGraph Python)
- Overview: https://docs.langchain.com/oss/python/langgraph/overview.md
- Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api.md
- Use the graph API: https://docs.langchain.com/oss/python/langgraph/use-graph-api.md
- Persistence: https://docs.langchain.com/oss/python/langgraph/persistence.md
- Interrupts (HITL): https://docs.langchain.com/oss/python/langgraph/interrupts.md
- Streaming: https://docs.langchain.com/oss/python/langgraph/streaming.md
- Time-travel / replay: https://docs.langchain.com/oss/python/langgraph/use-time-travel.md

## Grafos em uso

### Fluxo de mensagens (FlowMessageState)
- build_flow_message_graph / get_flow_message_graph
- build_flow_response_graph / get_flow_response_graph
- Arquivo: backend-hormonia/app/ai/langgraph/graphs.py
- Nos: backend-hormonia/app/ai/langgraph/nodes.py

### Grafos de IA (AIState)
- build_humanization_graph
- build_sentiment_graph
- build_generation_graph
- build_question_variation_graph
- build_empathetic_follow_up_graph
- Arquivo: backend-hormonia/app/ai/langgraph/graphs.py

### Consenso (Hive-Mind)
- build_consensus_graph / get_consensus_graph
- Arquivo: backend-hormonia/app/ai/langgraph/consensus.py
- Uso: backend-hormonia/app/agents/patient/flow_coordinator/consensus_manager.py

## Estado e contrato
- FlowMessageState: backend-hormonia/app/ai/langgraph/state.py
  - patient_id, day_number, flow_kind
  - flow_state_id, flow_state_step_data
  - day_config, messages, send_mode, current_index
  - result, error
- AIState: backend-hormonia/app/ai/langgraph/ai_state.py

## Como invocamos
- Handler passado via config:
  - graph.ainvoke(state, config={"configurable": {"handler": handler}})
- Chamadas principais:
  - backend-hormonia/app/services/flow/sequential_message_handler.py
  - backend-hormonia/app/ai/client.py

## Testes
- Real flows: backend-hormonia/tests/langgraph/test_langgraph_real_flows.py (requer langgraph instalado)
- Unit (com stubs): backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py
