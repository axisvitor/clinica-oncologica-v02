# Quiz Mensal Interface - Comprehensive Architecture Analysis

**Date**: 2025-10-08
**Component**: quiz-mensal-interface
**Framework**: Next.js 14.2.33 (App Router)
**Analysis Type**: Full-stack Review

---

## 🎯 Executive Summary

The quiz-mensal-interface is a **Next.js 14 application** implementing a secure, client-side monthly health questionnaire system. It features **httpOnly cookie-based authentication**, **CSRF protection**, and comprehensive error handling. However, it has **critical production readiness issues** related to in-memory session storage.

### Key Strengths
✅ **Modern Stack**: Next.js 14 with App Router, TypeScript, Tailwind CSS 4
✅ **Security First**: CSRF tokens, httpOnly cookies, secure headers
✅ **Comprehensive UI**: Radix UI components with accessibility
✅ **Error Tracking**: Sentry integration configured
✅ **Testing Setup**: Jest with 75-80% coverage thresholds

### Critical Issues
❌ **P0**: In-memory session storage (loses data on restart/scale)
❌ **P0**: In-memory CSRF tokens (same issue)
❌ **P1**: No persistent backend for sessions (needs Redis/Supabase)
❌ **P1**: Sentry monitoring not verified as operational

---

## 📋 Architecture Overview

### Application Structure

```
quiz-mensal-interface/
├── app/                          # Next.js App Router
│   ├── api/                      # API Route Handlers
│   │   ├── csrf-token/route.ts   # CSRF token generation
│   │   └── quiz/                 # Quiz-specific endpoints
│   │       ├── initialize-session/   # Token → Cookie conversion
│   │       ├── submit-answer/        # Answer submission + CSRF
│   │       ├── session-status/       # Session validation
│   │       └── logout/              # Session cleanup
│   ├── layout.tsx                # Root layout with error boundaries
│   └── page.tsx                  # Main quiz page
├── components/
│   ├── quiz/                     # Quiz-specific components
│   │   ├── QuizContainer.tsx     # Main quiz wrapper
│   │   ├── QuizProgress.tsx      # Progress indicators
│   │   ├── QuizNavigation.tsx    # Navigation controls
│   │   └── QuestionRenderer/     # Question type renderers
│   ├── quiz-interface.tsx        # Legacy main component
│   ├── error/                    # Error boundaries
│   └── ui/                       # Radix UI components
├── hooks/
│   └── quiz/
│       └── useQuizState.ts       # Quiz state management hook
├── lib/
│   ├── api.ts                    # Backend API client
│   ├── auth-utils.ts             # Cookie auth + CSRF
│   └── monitoring/
│       └── sentry.ts             # Sentry configuration
├── tests/                        # Jest test suite
│   ├── quiz.test.tsx
│   ├── quiz-other-option.test.tsx
│   ├── security/                 # Security tests
│   ├── fixtures/                 # Test data
│   └── mocks/                    # Mock handlers
└── next.config.mjs               # Next.js configuration
```

---

## 🔒 Security Architecture

### 1. CSRF Protection

**File**: `app/api/csrf-token/route.ts`

```typescript
// Token Generation
- Generates 32-byte secure random token
- Stores in Map<sessionId, {token, expires}>
- Sets httpOnly cookie with session ID
- Token expiry: 1 hour

// Token Validation
export function validateCSRF(request, providedToken) {
  - Retrieves session ID from cookie
  - Validates token from in-memory Map
  - Checks expiration
  - Returns boolean
}
```

**⚠️ CRITICAL ISSUE**: In-memory storage means:
- Tokens lost on server restart
- Not suitable for horizontal scaling
- No persistence across deployments

**RECOMMENDATION**: Migrate to Redis or Supabase storage

### 2. Authentication Flow

**File**: `lib/auth-utils.ts`

```typescript
class SecureCookieAuth {
  // Step 1: Initialize Session
  async initializeSession(token: string) {
    1. Fetch CSRF token
    2. Call /api/quiz/initialize-session with URL token
    3. Backend calls quiz API to validate token
    4. Server creates session cookie (httpOnly, secure, sameSite)
    5. Returns QuizSession data
  }

  // Step 2: Submit Answers
  async submitAnswer(questionId, responseValue, metadata) {
    1. Get CSRF token
    2. Include X-CSRF-Token header
    3. Call /api/quiz/submit-answer
    4. Server retrieves session from cookie
    5. Server calls backend with stored token
    6. Handle token rotation if provided
  }

  // Step 3: Session Management
  async checkSession() - Validates session via /api/quiz/session-status
  async clearSession() - Logout + CSRF cleanup
}
```

