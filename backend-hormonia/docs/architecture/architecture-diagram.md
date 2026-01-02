# Cache Invalidation Service - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                           │
│  (PatientCRUDService, QuizService, FlowService, etc.)          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ Uses
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              CacheInvalidationService (Core)                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Invalidation Strategies                               │   │
│  │  • SINGLE    - Single key invalidation                 │   │
│  │  • PATTERN   - Wildcard pattern matching               │   │
│  │  • TAGS      - Tag-based bulk invalidation             │   │
│  │  • CASCADE   - Key + related patterns                  │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Core Features                                         │   │
│  │  • Retry Logic (exponential backoff)                   │   │
│  │  • Multi-backend support (Redis/Local)                 │   │
│  │  • Automatic fallback                                  │   │
│  │  • Metrics collection                                  │   │
│  │  • Detailed logging                                    │   │
│  └────────────────────────────────────────────────────────┘   │
└────────────┬───────────────────────────┬──────────────────────┘
             │                           │
             │ Uses                      │ Uses
             ▼                           ▼
┌──────────────────────────┐  ┌──────────────────────────────────┐
│   CacheKeyBuilder        │  │   Backend Adapters               │
│                          │  │                                  │
│  • build()               │  │  ┌────────────────────────────┐ │
│  • build_pattern()       │  │  │  Redis Adapter             │ │
│  • build_tag_key()       │  │  │  • SCAN operations         │ │
│  • parse()               │  │  │  • Native pattern matching │ │
│  • get_entity_patterns() │  │  │  • Set operations (tags)   │ │
│                          │  │  └────────────────────────────┘ │
│  Output:                 │  │                                  │
│  hormonia:v1:entity:id   │  │  ┌────────────────────────────┐ │
└──────────────────────────┘  │  │  Local Cache Adapter       │ │
                              │  │  • Dict-based storage      │ │
                              │  │  • Regex pattern matching  │ │
                              │  │  • In-memory tags          │ │
                              │  └────────────────────────────┘ │
                              └──────────────────────────────────┘
```

## Data Flow

### 1. Entity Invalidation Flow

```
┌──────────────┐
│  Service     │
│  (CRUD ops)  │
└──────┬───────┘
       │
       │ 1. invalidate_entity("patient", "123", cascade=True)
       ▼
┌──────────────────────────┐
│ CacheInvalidationService │
└──────┬───────────────────┘
       │
       │ 2. Build patterns
       ▼
┌──────────────────────────┐
│   CacheKeyBuilder        │
│                          │
│   Returns:               │
│   - patient:123          │
│   - patient:list:*       │
│   - patient:count:*      │
│   - patient:search:*     │
└──────┬───────────────────┘
       │
       │ 3. Execute invalidation
       ▼
┌──────────────────────────────────────┐
│   Backend (Redis or Local)           │
│                                      │
│   If Redis fails:                    │
│   ├─ Retry 3x (exponential backoff) │
│   └─ Fallback to local cache        │
└──────┬───────────────────────────────┘
       │
       │ 4. Log & collect metrics
       ▼
┌──────────────────────────┐
│   Metrics                │
│   - invalidations++      │
│   - retries (if any)     │
│   - failures (if any)    │
│   - fallbacks (if any)   │
└──────────────────────────┘
```

### 2. Pattern Matching Flow

```
┌─────────────────────┐
│  Pattern Request    │
│  "patient:list:*"   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────────────┐
│  Redis SCAN Operation           │
│                                 │
│  cursor = 0                     │
│  while cursor != 0:             │
│    cursor, keys = SCAN(cursor)  │
│    DELETE(keys...)              │
└─────────┬───────────────────────┘
          │
          │ Results
          ▼
┌─────────────────────────────────┐
│  Deleted Keys                   │
│  - patient:list:abc123          │
│  - patient:list:def456          │
│  - patient:list:ghi789          │
└─────────────────────────────────┘
```

### 3. Tag-based Invalidation Flow

```
┌──────────────────┐
│  Tag Keys        │
│  tag_key()       │
└────┬─────────────┘
     │
     │ Store mapping
     ▼
