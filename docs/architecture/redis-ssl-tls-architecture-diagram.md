# Redis SSL/TLS Architecture - Visual Diagrams

**Component Interaction & Data Flow**
**Version:** 1.0.0
**Date:** 2025-10-05

---

## 1. Current vs. Proposed Architecture

### Current Architecture (Problematic)

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐         ┌──────────────┐                  │
│  │  Settings   │         │ Redis Manager│                  │
│  │  (config.py)│         │              │                  │
│  │             │         │              │                  │
│  │ ❌ Missing: │         │ ❌ No certifi│                  │
│  │ - SSL_MIN_  │         │    fallback  │                  │
│  │   VERSION   │         │              │                  │
│  │ - CA_CERTS  │         │ ⚠️  Logs full│                  │
│  │ - BASE_DIR  │         │    URL with  │                  │
│  │             │         │    password  │                  │
│  └─────────────┘         └──────────────┘                  │
│                                                             │
│              ┌────────────────────┐                         │
│              │ Monitoring Config  │                         │
│              │                    │                         │
│              │ ❌ replace('/0',  │                         │
│              │    '/1') breaks   │                         │
│              │    on edge cases  │                         │
│              └────────────────────┘                         │
│                                                             │
└─────────────────────┬───────────────────────────────────────┘
                      │ ❌ SSL Handshake Fails
                      │    (No CA certs)
                      ▼
            ┌──────────────────┐
            │  Redis Cloud     │
            │  (SSL Required)  │
            │                  │
            │  rediss://       │
            │  host:6380       │
            └──────────────────┘
```

---

### Proposed Architecture (Fixed)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Application Layer                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐         ┌─────────────────────────┐          │
│  │  Settings        │         │  Redis Manager          │          │
│  │  (config.py)     │         │  (redis_manager.py)     │          │
│  │                  │         │                         │          │
│  │ ✅ New Fields:   │────────▶│ ✅ Certifi Fallback:    │          │
│  │ - SSL_MIN_       │         │    if no custom CA:     │          │
│  │   VERSION        │         │    → use certifi.where()│          │
│  │ - CA_CERTS       │         │                         │          │
│  │ - BASE_DIR       │         │ ✅ Secure Logging:      │          │
│  │                  │         │    scheme=rediss        │          │
│  │ ✅ Validation:   │         │    host=redis-xxx       │          │
│  │ - Verify certifi │         │    port=6380            │          │
│  │ - Check TLS ver  │         │    tls=TLSV1_2          │          │
│  │ - Validate CA    │         │    cert_reqs=required   │          │
│  └──────────────────┘         │    ❌ NO PASSWORD       │          │
│                               └─────────────────────────┘          │
│                                                                     │
│              ┌──────────────────────────────────┐                  │
│              │  Monitoring Config               │                  │
│              │  (monitoring/config.py)          │                  │
│              │                                  │                  │
│              │ ✅ urllib.parse:                 │                  │
│              │    1. Parse URL                  │                  │
│              │    2. Split path by '/'          │                  │
│              │    3. Replace last digit         │                  │
│              │    4. Reconstruct URL            │                  │
│              │                                  │                  │
│              │ ✅ Handles:                      │                  │
│              │    - /0 → /1                     │                  │
│              │    - (empty) → /1                │                  │
│              │    - /path/0 → /path/1           │                  │
│              └──────────────────────────────────┘                  │
│                                                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │ ✅ SSL Handshake Success
                         │    (Certifi CA certs)
                         ▼
               ┌────────────────────┐
               │  Redis Cloud       │
               │  (SSL/TLS 1.2/1.3) │
               │                    │
               │  rediss://         │
               │  host:6380         │
               │  ✅ Verified        │
               └────────────────────┘
```

---