**Security Features**:
- ✅ httpOnly cookies (prevents XSS token theft)
- ✅ CSRF tokens on all mutations
- ✅ Secure/SameSite cookie flags
- ✅ URL token cleanup (removed from browser after use)
- ✅ Token rotation support

**Security Concerns**:
- ❌ Session storage in-memory (Map)
- ❌ No session persistence
- ❌ No session replication for multi-instance

### 3. Security Headers

**File**: `next.config.mjs`

```javascript
headers: [
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  {
    key: 'Content-Security-Policy',
    value: "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'..."
  }
]
```

**Analysis**:
- ✅ Strong CSP policy with Railway backend whitelisted
- ✅ Frame protection (clickjacking prevention)
- ✅ MIME type sniffing prevention
- ⚠️ CSP includes 'unsafe-inline' and 'unsafe-eval' (necessary for Next.js but risky)

---

## 🔌 API Integration

### Backend Communication

**File**: `lib/api.ts` (QuizAPI class)

```typescript
class QuizAPI {
  // URL Resolution Priority:
  1. NEXT_PUBLIC_QUIZ_PUBLIC_API_URL (explicit full path)
  2. NEXT_PUBLIC_API_URL (base + auto-construct /api/v1/monthly-quiz-public)
  3. localhost:8000 (development fallback)

  // Features:
  - Timeout support (default 30s, configurable)
  - Retry logic with exponential backoff (3 attempts)
  - Network error detection
  - Retryable error classification (5xx, 408)
  - Debug logging (NEXT_PUBLIC_DEBUG_MODE=true)

  // Methods:
  async accessQuiz(token)      - Initializes quiz session
  async submitAnswer(...)      - Submits answer with retry
  async completeQuiz(token)    - Marks completion
  async healthCheck()          - API health status
}
```

**API Flow**:
```
User clicks link with token
  ↓
1. Client extracts token from URL
2. Client fetches CSRF token (/api/csrf-token)
3. Client calls /api/quiz/initialize-session
   ↓
   Server validates CSRF
   Server calls QuizAPI.accessQuiz(token)
   Backend validates token → returns QuizSession
   Server stores session in Map
   Server sets httpOnly cookie
   ↓
4. Client receives QuizSession data
5. Client renders quiz questions
   ↓
6. User answers question
7. Client calls /api/quiz/submit-answer
   ↓
   Server validates CSRF
   Server retrieves session from cookie
   Server calls QuizAPI.submitAnswer(session.token, ...)
   Backend saves answer
   Backend returns new_token if rotated
   Server updates session token
   ↓
8. Repeat steps 6-7 for all questions
9. Backend auto-completes on last answer
```

### Environment Configuration

**Priority**:
1. `NEXT_PUBLIC_QUIZ_PUBLIC_API_URL` - Explicit full endpoint
2. `NEXT_PUBLIC_API_URL` - Base URL (auto-appends path)
3. Fallback: `http://localhost:8000/api/v1/monthly-quiz-public`

**Current Setup** (from git status):
```bash
# Railway Production
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app
```

---

## 🎨 UI Components & State Management

### Question Types Support

**File**: `components/quiz-interface.tsx`

```typescript
Supported Question Types:
1. single_choice     - Radio buttons with optional "Outra" text input
2. multiple_choice   - Checkboxes with optional "Outra" text input
3. scale             - Visual scale selector (min-max range)
4. text              - Textarea for free-form responses
5. yes_no            - Simple yes/no radio selection

"Outra" Option Handling:
- Dynamically detects "other" options (allow_other flag)
- Shows text input when "Outra" selected
- Validates text is provided before submission
- Stores both option value + custom text
- Sends as {value: "other_option_id", customText: "user text"}
```

### State Management Hook

**File**: `hooks/quiz/useQuizState.ts`

