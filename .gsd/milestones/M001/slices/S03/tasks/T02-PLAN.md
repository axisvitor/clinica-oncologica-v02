# T02: Correlation propagation and AI fallback metrics

**Slice:** S03 — **Milestone:** M001

## Description

Track AI personalization fallback rate via a Prometheus counter and propagate a correlation ID from webhook entry through every processing step so operators can trace a single patient message through the entire pipeline.

Purpose: Silent AI fallback degrades patient experience without visibility. Operators need to trace any message through webhook -> gate -> continuation -> send to debug issues.
Output: Prometheus counter for fallback rate, correlation ID generation at webhook entry, propagation through processing chain, and unit tests.

## Must-Haves

- [ ] "Every AI personalization fallback increments the ai_personalization_fallback_total Prometheus counter with a reason label"
- [ ] "A correlation ID is generated at WuzAPI webhook entry and set in the correlation_id ContextVar"
- [ ] "The correlation ID appears in structured logs at every processing step: webhook handler, sequential gate, response flow, message flow, and send"
- [ ] "Correlation ID propagates through the chain: webhook entry -> message handler -> gate evaluation -> continuation -> send"

## Files

- `backend-hormonia/app/services/flow/metrics.py`
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/personalization.py`
- `backend-hormonia/app/integrations/wuzapi/webhook.py`
- `backend-hormonia/app/services/webhook/handlers/message_handler.py`
- `backend-hormonia/app/services/flow/_flow_response_flow.py`
- `backend-hormonia/app/services/flow/_flow_message_flow.py`
- `backend-hormonia/tests/unit/services/flow/test_flow_metrics.py`
- `backend-hormonia/tests/unit/integrations/test_wuzapi_correlation_id.py`
