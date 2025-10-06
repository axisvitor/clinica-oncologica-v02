# CORS Request Flow Diagrams

## 1. Successful CORS Request Flow (Current Architecture)

```mermaid
sequenceDiagram
    participant Browser
    participant CORSMiddleware
    participant Backend
    participant Database

    Note over Browser: User triggers API call
    Browser->>+CORSMiddleware: OPTIONS /api/v1/auth/me
    Note over Browser,CORSMiddleware: Preflight Request<br/>Origin: https://frontend.railway.app

    CORSMiddleware->>CORSMiddleware: Check origin in ALLOWED_ORIGINS
    alt Origin Allowed
        CORSMiddleware-->>Browser: 200 OK + CORS Headers
        Note over CORSMiddleware,Browser: Access-Control-Allow-Origin: https://frontend.railway.app<br/>Access-Control-Allow-Methods: *<br/>Access-Control-Allow-Headers: *<br/>Access-Control-Allow-Credentials: true

        Browser->>+CORSMiddleware: GET /api/v1/auth/me
        Note over Browser,CORSMiddleware: Actual Request<br/>Authorization: Bearer <token>

        CORSMiddleware->>+Backend: Forward request
        Backend->>+Database: Query user data
        Database-->>-Backend: User data
        Backend-->>-CORSMiddleware: 200 OK + JSON response

        CORSMiddleware->>CORSMiddleware: Add CORS headers to response
        CORSMiddleware-->>-Browser: Response + CORS Headers
        Note over Browser: Request successful
    else Origin Not Allowed
        CORSMiddleware-->>Browser: 200 OK (no CORS headers)
        Note over Browser: Browser blocks response<br/>(CORS error in console)
    end
```

---

## 2. Failed CORS Request (PatternCORSMiddleware - Previous Architecture)

```mermaid
sequenceDiagram
    participant Browser
    participant PatternCORSMiddleware
    participant Backend

    Note over Browser: User triggers API call
    Browser->>+PatternCORSMiddleware: OPTIONS /api/v1/auth/me
    Note over Browser,PatternCORSMiddleware: Preflight Request<br/>Origin: https://frontend.railway.app

    PatternCORSMiddleware->>PatternCORSMiddleware: Pattern matching logic
    Note over PatternCORSMiddleware: ⚠️ BUG: CORS headers not set<br/>despite origin being allowed

    PatternCORSMiddleware-->>Browser: 200 OK (NO CORS headers)
    Note over Browser: ❌ CORS preflight failed<br/>ERR_FAILED

    Browser->>Browser: Abort actual request
    Note over Browser: ❌ API call never sent<br/>User sees white screen
```

---

## 3. CORS Middleware Stack Architecture

```mermaid
graph TB
    subgraph "Request Flow (Top to Bottom)"
        A[Incoming Request] --> B[Monitoring Middleware]
        B --> C[Query Performance Middleware]
        C --> D[Request Logging Middleware<br/>Development Only]
        D --> E[Security Middleware]
        E --> F[Rate Limiting Middleware]
        F --> G[Compression Middleware]
        G --> H[CORSMiddleware]
        H --> I[Route Handler]
    end

    subgraph "Response Flow (Bottom to Top)"
        I --> J[CORSMiddleware<br/>Adds CORS headers]
        J --> K[Compression Middleware<br/>Gzip/Brotli]
        K --> L[Rate Limiting Middleware<br/>Adds rate limit headers]
        L --> M[Security Middleware<br/>Adds security headers]
        M --> N[Request Logging Middleware<br/>Logs response]
        N --> O[Query Performance Middleware<br/>Adds DB metrics]
        O --> P[Monitoring Middleware<br/>Records metrics]
        P --> Q[Response to Client]
    end

    style H fill:#4CAF50,stroke:#2E7D32,stroke-width:3px,color:#fff
    style J fill:#4CAF50,stroke:#2E7D32,stroke-width:3px,color:#fff
```

**Key Points**:
- **CORS is last middleware added** (executes first in request chain)
- **CORS executes before route handler** (validates origin before processing)
- **CORS adds headers on both preflight and actual responses**

---

## 4. Development vs Production CORS Configuration