```typescript
export function useQuizState({ session, onComplete }) {
  // Local State
  - currentQuestionIndex: number
  - selectedAnswer: SingleAnswer | MultipleAnswer | null
  - answers: Map<questionId, answer>
  - otherTexts: Map<questionId, customText>
  - isSubmitting: boolean
  - isCompleted: boolean

  // Computed Values
  - currentQuestion: QuizQuestion
  - totalQuestions: number
  - progress: number (percentage)
  - isLastQuestion: boolean

  // Methods
  async handleSubmitAnswer(questionId, responseValue, metadata) {
    1. Call secureCookieAuth.submitAnswer()
    2. Handle is_last_question flag
    3. Update local state
    4. Navigate to next question or completion screen
  }
}
```

**Key Features**:
- ✅ No localStorage usage (secure)
- ✅ Cookie-based auth via secureCookieAuth
- ✅ Automatic question navigation
- ✅ Answer validation before submission
- ✅ Support for complex answer types (arrays, other text)

---

## 📊 Monitoring & Error Handling

### Sentry Configuration

**File**: `lib/monitoring/sentry.ts` (14.7 KB)

```typescript
class QuizSentryMonitoring {
  // Integrations:
  - BrowserTracing: Client-side performance tracking
  - Replay: Session replay with masking
  - CaptureConsole: Error/warn console capture

  // Features:
  - Custom transaction naming for quiz flow
  - Quiz context tracking (sessionId, questionProgress)
  - User context management
  - API call tracking
  - Performance metrics
  - Error filtering (development noise)

  // Quiz-Specific Tracking:
  trackQuizStart(quizId, metadata)
  trackQuestionInteraction(number, total, action)
  trackQuizCompletion(score, totalQuestions, time)
  trackQuizError(errorType, error, context)
  trackApiCall(endpoint, method, status, duration)
}
```

**Configuration**:
```javascript
Environment: process.env.NODE_ENV
DSN: process.env.NEXT_PUBLIC_SENTRY_DSN
Traces Sample Rate: 0.1 (10%)
Replays Session Rate: 0.1 (10%)
Replays Error Rate: 1.0 (100% on errors)

Masked Elements:
- .quiz-answer-input (user answers)
- .user-email
- .sensitive-data

Ignored Errors:
- "Quiz session expired"
- "Network timeout"
- ResizeObserver warnings
- Browser extension errors
```

**⚠️ VERIFICATION NEEDED**: Sentry is configured but not confirmed operational. Need to:
1. Check if `NEXT_PUBLIC_SENTRY_DSN` is set
2. Verify events are being captured
3. Test error reporting

### Error Boundaries

```typescript
<ErrorBoundary>         - app/layout.tsx (root level)
<QuizErrorBoundary>     - components/error/QuizErrorBoundary.tsx
<ErrorFallback>         - components/error/ErrorFallback.tsx
```

---

## ⚡ Performance Optimizations

### Next.js Configuration

**File**: `next.config.mjs`

```javascript
Performance Features:
✅ output: 'standalone' - Optimized Docker deployment
✅ compress: true - Gzip compression
✅ swcMinify: true - Fast SWC minification
✅ optimizePackageImports: ['@radix-ui/*', 'lucide-react']
✅ Code splitting: vendor + common chunks
✅ Console removal in production (except error/warn)

Image Optimization:
✅ formats: ['webp', 'avif']
✅ Device sizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840]
✅ Remote patterns: Railway backend + localhost
```

### Bundle Optimization

```javascript
webpack: (config) => {
  config.optimization.splitChunks = {
    cacheGroups: {
      vendor: {
        name: 'vendor',
        test: /node_modules/,
        priority: 20
      },
      common: {
        name: 'common',
        minChunks: 2,
        priority: 10
      }
    }
  }
}
```

---

## 🧪 Testing Strategy

### Jest Configuration

**File**: `package.json`

```json
{
  "jest": {
    "preset": "ts-jest",
    "testEnvironment": "jsdom",
    "setupFilesAfterEnv": ["<rootDir>/tests/setup.ts"],
    "moduleNameMapper": {
      "\\.(css|less|scss|sass)$": "identity-obj-proxy",
      "^@/(.*)$": "<rootDir>/$1"
    },
    "coverageThreshold": {
      "global": {
        "branches": 75,
        "functions": 80,
        "lines": 80,
        "statements": 80
      }
    }
  }
}
```

### Test Files

```
tests/
├── quiz.test.tsx                    # Main quiz functionality
├── quiz-other-option.test.tsx       # "Outra" option handling
├── security/                        # Security-specific tests
├── fixtures/                        # Test data
└── mocks/                           # Mock handlers (MSW)
```

