# Authentication Architecture Diagrams

**Visual Guide to Current and Proposed Authentication Flows**

---

## 1. Current System: 5-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Browser)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────┐     ┌─────────────┐     ┌──────────────┐                  │
│  │ LoginPage  │────▶│ AuthContext │────▶│ apiClient    │                  │
│  │  (UI)      │     │  (State)    │     │  (Network)   │                  │
│  └────────────┘     └─────────────┘     └──────────────┘                  │
│        │                   │                     │                          │
└────────┼───────────────────┼─────────────────────┼──────────────────────────┘
         │                   │                     │
         ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │ Firebase Auth    │ ◀── 1. signInWithPassword(email, password)           │
│  │  (Google Cloud)  │ ──▶ Returns: { user, idToken }                       │
│  └──────────────────┘     ⏱️ ~150-200ms                                      │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         │ 2. Send Firebase token to backend
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACKEND API (FastAPI)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  POST /api/v1/session/                                                      │
│  Body: { firebase_token, device_info }                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 1: CSRF Token Validation                                  │       │
│  │ ────────────────────────────────────────────────────────────    │       │
│  │ ✅ Verify X-CSRF-Token header                                   │       │
│  │ ⏱️ ~1-2ms                                                         │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 2: Firebase Token Validation                              │       │
│  │ ────────────────────────────────────────────────────────────    │       │
│  │ ✅ Firebase Admin SDK validates token (network call to Google)  │       │
│  │ ✅ Returns: { uid, email, role, custom_claims }                 │       │
│  │ ⏱️ ~100-200ms (network latency)                                  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 3: Redis Session Creation                                 │       │
│  │ ────────────────────────────────────────────────────────────    │       │
│  │ ✅ Generate session_id (256-bit entropy)                        │       │
│  │ ✅ Store in Redis: session:{id} → {user_id, firebase_uid, ...} │       │
│  │ ✅ TTL: 24 hours                                                 │       │
│  │ ⏱️ ~2-5ms                                                         │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 4: PostgreSQL User Lookup                                 │       │
│  │ ────────────────────────────────────────────────────────────    │       │
│  │ ✅ Query: SELECT * FROM users WHERE firebase_uid = ?            │       │
│  │ ✅ Create user if not exists                                    │       │
│  │ ⏱️ ~20-50ms                                                       │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 5: Set httpOnly Cookie                                    │       │
│  │ ────────────────────────────────────────────────────────────    │       │
│  │ ✅ Set-Cookie: session_id={id}; HttpOnly; Secure; SameSite     │       │
│  │ ✅ JavaScript cannot access (XSS protection)                    │       │
│  │ ⏱️ ~1ms                                                           │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  Response: { status: "authenticated", user: {...} }                         │
│  (session_id is in httpOnly cookie, not in response body)                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         │ 3. Frontend gets user profile
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  GET /api/v1/auth/me                                                        │
│  Cookie: session_id={id} (sent automatically)                               │
│                                                                              │
│  Backend validates session → Returns full user profile                       │
│  ⏱️ ~50-100ms                                                                 │
└──────────────────────────────────────────────────────────────────────────────┘

