# Circuit Breaker Flow Diagram

## Request Flow with Circuit Breaker

```
┌─────────────────────────────────────────────────────────────────┐
│                     AI Service Request                          │
│              (e.g., Gemini, Sentiment Analysis)                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Check Cache First                            │
│                                                                 │
│  ┌──────────────┐                                              │
│  │ Cache Hit?   │──Yes──▶ Return Cached Response (Fast!)       │
│  └──────┬───────┘                                              │
│         │ No                                                    │
└─────────┼─────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Circuit Breaker Check                          │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Circuit State?                         │  │
│  └──┬────────────────┬──────────────────┬──────────────────┘  │
│     │ CLOSED         │ OPEN             │ HALF_OPEN           │
│     │ (Normal)       │ (Failing)        │ (Testing)           │
└─────┼────────────────┼──────────────────┼──────────────────────┘
      │                │                  │
      ▼                ▼                  ▼
┌───────────┐   ┌────────────┐   ┌──────────────┐
│  Allow    │   │   Block    │   │  Allow       │
│  Request  │   │   Request  │   │  Limited     │
│           │   │            │   │  Requests    │
└─────┬─────┘   └─────┬──────┘   └──────┬───────┘
      │               │                  │
      │               │                  │
      ▼               ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Execute Request                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Call AI Service API                         │  │
│  │    (Gemini, OpenAI, LangChain, etc.)                     │  │
│  └──────────┬────────────────────────┬──────────────────────┘  │
│             │ Success                │ Failure                  │
└─────────────┼────────────────────────┼──────────────────────────┘
              │                        │
              ▼                        ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  Record Success  │      │  Record Failure  │
    │                  │      │                  │
    │  • Increment     │      │  • Increment     │
    │    success count │      │    failure count │
    │  • Reset         │      │  • Check         │
    │    failure count │      │    threshold     │
    └────────┬─────────┘      └────────┬─────────┘
             │                         │
             ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │ HALF_OPEN?       │      │ Threshold        │
    │                  │      │ Reached?         │
    │ Yes: Check if    │      │                  │
    │ enough successes │      │ Yes: Open        │
    │ to close circuit │      │ Circuit          │
    └────────┬─────────┘      └────────┬─────────┘
             │                         │
             ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │ Close Circuit    │      │ Execute Fallback │
    │                  │      │                  │
    │ Return to        │      │ • Return         │
    │ normal operation │      │   fallback       │
    └────────┬─────────┘      │   response       │
             │                └────────┬─────────┘
             │                         │
             ▼                         ▼
    ┌──────────────────┐      ┌──────────────────┐
    │  Cache Response  │      │  Log Failure     │
    └────────┬─────────┘      └────────┬─────────┘
             │                         │
             └─────────┬───────────────┘
                       │
                       ▼
             ┌──────────────────┐
             │ Return Response  │
             │ to Caller        │
             └──────────────────┘
```

## State Transition Diagram

```
                 Start
                   │
                   ▼
         ┌─────────────────┐
         │                 │
         │     CLOSED      │◀─┐
         │  (Normal Ops)   │  │
         │                 │  │
         └────────┬────────┘  │
                  │            │
           failures ≥ 3       │
                  │            │
                  ▼            │
         ┌─────────────────┐  │
         │                 │  │
         │      OPEN       │  │
         │   (Failing)     │  │
         │                 │  │
         └────────┬────────┘  │
                  │            │
         timeout elapsed       │
         (30-60 seconds)       │
                  │            │
                  ▼            │
         ┌─────────────────┐  │
         │                 │  │
         │   HALF_OPEN     │  │
         │   (Testing)     │  │
         │                 │  │
         └────────┬────────┘  │
                  │            │
           ┌──────┴──────┐    │
           │             │    │
      Success       Failure   │
      (≥2 times)              │
           │             │    │
           └─────────────┴────┘
                         │
                         ▼
                 ┌──────────────┐
                 │ Back to OPEN │
                 └──────────────┘
```

## Example Scenario: Gemini API Failure

```
Timeline:

T=0s    │ Request 1 → Success → Circuit: CLOSED
        │
T=5s    │ Request 2 → Success → Circuit: CLOSED
        │
T=10s   │ Request 3 → FAILURE → Circuit: CLOSED (failure_count=1)
        │
T=15s   │ Request 4 → FAILURE → Circuit: CLOSED (failure_count=2)
        │
T=20s   │ Request 5 → FAILURE → Circuit: OPEN ❌ (threshold reached!)
        │                         ↓
        │                   Use fallback response
        │
T=25s   │ Request 6 → Circuit: OPEN ❌ (immediate fallback)
        │
T=30s   │ Request 7 → Circuit: OPEN ❌ (immediate fallback)
        │
T=50s   │ [30 second timeout elapsed]
        │ Request 8 → Circuit: HALF_OPEN 🟡 (testing recovery)
        │              → Success! (success_count=1)
        │
T=55s   │ Request 9 → Circuit: HALF_OPEN 🟡
        │              → Success! (success_count=2)
        │              → Circuit: CLOSED ✅ (recovered!)
        │
T=60s   │ Request 10 → Circuit: CLOSED ✅ (normal operation)
```

## Fallback Decision Tree