**Coverage Target**: 75-80%
**Test Framework**: Jest + Testing Library
**Mocking**: MSW (Mock Service Worker)

---

## 📦 Dependencies Analysis

### Core Dependencies

```json
{
  "next": "^14.2.33",
  "react": "^18",
  "typescript": "^5.9.2",

  // UI Components
  "@radix-ui/*": "Latest stable versions",
  "lucide-react": "^0.454.0",
  "tailwindcss": "^4.1.9",

  // Forms & Validation
  "react-hook-form": "^7.60.0",
  "@hookform/resolvers": "^3.10.0",
  "zod": "3.25.67",

  // Security
  "isomorphic-dompurify": "^2.28.0",

  // Analytics & Monitoring
  "@vercel/analytics": "1.3.1",
  "@sentry/nextjs": "Implied by monitoring/sentry.ts",

  // Charts & Data Viz
  "recharts": "2.15.4",

  // Dev Dependencies
  "@testing-library/react": "^14.1.2",
  "@testing-library/jest-dom": "^6.1.5",
  "jest": "^29.7.0",
  "msw": "^1.3.5"
}
```

---

## 🚨 Critical Issues & Recommendations

### P0 - Critical (Production Blockers)

#### Issue 1: In-Memory Session Storage
**Location**: `app/api/quiz/initialize-session/route.ts`

```typescript
// CURRENT (BROKEN):
const sessions = new Map<string, SessionData>()

// PROBLEM:
- Sessions lost on server restart
- No sharing between instances
- Memory leaks over time
- No horizontal scaling

// SOLUTION:
Use Supabase or Redis for persistent storage
```

**Implementation**:
```typescript
// Recommended: Supabase Storage
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
)

async function storeSession(sessionId: string, data: SessionData) {
  const { error } = await supabase
    .from('quiz_sessions')
    .upsert({
      session_id: sessionId,
      token: data.token,
      session_data: data.sessionData,
      expires_at: new Date(data.expires)
    })

  if (error) throw error
}

async function getSession(sessionId: string) {
  const { data, error } = await supabase
    .from('quiz_sessions')
    .select('*')
    .eq('session_id', sessionId)
    .gt('expires_at', new Date().toISOString())
    .single()

  if (error || !data) return null
  return {
    token: data.token,
    sessionData: data.session_data,
    expires: new Date(data.expires_at).getTime()
  }
}
```

#### Issue 2: In-Memory CSRF Tokens
**Location**: `app/api/csrf-token/route.ts`

Same problem as sessions - use Supabase/Redis.

```sql
-- Supabase Table Schema
CREATE TABLE csrf_tokens (
  session_id TEXT PRIMARY KEY,
  token TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_csrf_expires ON csrf_tokens(expires_at);

-- Auto-cleanup expired tokens
CREATE OR REPLACE FUNCTION cleanup_expired_csrf()
RETURNS void AS $$
BEGIN
  DELETE FROM csrf_tokens WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;
```

### P1 - High Priority

#### Issue 3: Sentry Not Verified
**Action Items**:
1. Set `NEXT_PUBLIC_SENTRY_DSN` in environment
2. Test error capture: `throw new Error("Test Sentry")`
3. Verify events appear in Sentry dashboard
4. Setup error alerts
5. Configure source maps upload for stack traces

#### Issue 4: No Backend Health Monitoring
**Recommendation**:
```typescript
// Add to components/quiz-interface.tsx
useEffect(() => {
  const checkHealth = async () => {
    const healthy = await quizAPI.healthCheck()
    if (!healthy) {
      // Show warning banner or offline mode
      setBackendStatus('offline')
    }
  }

  checkHealth()
  const interval = setInterval(checkHealth, 60000) // Check every minute
  return () => clearInterval(interval)
}, [])
```

### P2 - Medium Priority

#### Issue 5: Debug Logging in Production
```typescript
// lib/api.ts - Lines 76-82
if (typeof window !== 'undefined' && process.env.NEXT_PUBLIC_DEBUG_MODE === 'true') {
  console.log('[API Configuration]', {
    baseUrl: API_BASE_URL,
    // ... potentially sensitive data
  })
}
```

**Fix**: Remove or use proper logging service (Sentry breadcrumbs)