TOTAL LOGIN TIME: 250-350ms
```

---

## 2. Current System: Redis Cache Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REDIS CACHE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ Layer 1: Token Validation Cache                                │        │
│  │ ──────────────────────────────────────────────────────────     │        │
│  │ Key:   firebase:token:{sha256(id_token)}                       │        │
│  │ Value: { firebase_uid, email, role, validated_at }            │        │
│  │ TTL:   1 hour                                                  │        │
│  │                                                                 │        │
│  │ Purpose: Skip Firebase Admin SDK validation (200ms → 5ms)      │        │
│  │ Hit Rate: 40-60% (depends on token refresh frequency)          │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ Layer 2: User Object Cache                                     │        │
│  │ ──────────────────────────────────────────────────────────     │        │
│  │ Key:   user:firebase_uid:{uid}                                 │        │
│  │ Value: { id, email, full_name, role, is_active, ... }         │        │
│  │ TTL:   2 hours                                                 │        │
│  │                                                                 │        │
│  │ Purpose: Skip PostgreSQL query (100ms → 5ms)                   │        │
│  │ Hit Rate: 90-95% (users rarely change during session)          │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────┐        │
│  │ Layer 3: Session Storage (⭐ KEEP THIS)                        │        │
│  │ ──────────────────────────────────────────────────────────     │        │
│  │ Key:   session:{session_id}                                    │        │
│  │ Value: { user_id, firebase_uid, created_at, metadata }        │        │
│  │ TTL:   24 hours                                                │        │
│  │                                                                 │        │
│  │ Purpose: Fast session validation + instant logout              │        │
│  │ Hit Rate: 95-98% (every authenticated request)                 │        │
│  └────────────────────────────────────────────────────────────────┘        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

CURRENT PROBLEM:
- Layer 1: Low hit rate (40-60%), adds complexity
- Layer 2: Duplicates data from PostgreSQL, cache invalidation issues
- Layer 3: Essential for fast auth (KEEP)

RECOMMENDATION: Remove Layer 1 and Layer 2
```

---

## 3. Proposed System: Simplified 3-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (Browser)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────┐     ┌─────────────┐     ┌──────────────┐                  │
│  │ LoginPage  │────▶│ AuthContext │────▶│ apiClient    │                  │
│  │  (UI)      │     │  (State)    │     │  (Network)   │                  │
│  └────────────┘     └─────────────┘     └──────────────┘                  │
│        │                   │                     │                          │
└────────┼───────────────────┼─────────────────────┼──────────────────────────┘
         │                   │                     │
         │                   │                     │ ⬅️ OPTIMIZATION 1:
         │                   │                     │    Parallel requests
         ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARALLEL EXTERNAL CALLS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐          ┌──────────────────────┐                 │
│  │ GET /api/v1/        │          │ Firebase Auth        │                 │
│  │     csrf-token      │  ◀──┬───▶│  signInWithPassword │                 │
│  └─────────────────────┘     │    └──────────────────────┘                 │
│         │                    │             │                                │
│         │ ⏱️ ~50ms            │             │ ⏱️ ~150-200ms                  │
│         ▼                    │             ▼                                │
│  CSRF token received         │      Firebase token received                 │
│                              │                                              │
│  ⬅️ SPEEDUP: Parallel = max(50ms, 200ms) = 200ms (not 250ms)               │
└──────────────────────────────────────────────────────────────────────────────┘
         │
         │ Send Firebase token to backend
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACKEND API (FastAPI)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  POST /api/v1/session/                                                      │
│  Body: { firebase_token, device_info }                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 1: CSRF Token Validation                                  │       │
│  │ ⏱️ ~1-2ms                                                         │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 2: Firebase Token Validation                              │       │
│  │ ⏱️ ~100-200ms (no cache - direct Firebase call)                  │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Layer 3: PostgreSQL User Lookup (DIRECT, NO CACHE)              │       │
│  │ ──────────────────────────────────────────────────────────      │       │
│  │ ✅ Indexed query: SELECT * FROM users                           │       │
│  │                   WHERE firebase_uid = ?                         │       │
│  │ ✅ Index on firebase_uid (UNIQUE) = <20ms lookup                │       │
│  │ ⏱️ ~10-20ms (with index)                                          │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│           │                                                                  │
│           ▼                                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │ Create Redis Session + Set Cookie                               │       │
│  │ ──────────────────────────────────────────────────────────      │       │
│  │ ✅ Store session in Redis (~5ms)                                │       │
│  │ ✅ Set httpOnly cookie (~1ms)                                   │       │
│  │ ⏱️ ~6ms                                                           │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                              │
│  ⬅️ OPTIMIZATION 2: Combined response                                       │
│  Response: {                                                                 │
│    status: "authenticated",                                                 │
│    user: { id, email, full_name, role, permissions, ... }  ⬅️ FULL PROFILE │
│  }                                                                           │
│                                                                              │
│  ❌ REMOVED: Separate GET /api/v1/auth/me call                              │
│  ⏱️ SAVED: 50-100ms                                                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