┌────────────────────────────┐
│  Redis Sets               │
│                            │
│  tags:oncology → {         │
│    patient:123,            │
│    quiz:456                │
│  }                         │
│                            │
│  tags:active → {           │
│    patient:123,            │
│    patient:789             │
│  }                         │
└────────────────────────────┘
     │
     │ Invalidate by tag
     ▼
┌────────────────────────────┐
│  Retrieve Tagged Keys      │
│  SMEMBERS tags:oncology    │
└────┬───────────────────────┘
     │
     │ Delete all
     ▼
┌────────────────────────────┐
│  DELETE patient:123        │
│  DELETE quiz:456           │
└────────────────────────────┘
```

## Retry Mechanism

```
┌─────────────────────────────────────────────────────────┐
│                    Retry Timeline                       │
└─────────────────────────────────────────────────────────┘

Attempt 1: ──┐
             │ Immediate execution
             ├─[FAIL]
             │
             │ Wait 0.1s
             ▼
Attempt 2: ──┐
             │ Retry with 0.1s delay
             ├─[FAIL]
             │
             │ Wait 0.2s (backoff x2)
             ▼
Attempt 3: ──┐
             │ Retry with 0.2s delay
             ├─[FAIL]
             │
             │ Wait 0.4s (backoff x2)
             ▼
Attempt 4: ──┐
             │ Final retry with 0.4s delay
             ├─[FAIL]
             │
             ▼
┌────────────────────────┐
│  Fallback to Local     │
│  OR Log Error          │
└────────────────────────┘
```

## Service Integration Pattern

```
┌───────────────────────────────────────────────────────────┐
│                  PatientCRUDService                       │
└───────────────────────────────────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
┌─────────┐           ┌───────────┐          ┌──────────────────┐
│   DB    │           │   Cache   │          │  Cache           │
│ Update  │           │ Invalidate│          │  Invalidation    │
│         │           │           │          │  Service         │
└────┬────┘           └─────┬─────┘          └────────┬─────────┘
     │                      │                         │
     │ 1. Transaction       │                         │
     ├──────────────────────┤                         │
     │ BEGIN                │                         │
     │ UPDATE patients...   │                         │
     │ COMMIT ✓             │                         │
     │                      │                         │
     │                      │ 2. After commit         │
     │                      │ (best-effort)           │
     │                      ├─────────────────────────▶
     │                      │                         │
     │                      │    invalidate_entity()  │
     │                      │                         │
     │                      │                    ┌────┴────┐
     │                      │                    │ Retry   │
     │                      │                    │ Logic   │
     │                      │                    └────┬────┘
     │                      │                         │
     │                      ◀─────────────────────────┤
     │                      │     Success/Failure     │
     │                      │                         │
     ▼                      ▼                         ▼
┌──────────────────────────────────────────────────────────┐
│  DB Updated + Cache Invalidated (or logged warning)     │
└──────────────────────────────────────────────────────────┘
```

## Key Generation Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    Key Structure                            │
└─────────────────────────────────────────────────────────────┘

Format: namespace:version:entity[:identifier][:operation][:params_hash]

Examples:

1. Simple entity key:
   hormonia:v1:patient:123e4567-e89b-12d3-a456-426614174000

2. Operation key:
   hormonia:v1:patient:list

3. Parameterized operation:
   hormonia:v1:patient:list:a3f2c1b4
                              └─ hash of {status: "active", page: 1}

4. Pattern (wildcard):
   hormonia:v1:patient:*
   hormonia:v1:patient:123:*
   hormonia:v1:patient:list:*

5. Tag key:
   hormonia:tags:v1:oncology
   hormonia:tags:v1:active
```

## Error Handling Flow