```
                    Circuit Open?
                         │
              ┌──────────┴──────────┐
              │                     │
             Yes                   No
              │                     │
              ▼                     ▼
    Use Fallback Response     Call AI Service
              │                     │
              │                     │
    ┌─────────┴─────────┐          │
    │                   │          │
    │   Fallback Type   │          │
    │                   │          │
    └─────────┬─────────┘          │
              │                     │
    ┌─────────┼─────────┐          │
    │         │         │          │
 Gemini   Sentiment   Quiz         │
    │         │         │          │
    ▼         ▼         ▼          │
Portuguese  Rule-based  Option     │
Generic     Keywords   Matching    │
Message     Analysis              │
    │         │         │          │
    └─────────┴─────────┴──────────┘
              │
              ▼
        Return Response
```

## Integration Points

```
┌───────────────────────────────────────────────────────────────────┐
│                         Application Layer                         │
│                                                                   │
│  ┌─────────────────┐              ┌──────────────────┐          │
│  │  WhatsApp Bot   │              │   Web API        │          │
│  └────────┬────────┘              └────────┬─────────┘          │
│           │                                 │                     │
└───────────┼─────────────────────────────────┼─────────────────────┘
            │                                 │
            ▼                                 ▼
┌───────────────────────────────────────────────────────────────────┐
│                         Service Layer                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐      │
│  │              AIService                                 │      │
│  │  ┌──────────────────────────────────────────────┐     │      │
│  │  │         Circuit Breaker                      │     │      │
│  │  │  ┌──────────────┐  ┌──────────────┐         │     │      │
│  │  │  │   Gemini     │  │  Sentiment   │         │     │      │
│  │  │  │   Breaker    │  │   Breaker    │         │     │      │
│  │  │  └──────┬───────┘  └──────┬───────┘         │     │      │
│  │  └─────────┼──────────────────┼─────────────────┘     │      │
│  └────────────┼──────────────────┼───────────────────────┘      │
└───────────────┼──────────────────┼───────────────────────────────┘
                │                  │
                ▼                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Integration Layer                            │
│                                                                   │
│  ┌──────────────────┐              ┌──────────────────┐          │
│  │  GeminiClient    │              │  LangChain       │          │
│  │                  │              │  Orchestrator    │          │
│  └────────┬─────────┘              └────────┬─────────┘          │
└───────────┼──────────────────────────────────┼─────────────────────┘
            │                                  │
            ▼                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                       External Services                           │
│                                                                   │
│  ┌──────────────────┐              ┌──────────────────┐          │
│  │  Google Gemini   │              │  OpenAI API      │          │
│  │  API             │              │                  │          │
│  └──────────────────┘              └──────────────────┘          │
└───────────────────────────────────────────────────────────────────┘
```

## Metrics Collection Flow

```
Every AI Request
      │
      ▼
┌─────────────────┐
│ Circuit Breaker │
│ Intercepts Call │
└────────┬────────┘
         │
         ├─────▶ Record: total_requests++
         │
         ├─────▶ Record: timestamp
         │
         ▼
   Execute Request
         │
    ┌────┴────┐
    │         │
 Success   Failure
    │         │
    ▼         ▼
Record:    Record:
• success  • failure
  _count++   _count++
• success  • consec
  _rate      _failures++
• consec   • last
  _succ++    _failure
• state      time
  change   • state
           change
    │         │
    └────┬────┘
         │
         ▼
   ┌──────────────┐
   │ Update Stats │
   │  (in memory) │
   └──────────────┘
         │
         ▼
   ┌──────────────┐
   │ Return Stats │
   │ via API      │
   └──────────────┘
```

## Cache Interaction

```
Request Arrives
      │
      ▼
┌─────────────────┐
│  Check Cache    │
│  (Redis/Memory) │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
  Hit       Miss
    │         │
    ▼         ▼
 Return    Circuit
 Cached    Breaker
 (Fast!)   Check
    │         │
    │         ▼
    │    Call AI
    │    Service
    │         │
    │         ▼
    │    Cache
    │    Result
    │         │
    └────┬────┘
         │
         ▼
    Return to
     Caller
```

## Error Handling Flow

```
AI Request
    │
    ▼
┌─────────────────┐
│ Try AI Call     │
│ with Circuit    │
└────────┬────────┘
         │
    ┌────┴─────┐
    │          │
Success    Exception
    │          │
    ▼          ▼
Return   ┌──────────────┐
Result   │ Circuit      │
         │ Catches      │
         └──────┬───────┘
                │
           ┌────┴────┐
           │         │
      API Error  Timeout
           │         │
           └────┬────┘
                │
                ▼
         ┌──────────────┐
         │ Log Error    │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │ Check        │
         │ Threshold    │
         └──────┬───────┘
                │
           ┌────┴────┐
           │         │
       Reached   Not Yet
           │         │
           ▼         ▼
      Open      Increment
      Circuit   Counter
           │         │
           └────┬────┘
                │
                ▼
         ┌──────────────┐
         │ Execute      │
         │ Fallback     │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │ Return       │
         │ Fallback     │
         │ Response     │
         └──────────────┘
```

## Legend

```
┌─────────────────┐
│  Process/Step   │
└─────────────────┘

      │
      ▼
   Arrow (Flow)

┌──────┴──────┐
│   Decision  │
└─────────────┘

◀─┐
  │  Loop/Return
  │
──┘

✅ Success State
❌ Error State
🟡 Warning State
```