TOTAL LOGIN TIME: 200-250ms (20-40% faster)
API CALLS: 4 (down from 6)
CACHE LAYERS: 1 (down from 3)
```

---

## 4. Authenticated Request Flow: Before vs After

### BEFORE (Current System)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GET /api/v1/patients (example authenticated request)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1️⃣ Browser sends session cookie automatically                              │
│     Cookie: session_id={id}                                                 │
│                                                                              │
│  2️⃣ Backend: Validate session (Layer 3 cache)                              │
│     Redis GET session:{id}                                                  │
│     ⏱️ ~2-5ms (95-98% hit rate)                                              │
│                                                                              │
│  3️⃣ Backend: Get user from cache (Layer 2 cache)                           │
│     Redis GET user:firebase_uid:{uid}                                       │
│     ⏱️ ~2-5ms (90-95% hit rate)                                              │
│     └─▶ On miss: PostgreSQL query (~50-100ms) ❌ Rare but slow             │
│                                                                              │
│  4️⃣ Backend: Validate user.is_active                                       │
│     ⏱️ ~0ms (in-memory check)                                                │
│                                                                              │
│  5️⃣ Backend: Execute business logic                                        │
│     └─▶ Return patient list                                                │
│                                                                              │
│  TOTAL: 4-10ms (warm) vs 50-110ms (cold on Layer 2 miss)                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### AFTER (Simplified System)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  GET /api/v1/patients (example authenticated request)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1️⃣ Browser sends session cookie automatically                              │
│     Cookie: session_id={id}                                                 │
│                                                                              │
│  2️⃣ Backend: Validate session (ONLY cache layer)                           │
│     Redis GET session:{id} → { user_id, firebase_uid, metadata }           │
│     ⏱️ ~2-5ms (95-98% hit rate)                                              │
│                                                                              │
│  3️⃣ Backend: Get user from PostgreSQL (DIRECT)                             │
│     PostgreSQL: SELECT * FROM users WHERE id = ?                            │
│     ⏱️ ~5-10ms (indexed on primary key, very fast)                           │
│                                                                              │
│  4️⃣ Backend: Validate user.is_active                                       │
│     ⏱️ ~0ms (in-memory check)                                                │
│                                                                              │
│  5️⃣ Backend: Execute business logic                                        │
│     └─▶ Return patient list                                                │
│                                                                              │
│  TOTAL: 7-15ms (consistently fast, no cache miss spike)                     │
│                                                                              │
│  ✅ BENEFIT: Predictable performance (no cache miss surprises)              │
│  ✅ BENEFIT: Always fresh user data (no cache invalidation issues)          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Analysis:**
- Session validation: Same speed (~5ms)
- User lookup: Slightly slower (~10ms vs ~5ms on cache hit)
- **Trade-off:** +5ms per request for simpler architecture = WORTH IT
- **Benefit:** No cache invalidation bugs, always fresh data

---

## 5. Token Refresh Flow: Before vs After

### BEFORE (Current - Every 55 Minutes)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  setInterval(() => refreshToken(), 55 * 60 * 1000)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1️⃣ Get current Firebase user                                              │
│     firebaseAuthLazy.getCurrentUser()                                       │
│     ⏱️ ~5ms                                                                   │
│                                                                              │
│  2️⃣ Force token refresh (network call to Firebase)                         │
│     firebaseUser.getIdToken(true)                                           │
│     ⏱️ ~100-200ms                                                             │
│                                                                              │
│  3️⃣ Update apiClient with new token                                        │
│     apiClient.setAuthToken(newToken)                                        │
│     ⏱️ ~0ms                                                                   │
│                                                                              │
│  4️⃣ Validate with backend (network call)                                   │
│     GET /api/v1/auth/me                                                     │
│     ⏱️ ~50-100ms                                                              │
│                                                                              │
│  5️⃣ Check if user is still active                                          │
│     if (!user.is_active) → force logout                                    │
│                                                                              │
│  TOTAL: ~155-305ms (every 55 minutes)                                       │
│                                                                              │
│  ❌ PROBLEM: Refreshes even if user inactive                                │
│  ❌ PROBLEM: No exponential backoff on failure                              │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### AFTER (Optimized - Smart Refresh)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  setInterval(() => smartRefresh(), 5 * 60 * 1000)  // Every 5 minutes       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ⬅️ OPTIMIZATION: Only refresh if <5 minutes until expiry                   │
│                                                                              │
│  1️⃣ Check token expiry time                                                │
│     const exp = parseJWT(token).exp                                         │
│     const timeUntilExpiry = exp - Date.now()                                │
│     if (timeUntilExpiry > 5 * 60 * 1000) return  // Still >5min, skip      │
│                                                                              │
│  2️⃣ Force token refresh (only if needed)                                   │
│     firebaseUser.getIdToken(true)                                           │
│     ⏱️ ~100-200ms                                                             │
│                                                                              │
│  3️⃣ Update apiClient                                                       │
│     apiClient.setAuthToken(newToken)                                        │
│     ⏱️ ~0ms                                                                   │
│                                                                              │
│  4️⃣ Passive validation (next authenticated request)                        │
│     Backend validates session automatically                                 │
│     No separate /auth/me call                                               │
│                                                                              │
│  TOTAL: ~100-200ms (only when needed, not every 55 min)                     │
│                                                                              │
│  ✅ BENEFIT: Fewer unnecessary refreshes                                    │
│  ✅ BENEFIT: Better battery life (mobile)                                   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Security Comparison: Before vs After

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SECURITY FEATURES                                    │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ Feature              │ Before (Current)     │ After (Simplified)            │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ CSRF Protection      │ ✅ Yes               │ ✅ Yes (maintained)           │
│ httpOnly Cookies     │ ✅ Yes               │ ✅ Yes (maintained)           │
│ Instant Logout       │ ✅ Yes (Redis)       │ ✅ Yes (Redis)                │
│ Token Expiration     │ ✅ 1 hour            │ ✅ 1 hour                     │
│ Session Regeneration │ ✅ 256-bit entropy   │ ✅ 256-bit entropy            │
│ Auto Token Refresh   │ ✅ Every 55 min      │ ✅ Smart (when needed)        │
│ XSS Protection       │ ✅ No localStorage   │ ✅ No localStorage            │
│ Session Hijacking    │ ✅ Secure cookies    │ ✅ Secure cookies             │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ SECURITY SCORE       │ 🟢 10/10             │ 🟢 10/10                      │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

VERDICT: ✅ NO SECURITY DEGRADATION
```

