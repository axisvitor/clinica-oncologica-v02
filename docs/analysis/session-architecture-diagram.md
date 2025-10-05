# Session Management Architecture Diagrams

## 1. Session Creation Flow (Thread-Safe)

```mermaid
sequenceDiagram
    participant Client
    participant Middleware
    participant SessionMgr as SessionManager
    participant ContextVar
    participant Database
    participant Redis

    Client->>Middleware: HTTP Request
    Middleware->>Middleware: Rate Limit Check (Redis)
    Middleware->>Middleware: Security Validation
    Middleware->>SessionMgr: get_session()

    SessionMgr->>ContextVar: _request_session.get()
    alt Existing Active Session
        ContextVar-->>SessionMgr: Return existing session
        SessionMgr-->>Middleware: Reuse session
    else No Session or Inactive
        SessionMgr->>Database: SessionLocal()
        Database-->>SessionMgr: New DB Session
        SessionMgr->>ContextVar: _request_session.set(session)
        SessionMgr-->>Middleware: New session created
    end

    Middleware->>Middleware: Process Request
    Middleware->>SessionMgr: Commit/Rollback
    SessionMgr->>Database: session.close()
    SessionMgr->>ContextVar: reset context
    SessionMgr-->>Middleware: Cleanup complete
    Middleware-->>Client: HTTP Response
```

## 2. Authentication Flow (Firebase + Local Sync)

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant AuthDep as auth_dependencies
    participant Firebase
    participant UserSync
    participant Database
    participant Redis

    Client->>API: Request with JWT Bearer Token
    API->>AuthDep: get_current_user()
    AuthDep->>Firebase: verify_token(jwt)

    alt Firebase Configured
        Firebase-->>AuthDep: User Data (uid, email)
        AuthDep->>UserSync: sync_firebase_user()

        UserSync->>Database: Check user exists
        alt User Exists
            Database-->>UserSync: Return user
        else User Not Found
            UserSync->>Database: Create new user
            Database-->>UserSync: New user created
        end

        UserSync-->>AuthDep: User object
        AuthDep->>AuthDep: Check is_active

        alt User Active
            AuthDep->>Redis: Cache user data (30 min TTL)
            AuthDep-->>API: Authenticated User
        else User Inactive
            AuthDep-->>API: 403 Forbidden
        end

    else Firebase Not Configured
        AuthDep-->>API: 503 Service Unavailable
    end
```

## 3. Rate Limiting Flow (Distributed)

```mermaid
sequenceDiagram
    participant Request
    participant Middleware
    participant Redis
    participant InMemory

    Request->>Middleware: HTTP Request
    Middleware->>Middleware: Extract email/IP

    alt Redis Available
        Middleware->>Redis: GET rate_limit:email:{email}
        Redis-->>Middleware: Current count (or null)

        alt Count < Limit
            Middleware->>Redis: INCR rate_limit:email:{email}
            Middleware->>Redis: EXPIRE (lockout_window)
            Redis-->>Middleware: Allow request
            Middleware->>Request: Process request
        else Count >= Limit
            Middleware-->>Request: 429 Too Many Requests
        end

    else Redis Unavailable
        Note over Middleware,InMemory: SECURITY ISSUE: Currently allows request!

        Middleware->>InMemory: Check in-memory store
        alt Single Instance Only
            InMemory-->>Middleware: Count (per-process)
            Middleware->>Request: Allow/Deny (unreliable)
        end
    end
```

## 4. Session Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> Initialized: Request arrives

    Initialized --> ContextCheck: get_session()

    ContextCheck --> ReuseExisting: Session exists & active
    ContextCheck --> CreateNew: No session / inactive

    ReuseExisting --> Processing
    CreateNew --> ContextStore: Create SessionLocal()
    ContextStore --> Processing

    Processing --> TransactionCheck: Request completed
    TransactionCheck --> Commit: Success
    TransactionCheck --> Rollback: Exception

    Commit --> Cleanup
    Rollback --> Cleanup

    Cleanup --> ContextReset: session.close()
    ContextReset --> [*]: Request complete
```

## 5. Redis Manager Architecture (Dual Client)

```mermaid
graph TB
    subgraph Application
        A[FastAPI App] --> B{Context Detection}
        B -->|Async Context| C[AsyncToSyncWrapper]
        B -->|Sync Context| D[Sync Client]
        B -->|Auto Detect| E[Compatible Client]
    end

    subgraph Redis Manager
        C --> F[Async Client]
        D --> G[Sync Client]
        E --> H[Event Loop Check]
        H -->|Loop Running| F
        H -->|No Loop| G

        F --> I[Async Connection Pool<br/>Max: 50 connections]
        G --> J[Sync Connection Pool<br/>Max: 50 connections]
    end

    subgraph Redis Backend
        I --> K[Redis Cloud<br/>SSL/TLS]
        J --> K
        K --> L[(Redis DB 0-15)]
    end

    style F fill:#4CAF50
    style G fill:#2196F3
    style K fill:#FF9800
```

## 6. Security Middleware Stack