```
┌────────────────────────┐
│  Invalidation Request  │
└──────────┬─────────────┘
           │
           ▼
    ┌──────────────┐
    │   Try Redis  │
    └──────┬───────┘
           │
    ┌──────▼──────────────────┐
    │                         │
    │  Success?               │
    │                         │
    └──┬──────────────────┬───┘
       │ Yes              │ No
       │                  │
       ▼                  ▼
┌──────────────┐   ┌─────────────────┐
│   Return     │   │  Retry Logic    │
│   Success    │   │  (max 3x)       │
└──────────────┘   └─────┬───────────┘
                         │
                  ┌──────▼──────────────┐
                  │                     │
                  │  Still Failing?     │
                  │                     │
                  └──┬──────────────┬───┘
                     │ No           │ Yes
                     │              │
                     ▼              ▼
              ┌──────────────┐  ┌────────────────┐
              │   Return     │  │  Fallback to   │
              │   Success    │  │  Local Cache   │
              └──────────────┘  └────┬───────────┘
                                     │
                              ┌──────▼──────────┐
                              │  Log Warning    │
                              │  Increment      │
                              │  Fallback       │
                              │  Metric         │
                              └─────────────────┘
```

## Metrics Collection

```
┌─────────────────────────────────────────────────────────┐
│                   Metrics Structure                     │
└─────────────────────────────────────────────────────────┘

{
  "invalidations": 142,      ← Total operations
  "retries": 8,             ← Number of retries across all ops
  "failures": 2,            ← Operations that failed completely
  "fallbacks": 3,           ← Times fell back to local cache
  "timestamp": "2025-12-23T20:00:00Z",
  "backend": "redis"        ← Current primary backend
}

┌─────────────────────────────────────────────────────────┐
│                Metrics Over Time                        │
└─────────────────────────────────────────────────────────┘

Invalidations  │ ████████████████  142
Retries        │ ████              8
Failures       │ █                 2
Fallbacks      │ ██                3

Success Rate: 98.6% (140/142)
Retry Rate: 5.6% (8/142)
Fallback Rate: 2.1% (3/142)
```

## Component Interaction

```
┌──────────────────────────────────────────────────────────┐
│                   Component Stack                        │
└──────────────────────────────────────────────────────────┘

         User Request
              │
              ▼
    ┌──────────────────┐
    │   API Router     │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │  CRUD Service    │◄─────┐
    └────────┬─────────┘      │
             │                │
    ┌────────▼─────────┐      │
    │   Repository     │      │
    └────────┬─────────┘      │
             │                │
    ┌────────▼─────────┐      │
    │   Database       │      │
    │   Transaction    │      │
    └────────┬─────────┘      │
             │                │
             │ Commit         │
             ▼                │
    ┌──────────────────────┐  │
    │  Cache Invalidation  ├──┘
    │  Service             │
    └──────────┬───────────┘
               │
      ┌────────┼────────┐
      │                 │
      ▼                 ▼
┌──────────┐      ┌──────────┐
│  Redis   │      │  Local   │
│  Cache   │      │  Cache   │
└──────────┘      └──────────┘
```

## Deployment Topology

```
┌─────────────────────────────────────────────────────────┐
│                Production Environment                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────┐       ┌─────────────────────┐
│   App Server 1          │       │   App Server 2      │
│                         │       │                     │
│  ┌───────────────────┐  │       │  ┌──────────────┐  │
│  │ Cache Service     │  │       │  │ Cache Service│  │
│  └─────────┬─────────┘  │       │  └──────┬───────┘  │
│            │             │       │         │          │
└────────────┼─────────────┘       └─────────┼──────────┘
             │                               │
             │        Shared Redis           │
             │                               │
             └───────────┬───────────────────┘
                         │
                         ▼
                ┌────────────────┐
                │  Redis Cluster │
                │                │
                │  ┌──────────┐  │
                │  │  Master  │  │
                │  └────┬─────┘  │
                │       │        │
                │  ┌────▼─────┐  │
                │  │ Replica  │  │
                │  └──────────┘  │
                └────────────────┘
```

## See Also

- [Implementation Summary](./IMPLEMENTATION_SUMMARY.md)
- [Cache Invalidation Service Guide](./CACHE_INVALIDATION_SERVICE.md)
- [Usage Examples](../app/services/cache/examples.py)