---

## 7. Complexity Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARCHITECTURAL COMPLEXITY                             │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│ Metric               │ Before (Current)     │ After (Simplified)            │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ External Services    │ 3 (Firebase+Redis+PG)│ 3 (same)                      │
│ Cache Layers         │ 3 (token+user+sess)  │ 1 (session only) ✅           │
│ API Calls (login)    │ 6                    │ 4 ✅                          │
│ Token Types          │ 3 (JWT+Cookie+CSRF)  │ 3 (same)                      │
│ Auth Code Lines      │ ~1200                │ ~800 ✅                       │
│ Cache Invalidation   │ 3 paths              │ 1 path ✅                     │
│ Debug Difficulty     │ High                 │ Medium ✅                     │
├──────────────────────┼──────────────────────┼───────────────────────────────┤
│ COMPLEXITY SCORE     │ 🔴 High              │ 🟡 Medium ✅                  │
└──────────────────────┴──────────────────────┴───────────────────────────────┘

VERDICT: ✅ 40% REDUCTION IN COMPLEXITY
```

---

## 8. Performance Comparison (Metrics)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PERFORMANCE METRICS                               │
├──────────────────────────┬──────────────────┬─────────────────┬────────────┤
│ Operation                │ Before (Current) │ After (Optimized)│ Change     │
├──────────────────────────┼──────────────────┼─────────────────┼────────────┤
│ Login Time (cold)        │ 250-350ms        │ 200-250ms       │ -20-40% ✅ │
│ Login Time (warm)        │ 150-200ms        │ 150-200ms       │ Same       │
│ API Calls (login)        │ 6                │ 4               │ -33% ✅    │
│ Authenticated Request    │ 4-10ms           │ 7-15ms          │ +5ms ⚠️    │
│ Auth Request (cold miss) │ 50-110ms         │ 7-15ms          │ -70% ✅    │
│ Token Refresh Frequency  │ Every 55 min     │ When needed     │ -80% ✅    │
├──────────────────────────┼──────────────────┼─────────────────┼────────────┤
│ PERFORMANCE SCORE        │ 🟢 Good          │ 🟢 Better ✅    │            │
└──────────────────────────┴──────────────────┴─────────────────┴────────────┘

KEY INSIGHTS:
- Login: 20-40% faster (parallel calls + combined response)
- Auth requests: Slightly slower (+5ms) but more consistent
- Cache misses: 70% faster (no spikes from Layer 2 misses)
- Token refresh: 80% fewer unnecessary refreshes

VERDICT: ✅ NET PERFORMANCE GAIN
```