```mermaid
graph LR
    A[Request] --> B[EnhancedRateLimitMiddleware]
    B --> C{Rate Limit Check}
    C -->|OK| D[EnhancedSecurityMiddleware]
    C -->|Exceeded| E[429 Response]

    D --> F{Security Checks}
    F -->|Size OK| G{Content Type OK}
    F -->|Too Large| H[413 Response]

    G -->|Valid| I{Pattern Check}
    G -->|Invalid| J[415 Response]

    I -->|SQL Injection| K[400 Response]
    I -->|XSS Detected| K
    I -->|Clean| L[RequestLoggingMiddleware]

    L --> M[Add Correlation ID]
    M --> N[Log Request]
    N --> O[Process Request]
    O --> P[Log Response]
    P --> Q[Add Security Headers]
    Q --> R[Response]

    style C fill:#FFC107
    style F fill:#FF5722
    style I fill:#E91E63
    style M fill:#9C27B0
```

## 7. Thread Safety Isolation (ContextVars)

```mermaid
graph TB
    subgraph Request 1 Thread
        R1[Request 1] --> CV1[ContextVar Copy 1]
        CV1 --> S1[DB Session 1]
        CV1 --> P1[ServiceProvider 1]
        CV1 --> RC1[Redis Client 1]
    end

    subgraph Request 2 Thread
        R2[Request 2] --> CV2[ContextVar Copy 2]
        CV2 --> S2[DB Session 2]
        CV2 --> P2[ServiceProvider 2]
        CV2 --> RC2[Redis Client 2]
    end

    subgraph Request N Thread
        RN[Request N] --> CVN[ContextVar Copy N]
        CVN --> SN[DB Session N]
        CVN --> PN[ServiceProvider N]
        CVN --> RCN[Redis Client N]
    end

    S1 --> DB[(Database Pool)]
    S2 --> DB
    SN --> DB

    RC1 --> REDIS[(Redis Pool)]
    RC2 --> REDIS
    RCN --> REDIS

    style CV1 fill:#4CAF50
    style CV2 fill:#2196F3
    style CVN fill:#FF9800
    style DB fill:#9C27B0
    style REDIS fill:#F44336
```

## 8. Token Lifecycle (JWT)

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant API
    participant Firebase
    participant Redis
    participant Blacklist

    User->>Client: Login
    Client->>Firebase: Authenticate
    Firebase-->>Client: Firebase JWT (30 min)
    Client->>API: Request + JWT

    loop Every Request
        API->>Firebase: Verify JWT signature
        Firebase-->>API: Token valid

        API->>Blacklist: Check blacklist (in-memory)
        alt Token Not Blacklisted
            Blacklist-->>API: OK
            API->>API: Process request
        else Token Blacklisted
            Blacklist-->>API: Denied
            API-->>Client: 401 Unauthorized
        end
    end

    User->>Client: Logout
    Client->>API: POST /logout
    API->>Blacklist: Add token to blacklist
    Note over Blacklist: ISSUE: In-memory only<br/>Lost on restart

    alt JWT Expires
        Client->>Firebase: Use refresh token
        Firebase-->>Client: New JWT
    end
```

## 9. Vulnerability: Session Fixation Attack

```mermaid
sequenceDiagram
    participant Attacker
    participant Victim
    participant Server

    Note over Attacker: 1. Attacker obtains JWT<br/>(via XSS/MITM/stolen device)

    Attacker->>Server: Use JWT normally
    Server-->>Attacker: Access granted ✅

    Note over Victim: 2. Victim logs in<br/>(same account)

    Victim->>Server: Login with password
    Server-->>Victim: Same JWT (NO ROTATION!) ⚠️

    Note over Attacker,Victim: BOTH can use JWT concurrently

    Attacker->>Server: Use stolen JWT
    Server-->>Attacker: Access still granted ❌

    Victim->>Server: Use JWT
    Server-->>Victim: Access granted ✅

    Note over Server: ISSUE: No token rotation<br/>No concurrent session detection<br/>No IP/User-Agent validation
```

## 10. Proposed Fix: Session Fingerprinting

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant Server
    participant Redis
    participant Fingerprint

    User->>Client: Login (IP: 1.2.3.4)
    Client->>Server: Authenticate
    Server->>Fingerprint: Generate(IP + User-Agent + User ID)
    Fingerprint-->>Server: Hash: abc123
    Server->>Redis: Store fingerprint:token_hash → abc123
    Server-->>Client: JWT + Cookie (HttpOnly)

    Note over Client,Server: Later request from same device

    Client->>Server: Request + JWT (IP: 1.2.3.4)
    Server->>Fingerprint: Generate current fingerprint
    Fingerprint-->>Server: Hash: abc123
    Server->>Redis: GET fingerprint:token_hash
    Redis-->>Server: Stored: abc123
    Server->>Server: Compare: abc123 == abc123 ✅
    Server-->>Client: Request processed

    Note over Client,Server: Attack: Different IP/User-Agent

    Client->>Server: Request + JWT (IP: 5.6.7.8) ⚠️
    Server->>Fingerprint: Generate current fingerprint
    Fingerprint-->>Server: Hash: xyz789 (DIFFERENT)
    Server->>Redis: GET fingerprint:token_hash
    Redis-->>Server: Stored: abc123
    Server->>Server: Compare: xyz789 != abc123 ❌
    Server->>Server: Alert security team
    Server->>Redis: Blacklist token
    Server-->>Client: 401 Unauthorized + Force re-login
```

---

**Generated:** 2025-10-05
**Related Document:** session-management-analysis.md