#### Issue 6: No Rate Limiting
Add rate limiting middleware to API routes:
```typescript
// middleware.ts
import { Ratelimit } from "@upstash/ratelimit"
import { Redis } from "@upstash/redis"

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, "1 m"), // 10 requests per minute
})

export async function middleware(request: Request) {
  const ip = request.headers.get("x-forwarded-for") ?? "127.0.0.1"
  const { success } = await ratelimit.limit(ip)

  if (!success) {
    return new Response("Too Many Requests", { status: 429 })
  }

  return NextResponse.next()
}
```

---

## 📋 Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)

```typescript
✅ Day 1-2: Setup Supabase
  - Create Supabase project
  - Install @supabase/supabase-js
  - Create tables: quiz_sessions, csrf_tokens
  - Setup environment variables

✅ Day 3-4: Migrate Session Storage
  - Replace Map with Supabase in initialize-session/route.ts
  - Update getSessionData, updateSessionToken functions
  - Add automatic cleanup for expired sessions
  - Test session persistence across restarts

✅ Day 5: Migrate CSRF Storage
  - Replace Map with Supabase in csrf-token/route.ts
  - Update validateCSRF function
  - Add TTL-based cleanup

✅ Day 6-7: Testing & Monitoring
  - Load testing with multiple instances
  - Verify session sharing works
  - Monitor Supabase performance
  - Setup error alerts
```

### Phase 2: Monitoring & Observability (Week 2)

```typescript
✅ Verify Sentry Integration
  - Configure DSN
  - Test error reporting
  - Setup source maps
  - Configure alerts

✅ Add Health Checks
  - Backend API health endpoint
  - Frontend health monitoring
  - Status dashboard

✅ Performance Monitoring
  - Track API response times
  - Monitor session operations
  - Database query optimization
```

### Phase 3: Enhancements (Week 3-4)

```typescript
✅ Rate Limiting
  - Setup Upstash Redis
  - Implement rate limiting middleware
  - Add CAPTCHA for excessive requests

✅ Request Correlation
  - Add request IDs
  - Link frontend → API routes → backend
  - Improve debugging

✅ Advanced Features
  - Offline support with service workers
  - Progressive enhancement
  - Performance budgets
```

---

## 🔍 Code Quality Observations

### Strengths

1. **TypeScript Usage**: ✅ Excellent type coverage
2. **Component Structure**: ✅ Well-organized, modular
3. **Error Handling**: ✅ Comprehensive try-catch blocks
4. **Security Practices**: ✅ No localStorage for tokens
5. **Code Style**: ✅ Consistent formatting

### Areas for Improvement

1. **Hardcoded Values**: Some magic numbers in code
2. **Comments**: Could use more JSDoc comments
3. **Testing**: Need more integration tests
4. **Error Messages**: Some generic error messages

---

## 📊 Performance Metrics

### Current Bundle Size (Estimated)

```
vendor.js:     ~500KB (React, Next.js, Radix UI)
common.js:     ~100KB (shared components)
page chunks:   ~50KB  (quiz-interface specific)

Total Initial Load: ~650KB (compressed)
Time to Interactive: <3s on 3G
First Contentful Paint: <1.5s
```

### Optimization Opportunities

1. ✅ Already implemented code splitting
2. ✅ Already using SWC minification
3. ⏳ Consider lazy loading for quiz completion screen
4. ⏳ Preload CSRF token on page load
5. ⏳ Implement service worker for offline support

---

## 🎯 Conclusion

The quiz-mensal-interface is a **well-architected, security-focused application** with modern best practices. However, it has **critical production readiness issues** that must be addressed:

### Must Fix Before Production
1. ❌ Replace in-memory session storage with Supabase/Redis
2. ❌ Replace in-memory CSRF tokens with persistent storage
3. ❌ Verify and test Sentry integration

### Should Fix Soon
4. ⚠️ Add backend health monitoring
5. ⚠️ Implement rate limiting
6. ⚠️ Setup proper request correlation

### Nice to Have
7. 💡 Enhanced offline support
8. 💡 Performance budgets and monitoring
9. 💡 A/B testing infrastructure

---

## 📚 Related Documentation

- [Backend Security Audit](./SECURITY_IMPROVEMENTS_2025-10-08.md)
- [Quiz Security Summary](./security/QUIZ_SECURITY_SUMMARY.md)
- [Frontend Performance Review](./frontend-performance-review.md)
- [Implementation Roadmap](./IMPLEMENTATION_ROADMAP.md)

---

**Analysis Completed**: 2025-10-08
**Next Review**: After implementing Phase 1 fixes
**Contact**: Development Team