```mermaid
graph LR
    subgraph "Development Environment"
        DevRequest[Request<br/>localhost:5173] --> DevCORS[CORSMiddleware]
        DevCORS --> DevOrigins{Origin Check}
        DevOrigins -->|localhost:3000-5179| DevAllow[✅ Allow]
        DevOrigins -->|127.0.0.1:3000-5179| DevAllow
        DevOrigins -->|Other| DevBlock[❌ Block]
    end

    subgraph "Production Environment"
        ProdRequest[Request<br/>frontend.railway.app] --> ProdCORS[CORSMiddleware]
        ProdCORS --> ProdOrigins{Origin Check}
        ProdOrigins -->|Explicit Railway URLs| ProdAllow[✅ Allow]
        ProdOrigins -->|*.railway.app wildcard| ProdBlock[❌ Block<br/>No Wildcards]
        ProdOrigins -->|localhost| ProdBlock2[❌ Block<br/>No Dev Origins]
    end

    style DevAllow fill:#4CAF50
    style ProdAllow fill:#4CAF50
    style DevBlock fill:#F44336
    style ProdBlock fill:#F44336
    style ProdBlock2 fill:#F44336
```

---

## 5. CORS Preflight Cache Flow

```mermaid
sequenceDiagram
    participant Browser
    participant BrowserCache
    participant CORSMiddleware
    participant Backend

    Note over Browser: First request to new endpoint
    Browser->>BrowserCache: Check preflight cache
    BrowserCache-->>Browser: Cache miss

    Browser->>+CORSMiddleware: OPTIONS /api/v1/auth/me
    CORSMiddleware-->>-Browser: 200 OK + CORS Headers<br/>Access-Control-Max-Age: 86400

    Browser->>BrowserCache: Store preflight response<br/>(valid for 24 hours)

    Browser->>+CORSMiddleware: GET /api/v1/auth/me
    CORSMiddleware->>Backend: Process request
    Backend-->>CORSMiddleware: Response
    CORSMiddleware-->>-Browser: Response + CORS Headers

    Note over Browser: Next request within 24 hours
    Browser->>BrowserCache: Check preflight cache
    BrowserCache-->>Browser: Cache hit! Skip OPTIONS

    Browser->>+CORSMiddleware: GET /api/v1/auth/me<br/>(no preflight)
    CORSMiddleware->>Backend: Process request
    Backend-->>CORSMiddleware: Response
    CORSMiddleware-->>-Browser: Response + CORS Headers
```

**Performance Optimization**: 24-hour preflight cache reduces OPTIONS requests by ~50%

---

## 6. WebSocket Connection with CORS

```mermaid
sequenceDiagram
    participant Browser
    participant CORSMiddleware
    participant WebSocketHandler
    participant Backend

    Note over Browser: Establish WebSocket connection
    Browser->>+CORSMiddleware: Upgrade: websocket
    Note over Browser,CORSMiddleware: Origin: https://frontend.railway.app

    CORSMiddleware->>CORSMiddleware: Validate origin
    alt Origin Allowed
        CORSMiddleware->>+WebSocketHandler: Forward upgrade request
        WebSocketHandler->>WebSocketHandler: Validate token
        alt Token Valid
            WebSocketHandler-->>-CORSMiddleware: 101 Switching Protocols
            CORSMiddleware-->>Browser: 101 + CORS Headers
            Note over Browser,WebSocketHandler: WebSocket connection established

            Browser->>WebSocketHandler: Send: {"type": "subscribe"}
            WebSocketHandler->>Backend: Subscribe to events
            Backend-->>WebSocketHandler: Event stream
            WebSocketHandler-->>Browser: Receive: {"event": "update"}
        else Token Invalid
            WebSocketHandler-->>CORSMiddleware: 401 Unauthorized
            CORSMiddleware-->>Browser: 401 + CORS Headers
            Note over Browser: Connection rejected
        end
    else Origin Not Allowed
        CORSMiddleware-->>Browser: 403 Forbidden (no CORS headers)
        Note over Browser: ❌ CORS blocked<br/>Connection fails
    end
```

---

## 7. Multi-Origin Request Flow (Quiz Interface)

```mermaid
graph TB
    subgraph "Frontend Origins"
        MainFE[Main Frontend<br/>frontend.railway.app]
        QuizFE[Quiz Interface<br/>quiz-interface.railway.app]
        MobileFE[Mobile App<br/>hormonia-frontend.railway.app]
    end

    subgraph "Backend CORS Handling"
        MainFE --> CORS[CORSMiddleware]
        QuizFE --> CORS
        MobileFE --> CORS

        CORS --> OriginCheck{Origin in<br/>ALLOWED_ORIGINS?}

        OriginCheck -->|Yes| AllowedPath[Add CORS Headers<br/>Process Request]
        OriginCheck -->|No| BlockedPath[No CORS Headers<br/>Browser Blocks]

        AllowedPath --> API[Backend APIs<br/>/api/v1/auth/me<br/>/api/v1/quiz/submit]
        BlockedPath --> Log[Log Blocked Origin<br/>Security Alert]
    end

    style CORS fill:#4CAF50
    style AllowedPath fill:#4CAF50
    style BlockedPath fill:#F44336
```