## 2. SSL/TLS Certificate Validation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Redis Connection Initialization              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                   ┌────────────────────────┐
                   │ Check REDIS_SSL=true?  │
                   └────────┬───────────────┘
                            │
                 ┌──────────┴──────────┐
                 │                     │
              YES│                     │NO
                 ▼                     ▼
    ┌────────────────────┐   ┌──────────────────┐
    │ Check CERT_REQS    │   │ Use non-SSL      │
    │ Setting            │   │ redis://         │
    └────────┬───────────┘   └──────────────────┘
             │
             ├──────┬──────┬──────┐
             │      │      │      │
          none  optional required │
             │      │      │      │
             ▼      ▼      ▼      │
    ┌─────────────────────────┐  │
    │ CERT_NONE               │  │
    │ (No validation)         │  │
    └─────────────────────────┘  │
                                 │
    ┌─────────────────────────┐  │
    │ CERT_OPTIONAL           │  │
    │ (Validate if present)   │  │
    └─────────────────────────┘  │
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │ CERT_REQUIRED          │
                    │ (MUST validate)        │
                    └────────┬───────────────┘
                             │
                  ┌──────────┴───────────┐
                  │                      │
                  ▼                      ▼
    ┌──────────────────────┐   ┌─────────────────────┐
    │ REDIS_SSL_CA_CERTS   │   │ No custom CA        │
    │ specified?           │   │                     │
    └──────┬───────────────┘   │                     │
           │                   │                     │
        YES│                   │                     │
           ▼                   ▼                     │
    ┌──────────────────┐   ┌──────────────────────┐ │
    │ Resolve Path:    │   │ CERTIFI FALLBACK:    │ │
    │ - Absolute?      │   │                      │ │
    │   → Use directly │   │ import certifi       │ │
    │ - Relative?      │   │ ca_certs =           │ │
    │   → Join with    │   │   certifi.where()    │ │
    │     BASE_DIR     │   │                      │ │
    └──────┬───────────┘   └──────────┬───────────┘ │
           │                          │             │
           │  ┌───────────────────────┘             │
           │  │                                     │
           ▼  ▼                                     │
    ┌────────────────────┐                         │
    │ Check file exists? │                         │
    └────────┬───────────┘                         │
             │                                     │
      ┌──────┴──────┐                             │
      │             │                             │
   YES│             │NO                           │
      ▼             ▼                             │
┌─────────┐   ┌────────────┐                     │
│ Use CA  │   │ Log Error, │                     │
│ cert    │   │ Fallback to│                     │
│ file    │   │ certifi    │                     │
└────┬────┘   └──────┬─────┘                     │
     │               │                           │
     └───────┬───────┘                           │
             │                                   │
             ▼                                   │
    ┌────────────────────┐                      │
    │ Configure          │                      │
    │ connection_kwargs: │                      │
    │ - ssl_cert_reqs    │                      │
    │ - ssl_ca_certs     │                      │
    │ - ssl_min_version  │◀─────────────────────┘
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ Create Connection  │
    │ Pool with SSL      │
    └────────┬───────────┘
             │
             ▼
    ┌────────────────────┐
    │ TLS Handshake      │
    │ with Redis Server  │
    └────────┬───────────┘
             │
      ┌──────┴──────┐
      │             │
   SUCCESS        FAIL
      │             │
      ▼             ▼
┌──────────┐   ┌──────────┐
│ Log:     │   │ Log:     │
│ ✅ SSL   │   │ ❌ SSL   │
│ Connected│   │ Error    │
│          │   │ + Details│
└──────────┘   └──────────┘
```

---

## 3. URL Parsing Flow (monitoring/config.py)

### Before (Brittle String Replacement)

```
Input: rediss://user:pass@host:6380/0

     │
     ▼
┌────────────────────┐
│ replace('/0','/1') │  ❌ Only works if exactly '/0'
└────────┬───────────┘
         │
         ▼
Output: rediss://user:pass@host:6380/1  (works)

───────────────────────────────────────────────

Input: rediss://user:pass@host:6380

     │
     ▼
┌────────────────────┐
│ replace('/0','/1') │  ❌ No match, nothing happens
└────────┬───────────┘
         │
         ▼
Output: rediss://user:pass@host:6380  (BROKEN - still DB 0)

───────────────────────────────────────────────

Input: rediss://user:pass@host:6380/10

     │
     ▼