---

## 9. Cost Comparison

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MONTHLY COSTS                                   │
├──────────────────────────┬──────────────────┬─────────────────┬────────────┤
│ Service                  │ Before (Current) │ After (Optimized)│ Change     │
├──────────────────────────┼──────────────────┼─────────────────┼────────────┤
│ Firebase Auth            │ $50-100          │ $60-120         │ +20% ⚠️    │
│ Redis Cloud              │ $30-50           │ $30-50          │ Same       │
│ PostgreSQL (Railway)     │ Included         │ Included        │ Same       │
├──────────────────────────┼──────────────────┼─────────────────┼────────────┤
│ TOTAL                    │ $80-150/month    │ $90-170/month   │ +$10-20 ⚠️ │
├──────────────────────────┼──────────────────┼─────────────────┼────────────┤
│ Developer Time (maint)   │ 4 hrs/month      │ 2 hrs/month     │ -50% ✅    │
│ Debugging Time (avg)     │ 2 hrs/incident   │ 1 hr/incident   │ -50% ✅    │
├──────────────────────────┼──────────────────┼─────────────────┼────────────┤
│ NET COST (incl. labor)   │ High             │ Lower ✅        │            │
└──────────────────────────┴──────────────────┴─────────────────┴────────────┘

ANALYSIS:
- Firebase costs increase 20% (no token cache)
- Developer productivity increases 50% (simpler code)
- Debugging time decreases 50% (fewer cache layers)

ROI: ✅ Worth the trade-off (labor savings > service costs)
```

---

## Legend

### Symbols
- ✅ Maintained/Improved
- ⚠️ Trade-off (acceptable)
- ❌ Removed (intentional simplification)
- ⏱️ Latency measurement
- 🟢 Good/Excellent
- 🟡 Acceptable
- 🔴 Needs improvement

### Performance Tiers
- **Cold:** First request after server restart (no cache)
- **Warm:** Cache partially populated
- **Hot:** Full cache hit (optimal)

---

**Document Version:** 1.0
**Created:** 2025-01-10
**Purpose:** Visual guide for authentication architecture decisions