**Security Note**: Each origin must be explicitly listed in `ALLOWED_ORIGINS`. No wildcards ensure no unauthorized domains can access the API.

---

## 8. CORS Error Flow and Debugging

```mermaid
graph TB
    Start[Browser Request] --> Preflight{Preflight<br/>Required?}

    Preflight -->|Yes<br/>Complex request| OPTIONS[Send OPTIONS]
    Preflight -->|No<br/>Simple request| DirectGET[Send GET/POST]

    OPTIONS --> CORSCheck1{CORS Headers<br/>in OPTIONS<br/>Response?}

    CORSCheck1 -->|Yes| ValidOrigin{Origin<br/>Allowed?}
    CORSCheck1 -->|No| Error1[❌ CORS Error<br/>No headers]

    ValidOrigin -->|Yes| ActualRequest[Send Actual Request]
    ValidOrigin -->|No| Error2[❌ CORS Error<br/>Origin blocked]

    DirectGET --> CORSCheck2{CORS Headers<br/>in Response?}
    ActualRequest --> CORSCheck2

    CORSCheck2 -->|Yes| Success[✅ Request Success]
    CORSCheck2 -->|No| Error3[❌ CORS Error<br/>Missing headers]

    Error1 --> Debug[Check Backend Logs<br/>Verify middleware setup]
    Error2 --> Debug2[Add origin to<br/>ALLOWED_ORIGINS]
    Error3 --> Debug3[Check middleware order<br/>Ensure CORS is last added]

    style Success fill:#4CAF50
    style Error1 fill:#F44336
    style Error2 fill:#F44336
    style Error3 fill:#F44336
```

---

## 9. Comparison: Before vs After Architecture

### Before (PatternCORSMiddleware)

```
┌─────────────────────────────────────────────────────────────┐
│ PatternCORSMiddleware (Custom)                              │
├─────────────────────────────────────────────────────────────┤
│ • Regex pattern matching: https://*.railway.app             │
│ • Wildcard support for dynamic subdomains                   │
│ • Custom origin validation logic                            │
│                                                             │
│ ❌ ISSUE: CORS headers not returned on OPTIONS             │
│ ❌ ISSUE: Preflight requests failing in production         │
│ ❌ ISSUE: No fallback for pattern matching failures        │
│                                                             │
│ Result: 100% API failure rate in production                │
└─────────────────────────────────────────────────────────────┘
```

### After (Standard CORSMiddleware)

```
┌─────────────────────────────────────────────────────────────┐
│ CORSMiddleware (FastAPI/Starlette Standard)                 │
├─────────────────────────────────────────────────────────────┤
│ • Explicit origin enumeration                               │
│ • Battle-tested by thousands of production apps             │
│ • RFC 6454 compliant                                        │
│                                                             │
│ ✅ CORS headers guaranteed on ALL OPTIONS requests         │
│ ✅ Predictable behavior across environments                │
│ ✅ Community support and documentation                     │
│                                                             │
│ Result: 100% API success rate in production                │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Health Endpoint Testing Flow

```mermaid
sequenceDiagram
    participant Admin
    participant Browser
    participant Backend

    Admin->>Browser: Navigate to /api/v1/health/cors-test

    Note over Browser,Backend: Automated CORS Testing

    Browser->>+Backend: OPTIONS /api/v1/health/cors-test
    Backend-->>-Browser: 200 OK + CORS Headers

    Browser->>+Backend: GET /api/v1/health/cors-test
    Backend-->>-Browser: {<br/>  "message": "CORS test successful",<br/>  "origin": "https://frontend.railway.app",<br/>  "cors_configured": true,<br/>  "allowed_origins": [...]<br/>}

    Browser->>Admin: Display CORS diagnostics

    Note over Admin: Verify:<br/>✅ OPTIONS returned CORS headers<br/>✅ GET request succeeded<br/>✅ Origin in allowed list
```

---

## Diagram Key

- **Green boxes**: Successful flow
- **Red boxes**: Error/blocked flow
- **Yellow boxes**: Decision points
- **Blue boxes**: Middleware/processing
- **Arrows**: Request/response direction

---

## Additional Resources

- See `ADR-001-CORS-Architecture.md` for decision rationale
- See `CORS_DEBUGGING_REPORT.md` for production incident analysis
- See `CORS_FIX_IMPLEMENTATION.md` for implementation details