┌────────────────────┐
│ replace('/0','/1') │  ❌ Matches '/10' → '/11'
└────────┬───────────┘
         │
         ▼
Output: rediss://user:pass@host:6380/11  (BROKEN - wrong DB)
```

---

### After (Robust URL Parsing)

```
Input: rediss://user:pass@host:6380/0

     │
     ▼
┌──────────────────────┐
│ urlparse(redis_url)  │
└──────────┬───────────┘
           │
           ▼
    ┌──────────────┐
    │ ParseResult: │
    │ - scheme     │
    │ - netloc     │
    │ - path='/0'  │
    │ - params     │
    │ - query      │
    └──────┬───────┘
           │
           ▼
┌─────────────────────────┐
│ path.split('/')         │
│ → ['', '0']             │
│                         │
│ Filter empty strings:   │
│ → ['0']                 │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Is last element digit?  │
│ YES: '0'.isdigit()      │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Replace with new DB:    │
│ path_parts[-1] = '1'    │
│ → ['1']                 │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Reconstruct path:       │
│ '/' + '/'.join(['1'])   │
│ → '/1'                  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ parsed._replace(        │
│   path='/1'             │
│ )                       │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ urlunparse()            │
└──────────┬──────────────┘
           │
           ▼
Output: rediss://user:pass@host:6380/1  ✅

───────────────────────────────────────────────

Edge Cases Handled:

Input: rediss://host:6380
→ path_parts = []
→ Append '1'
→ Output: rediss://host:6380/1  ✅

Input: rediss://host:6380/10
→ path_parts = ['10']
→ Replace '10' with '1'
→ Output: rediss://host:6380/1  ✅

Input: rediss://host:6380/path/2
→ path_parts = ['path', '2']
→ Replace '2' with '1'
→ Output: rediss://host:6380/path/1  ✅

Input: rediss://host/
→ path_parts = []
→ Append '1'
→ Output: rediss://host/1  ✅
```

---

## 4. Component Dependency Diagram

```
┌────────────────────────────────────────────────────────────┐
│                      Application Startup                   │
└───────────────────────────┬────────────────────────────────┘
                            │
                            ▼
                 ┌──────────────────┐
                 │  Load Settings   │
                 │  (config.py)     │
                 └────────┬─────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌──────────────┐
│ REDIS_SSL       │ │ CA_CERTS    │ │ SSL_MIN_     │
│ CERT_REQS       │ │ BASE_DIR    │ │ VERSION      │
└────────┬────────┘ └──────┬──────┘ └──────┬───────┘
         │                 │               │
         └────────┬────────┴───────────────┘
                  │
                  ▼
         ┌────────────────────┐
         │ Validate Config    │
         │ (production check) │
         └────────┬───────────┘
                  │
       ┌──────────┴───────────┐
       │                      │
       ▼                      ▼
┌──────────────┐    ┌─────────────────────┐
│ Check certifi│    │ Verify TLS version  │
│ available    │    │ (TLSV1_2/TLSV1_3)   │
└──────┬───────┘    └─────────┬───────────┘
       │                      │
       └──────────┬───────────┘
                  │ Config Valid
                  ▼
         ┌────────────────────┐
         │ Initialize Redis   │
         │ Manager            │
         └────────┬───────────┘
                  │
       ┌──────────┴────────────┐
       │                       │
       ▼                       ▼
┌──────────────┐      ┌────────────────┐
│ Async Client │      │ Sync Client    │
│ (async ops)  │      │ (legacy code)  │
└──────┬───────┘      └────────┬───────┘
       │                       │
       │  ┌────────────────────┘
       │  │
       ▼  ▼
┌─────────────────┐
│ Connection Pool │
│ (SSL configured)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Redis Cloud     │
│ (rediss://...)  │
└─────────────────┘

Dependencies (left to right):
  Settings → RedisManager → ConnectionPool → RedisCloud
  Settings → MonitoringConfig → MonitoringRedisClient → RedisCloud
```

---

## 5. Logging Architecture (Security)

### Information Flow

```
┌──────────────────────────────────────────────────────────┐
│              Application Component                       │
│                                                          │
│  ┌────────────────────────┐                             │
│  │ RedisManager.__init__  │                             │
│  │                        │                             │
│  │ redis_url =            │                             │
│  │  "rediss://user:       │  ❌ SENSITIVE DATA          │
│  │   PASSWORD@host:6380"  │     (In memory only)        │
│  └────────┬───────────────┘                             │
│           │                                             │
│           ▼                                             │
│  ┌────────────────────────┐                             │
│  │ Parse URL for logging  │                             │
│  │                        │                             │
│  │ from urllib.parse      │                             │
│  │   import urlparse      │                             │
│  │                        │                             │
│  │ parsed = urlparse(url) │                             │
│  └────────┬───────────────┘                             │
│           │                                             │
│           ▼                                             │
│  ┌────────────────────────────────┐                     │
│  │ Extract SAFE fields:           │                     │
│  │ - scheme = parsed.scheme       │  ✅ SAFE TO LOG     │
│  │ - hostname = parsed.hostname   │                     │
│  │ - port = parsed.port           │                     │
│  │ - db = self.db_number          │                     │
│  │                                │                     │
│  │ ❌ NEVER extract:              │                     │
│  │ - parsed.password              │                     │
│  │ - parsed.netloc (has password) │                     │
│  └────────┬───────────────────────┘                     │
│           │                                             │
│           ▼                                             │
│  ┌────────────────────────────────────────┐             │
│  │ logger.info(                           │             │
│  │   f"Redis: scheme={scheme}, "          │             │
│  │   f"host={hostname}, "                 │             │
│  │   f"port={port}, db={db}, "            │             │
│  │   f"ssl={settings.REDIS_SSL}, "        │             │
│  │   f"tls_version={tls_ver}, "           │             │
│  │   f"cert_validation={cert_reqs}"       │             │
│  │ )                                      │             │
│  └────────┬───────────────────────────────┘             │
└───────────┼──────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────┐
│         Log Output                 │
│                                    │
│ ✅ SAFE: Shows connection details  │
│    without exposing credentials    │
│                                    │
│ Example:                           │
│ "Redis async connection:           │
│  scheme=rediss,                    │
│  host=redis-xxx.railway.app,       │
│  port=6380,                        │
│  db=1,                             │
│  ssl=True,                         │
│  tls_version=TLSV1_2,              │
│  cert_validation=required"         │
│                                    │
│ ❌ NEVER includes password         │
└────────────────────────────────────┘
```

---

## 6. Data Flow Diagram (End-to-End)

```
┌──────────┐         ┌──────────┐         ┌────────────┐
│ .env     │────────▶│ Settings │────────▶│ Validation │
│          │ Load    │ Class    │ Validate│ Logic      │
│ REDIS_   │ env     │          │ at init │            │
│ SSL=true │ vars    │          │         │            │
└──────────┘         └──────────┘         └──────┬─────┘
                                                  │
                                           ┌──────┴──────┐
                                           │ Config OK?  │
                                           └──────┬──────┘
                                                  │ YES
                                                  ▼
                                         ┌────────────────┐
                                         │ Redis Manager  │
                                         │ Initialization │
                                         └────────┬───────┘
                                                  │
                                    ┌─────────────┴────────────┐
                                    │                          │
                                    ▼                          ▼
                           ┌────────────────┐       ┌─────────────────┐
                           │ Async Client   │       │ Sync Client     │
                           │ Creation       │       │ Creation        │
                           └────────┬───────┘       └─────────┬───────┘
                                    │                         │
                         ┌──────────┴──────────┐   ┌──────────┴──────┐
                         │                     │   │                 │
                         ▼                     ▼   ▼                 ▼
                  ┌──────────┐         ┌──────────────┐      ┌──────────┐
                  │ Check    │         │ Certifi      │      │ Custom   │
                  │ CERT_REQS│         │ Fallback     │      │ CA Path  │
                  └────┬─────┘         └──────┬───────┘      └────┬─────┘
                       │                      │                   │
                  ┌────┴────┐          ┌──────┴──────┐            │
                  │         │          │             │            │
               none    required    certifi.where()  File.exists() │
                  │         │          │             │            │
                  ▼         ▼          └──────┬──────┴────────────┘
            ┌──────────┐  ┌────────────────────────┐
            │ CERT_NONE│  │ Set ssl_ca_certs param │
            └────┬─────┘  └──────────┬─────────────┘
                 │                   │
                 └───────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Configure TLS Version│
              │ (if MIN_VERSION set) │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Create Connection    │
              │ Pool with SSL params │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Log Connection Info  │
              │ (NO PASSWORD)        │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ Attempt Connection   │
              │ to Redis Cloud       │
              └──────────┬───────────┘
                         │
                  ┌──────┴──────┐
                  │             │
               SUCCESS         FAIL
                  │             │
                  ▼             ▼
         ┌────────────┐  ┌─────────────┐
         │ Log Success│  │ Log Error + │
         │ Return     │  │ Connection  │
         │ Client     │  │ Details     │
         └────────────┘  └─────────────┘
```

---

## 7. Deployment Pipeline

```
┌────────────────────────────────────────────────────────────┐
│                   Development Phase                        │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ 1. Code Changes      │
            │    - config.py       │
            │    - redis_manager   │
            │    - monitoring      │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ 2. Unit Tests        │
            │    pytest tests/     │
            │    test_redis_ssl_*  │
            └──────────┬───────────┘
                       │
                ┌──────┴──────┐
                │             │
             PASS           FAIL
                │             │
                │             └──────▶ Fix & Retry
                ▼
            ┌──────────────────────┐
            │ 3. Integration Tests │
            │    Real Redis        │
            │    connection        │
            └──────────┬───────────┘
                       │
                ┌──────┴──────┐
                │             │
             PASS           FAIL
                │             │
                │             └──────▶ Debug & Fix
                ▼
┌──────────────────────────────────────────────────────────┐
│                   Staging Deployment                     │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ 4. Deploy to Staging │
            │    Railway PR Deploy │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ 5. Smoke Tests       │
            │    - Health check    │
            │    - Redis ping      │
            │    - Log inspection  │
            └──────────┬───────────┘
                       │
                ┌──────┴──────┐
                │             │
             PASS           FAIL
                │             │
                │             └──────▶ Rollback & Debug
                ▼
┌──────────────────────────────────────────────────────────┐
│                 Production Deployment                    │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ 6. Deploy to Prod    │
            │    Railway Main      │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │ 7. Monitor (15 min)  │
            │    - Logs            │
            │    - Metrics         │
            │    - Errors          │
            └──────────┬───────────┘
                       │
                ┌──────┴──────┐
                │             │
              OK             ISSUES
                │             │
                │             ▼
                │      ┌────────────────┐
                │      │ Rollback Plan: │
                │      │ - Revert commit│
                │      │ - Set SSL=false│
                │      │ - Restart      │
                │      └────────────────┘
                ▼
         ┌──────────────┐
         │ 8. Success!  │
         │    Monitor   │
         │    24 hours  │
         └──────────────┘
```

---

## Legend

### Symbols Used

- ✅ = Success / Implemented / Secure
- ❌ = Failure / Missing / Insecure
- ⚠️ = Warning / Caution
- → = Data flow / Process flow
- ▼ = Next step / Downward flow
- ─ = Connection / Relationship

### Component Types

```
┌──────────┐
│ Process  │  = Action or operation
└──────────┘

┌──────────┐
│ Decision │  = Conditional logic
└──────────┘

┌──────────┐
│ External │  = External system/service
│ Service  │
└──────────┘

┌────────────────┐
│ Configuration  │  = Settings or config
│ Data           │
└────────────────┘
```

---

**Document Version**: 1.0.0
**Related Documents**:
- [redis-ssl-tls-configuration-plan.md](./redis-ssl-tls-configuration-plan.md) - Full architectural plan
- [redis-ssl-tls-implementation-summary.md](./redis-ssl-tls-implementation-summary.md) - Quick reference
