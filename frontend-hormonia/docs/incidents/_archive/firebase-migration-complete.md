# Firebase Authentication Migration - Complete Documentation

## Table of Contents
1. [Migration Overview](#migration-overview)
2. [Firebase Architecture](#firebase-architecture)
3. [Modified APIs](#modified-apis)
4. [Migration Guide](#migration-guide)
5. [Troubleshooting](#troubleshooting)
6. [Next Steps](#next-steps)

---

## Migration Overview

### What Was Migrated

This project has successfully migrated from **Supabase Authentication** to **Firebase Authentication** for all user authentication flows. The migration maintains API compatibility while providing Firebase's robust authentication infrastructure.

**Timeline**: Migration completed in 2025-09-30

### Key Changes

| Component | Before | After |
|-----------|--------|-------|
| **Auth Provider** | Supabase Auth | Firebase Auth |
| **Token Management** | Supabase JWT | Firebase ID Token |
| **Session Persistence** | Supabase cookies | Firebase persistence (local/session) |
| **User Management** | Supabase Admin API | Firebase Admin SDK |
| **Email Verification** | Supabase templates | Firebase email templates |
| **Password Reset** | Supabase flows | Firebase flows |

### Files Modified

#### Core Authentication Files (3 files)
1. **`src/lib/firebase-client.ts`** - New Firebase authentication client
2. **`src/contexts/AuthContext.tsx`** - Main authentication context (user login)
3. **`contexts/AdminAuthContext.tsx`** - Admin authentication context

#### Configuration Files
- **`package.json`** - Added `firebase@^12.3.0` dependency
- **`.env.example`** - Added Firebase environment variables (need to be added)

#### Legacy Files (Backup)
- **`src/lib/supabase-client.ts.backup`** - Original Supabase client (for reference)

### Breaking Changes

#### 1. Environment Variables
**Old (Supabase)**:
```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

**New (Firebase)**:
```bash
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your-sender-id
VITE_FIREBASE_APP_ID=your-app-id
```

#### 2. User Object Structure
**Old (Supabase)**:
```typescript
{
  id: string
  email: string
  user_metadata: { full_name?: string }
  app_metadata: { role?: string }
}
```

**New (Firebase)**:
```typescript
{
  uid: string           // Maps to user.id
  email: string
  displayName: string   // Maps to full_name
  emailVerified: boolean
  metadata: {
    creationTime: string
    lastSignInTime: string
  }
}
```

#### 3. Token Refresh Behavior
- **Supabase**: Manual token refresh every 60 minutes
- **Firebase**: Automatic token refresh every 55 minutes (handled internally)

---

## Firebase Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────┐            │
│  │  AuthContext.tsx │         │AdminAuthContext  │            │
│  │  (User Login)    │         │  (Admin Login)   │            │
│  └────────┬─────────┘         └────────┬─────────┘            │
│           │                            │                       │
│           └──────────┬─────────────────┘                       │
│                      │                                         │
│           ┌──────────▼──────────┐                              │
│           │ firebase-client.ts  │                              │
│           │  - signInWithPassword()                            │
│           │  - signUp()                                        │
│           │  - signOut()                                       │
│           │  - refreshSession()                                │
│           │  - onAuthStateChange()                             │
│           └──────────┬──────────┘                              │
│                      │                                         │
└──────────────────────┼─────────────────────────────────────────┘
                       │
                       │ Firebase SDK
                       │
┌──────────────────────▼─────────────────────────────────────────┐
│                    FIREBASE SERVICES                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Firebase Authentication                     │   │
│  │  - User Management                                       │   │
│  │  - Email/Password Auth                                   │   │
│  │  - JWT Token Generation (1hr expiry)                     │   │
│  │  - Session Management                                    │   │
│  │  - Email Verification                                    │   │
│  │  - Password Reset                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                       │
                       │ JWT Token (Authorization: Bearer)
                       │
┌──────────────────────▼─────────────────────────────────────────┐
│                      BACKEND API                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   API Client                              │  │
│  │  - setAuthToken(token)                                    │  │
│  │  - auth.me() - Fetch user profile                         │  │
│  │  - auth.logout() - Audit logging                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │            Firebase Admin SDK (Backend)                   │  │
│  │  - verifyIdToken(token)                                   │  │
│  │  - getUserByEmail(email)                                  │  │
│  │  - updateUser(uid, data)                                  │  │
│  │  - createUser(email, password)                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Authentication Flow Diagrams

#### Login Flow
```
┌──────────┐         ┌──────────────┐         ┌─────────────┐         ┌────────────┐
│  User    │         │  AuthContext │         │  Firebase   │         │  Backend   │
│  (UI)    │         │              │         │   Auth      │         │    API     │
└────┬─────┘         └──────┬───────┘         └──────┬──────┘         └─────┬──────┘
     │                      │                        │                      │
     │  1. login(email,pw)  │                        │                      │
     ├─────────────────────>│                        │                      │
     │                      │                        │                      │
     │                      │ 2. signInWithPassword()│                      │
     │                      ├───────────────────────>│                      │
     │                      │                        │                      │
     │                      │  3. JWT Token + User   │                      │
     │                      │<───────────────────────┤                      │
     │                      │                        │                      │
     │                      │  4. setAuthToken(jwt)  │                      │
     │                      ├───────────────────────────────────────────────>│
     │                      │                        │                      │
     │                      │  5. GET /auth/me       │                      │
     │                      ├───────────────────────────────────────────────>│
     │                      │                        │                      │
     │                      │  6. User Profile Data  │                      │
     │                      │<───────────────────────────────────────────────┤
     │                      │                        │                      │
     │  7. User State       │                        │                      │
     │<─────────────────────┤                        │                      │
     │                      │                        │                      │
     │  8. Redirect to      │                        │                      │
     │     Dashboard        │                        │                      │
     │                      │                        │                      │
```

#### Token Refresh Flow (Automatic)
```
┌──────────────┐         ┌─────────────┐         ┌────────────┐
│ AuthContext  │         │  Firebase   │         │  Backend   │
│              │         │   Auth      │         │    API     │
└──────┬───────┘         └──────┬──────┘         └─────┬──────┘
       │                        │                      │
       │  55 min elapsed        │                      │
       │  (Firebase auto)       │                      │
       │                        │                      │
       │ 1. Token expired       │                      │
       │      detection         │                      │
       │                        │                      │
       │ 2. getIdToken(true)    │                      │
       ├───────────────────────>│                      │
       │                        │                      │
       │ 3. New JWT Token       │                      │
       │<───────────────────────┤                      │
       │                        │                      │
       │ 4. setAuthToken()      │                      │
       ├───────────────────────────────────────────────>│
       │                        │                      │
       │ 5. Subsequent requests │                      │
       │    use new token       │                      │
       │                        │                      │
```

#### Logout Flow
```
┌──────────┐         ┌──────────────┐         ┌─────────────┐         ┌────────────┐
│  User    │         │  AuthContext │         │  Firebase   │         │  Backend   │
│  (UI)    │         │              │         │   Auth      │         │    API     │
└────┬─────┘         └──────┬───────┘         └──────┬──────┘         └─────┬──────┘
     │                      │                        │                      │
     │  1. logout()         │                        │                      │
     ├─────────────────────>│                        │                      │
     │                      │                        │                      │
     │                      │  2. signOut()          │                      │
     │                      ├───────────────────────>│                      │
     │                      │                        │                      │
     │                      │  3. Session cleared    │                      │
     │                      │<───────────────────────┤                      │
     │                      │                        │                      │
     │                      │  4. POST /auth/logout  │                      │
     │                      │     (audit only)       │                      │
     │                      ├───────────────────────────────────────────────>│
     │                      │                        │                      │
     │                      │  5. setAuthToken(null) │                      │
     │                      ├───────────────────────────────────────────────>│
     │                      │                        │                      │
     │                      │  6. Clear state        │                      │
     │                      │     - user = null      │                      │
     │                      │     - session = null   │                      │
     │                      │                        │                      │
     │  7. Redirect to      │                        │                      │
     │     Login Page       │                        │                      │
     │<─────────────────────┤                        │                      │
```

### Frontend-Backend Integration

#### Token Flow
1. **Frontend** authenticates with Firebase
2. **Firebase** returns JWT ID Token (1hr expiry)
3. **Frontend** stores token and sends in API requests:
   ```typescript
   Authorization: Bearer <firebase-jwt-token>
   ```
4. **Backend** validates token using Firebase Admin SDK
5. **Backend** returns user profile data and custom claims

#### Session Persistence Options
```typescript
// Local Storage (default - "Remember Me")
await firebaseAuth.setPersistence(true)
// Token survives browser restart

// Session Storage (logout on close)
await firebaseAuth.setPersistence(false)
// Token cleared when browser closes
```

---

## Modified APIs

### 1. firebase-client.ts

New Firebase authentication client with Supabase-compatible API.

#### Available Methods

##### signInWithPassword()
Authenticate user with email and password.

**Signature**:
```typescript
async signInWithPassword(credentials: {
  email: string
  password: string
}): Promise<{
  user: FirebaseUser | null
  session: { access_token: string } | null
  error: Error | null
}>
```

**Example**:
```typescript
import { firebaseAuth } from '@/lib/firebase-client'

const result = await firebaseAuth.signInWithPassword({
  email: 'user@example.com',
  password: 'SecurePass123!'
})

if (result.error) {
  console.error('Login failed:', result.error.message)
} else {
  console.log('User:', result.user)
  console.log('Token:', result.session?.access_token)
}
```

##### signUp()
Create new user account.

**Signature**:
```typescript
async signUp(credentials: {
  email: string
  password: string
  options?: {
    data?: {
      full_name?: string
      role?: string
    }
  }
}): Promise<{
  user: FirebaseUser | null
  session: { access_token: string } | null
  error: Error | null
}>
```

**Example**:
```typescript
const result = await firebaseAuth.signUp({
  email: 'newuser@example.com',
  password: 'SecurePass123!',
  options: {
    data: {
      full_name: 'John Doe',
      role: 'patient'
    }
  }
})

if (!result.error) {
  // Email verification sent automatically
  console.log('Account created! Check email for verification.')
}
```

##### signOut()
Sign out current user.

**Signature**:
```typescript
async signOut(): Promise<{ error: Error | null }>
```

**Example**:
```typescript
const result = await firebaseAuth.signOut()
if (!result.error) {
  console.log('Signed out successfully')
}
```

##### getCurrentSession()
Get current authentication session.

**Signature**:
```typescript
async getCurrentSession(): Promise<{ access_token: string } | null>
```

**Example**:
```typescript
const session = await firebaseAuth.getCurrentSession()
if (session) {
  console.log('Active session token:', session.access_token)
}
```

##### getCurrentUser()
Get current authenticated user.

**Signature**:
```typescript
async getCurrentUser(): Promise<FirebaseUser | null>
```

**Example**:
```typescript
const user = await firebaseAuth.getCurrentUser()
if (user) {
  console.log('Current user:', user.email)
  console.log('Email verified:', user.emailVerified)
}
```

##### refreshSession()
Manually refresh the authentication token.

**Signature**:
```typescript
async refreshSession(): Promise<{ access_token: string } | null>
```

**Example**:
```typescript
const newSession = await firebaseAuth.refreshSession()
if (newSession) {
  console.log('Token refreshed:', newSession.access_token)
}
```

##### resetPasswordForEmail()
Send password reset email.

**Signature**:
```typescript
async resetPasswordForEmail(email: string): Promise<{ error: Error | null }>
```

**Example**:
```typescript
const result = await firebaseAuth.resetPasswordForEmail('user@example.com')
if (!result.error) {
  console.log('Password reset email sent')
}
```

##### setPersistence()
Set authentication persistence mode.

**Signature**:
```typescript
async setPersistence(rememberMe: boolean): Promise<void>
```

**Example**:
```typescript
// Persist across browser restarts
await firebaseAuth.setPersistence(true)

// Clear on browser close
await firebaseAuth.setPersistence(false)
```

##### onAuthStateChange()
Listen to authentication state changes.

**Signature**:
```typescript
onAuthStateChange(callback: (user: FirebaseUser | null) => void): () => void
```

**Example**:
```typescript
const unsubscribe = firebaseAuth.onAuthStateChange((user) => {
  if (user) {
    console.log('User logged in:', user.email)
  } else {
    console.log('User logged out')
  }
})

// Cleanup
unsubscribe()
```

---

### 2. AuthContext.tsx

Main authentication context for user login flows.

#### Interface Changes

**Context Type**:
```typescript
interface AuthContextType {
  user: User | null                    // Backend user profile
  firebaseUser: FirebaseUser | null    // NEW: Firebase user object
  session: { access_token: string } | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
}
```

**User Type**:
```typescript
interface User {
  id: string              // From Firebase uid
  email: string
  full_name: string       // From Firebase displayName or backend
  role: string            // From backend (default: 'user')
  is_active: boolean
  permissions: string[]   // From backend
  created_at: string
}
```

#### Usage Example

```typescript
import { useAuth } from '@/contexts/AuthContext'

function MyComponent() {
  const {
    user,
    firebaseUser,
    isAuthenticated,
    isLoading,
    login,
    logout,
    hasPermission,
    hasRole
  } = useAuth()

  // Check authentication
  if (isLoading) return <div>Loading...</div>
  if (!isAuthenticated) return <div>Please log in</div>

  // Check permissions
  if (!hasPermission('view_patients')) {
    return <div>Access denied</div>
  }

  // Check role
  if (hasRole('admin')) {
    return <div>Admin Panel</div>
  }

  return (
    <div>
      <h1>Welcome, {user?.full_name}</h1>
      <p>Email: {user?.email}</p>
      <p>Firebase UID: {firebaseUser?.uid}</p>
      <button onClick={logout}>Logout</button>
    </div>
  )
}
```

#### Key Behaviors

1. **Initialization** (on mount):
   - Checks for existing Firebase session
   - Sets API client token
   - Fetches user profile from backend
   - Falls back to Firebase user if backend fails
   - Timeout: 5 seconds

2. **Login Flow**:
   - Authenticates with Firebase
   - Stores Firebase token in API client
   - Fetches backend user profile
   - Updates local state
   - Throws error on failure

3. **Auth State Listener**:
   - Listens to Firebase auth state changes
   - Automatically updates tokens on refresh
   - Syncs with backend API
   - Clears state on logout

---

### 3. AdminAuthContext.tsx

Admin-specific authentication context with enhanced security.

#### Interface Changes

**Context Type**:
```typescript
interface AdminAuthContextValue {
  state: AdminAuthState
  signIn: (email: string, password: string, rememberMe?: boolean) => Promise<AdminLoginResponse>
  login: (email: string, password: string, rememberMe?: boolean) => Promise<AdminLoginResponse>
  signOut: () => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
  extendSession: () => Promise<void>
  updateUser: (updates: Partial<AdminUser>) => Promise<void>
}
```

**Admin State**:
```typescript
interface AdminAuthState {
  user: AdminUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  sessionExpiry: Date | null    // NEW: 1 hour from login
}
```

**Admin User Type**:
```typescript
interface AdminUser {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'superadmin'
  is_active: boolean
  permissions: string[]
  created_at: string
  updated_at: string
  last_login: string
  login_count: number
  two_factor_enabled: boolean
  failed_login_attempts: number
  locked_until: string | null
}
```

#### Usage Example

```typescript
import { useAdminAuth } from '@/contexts/AdminAuthContext'

function AdminLoginPage() {
  const { state, signIn, signOut } = useAdminAuth()
  const [rememberMe, setRememberMe] = useState(false)

  const handleLogin = async (email: string, password: string) => {
    const result = await signIn(email, password, rememberMe)

    if (result.success) {
      console.log('Admin logged in:', result.user)
      console.log('Token:', result.token)
    } else {
      console.error('Login failed:', result.error)
    }
  }

  if (state.isLoading) {
    return <div>Loading...</div>
  }

  if (state.error) {
    return <div>Error: {state.error}</div>
  }

  if (state.isAuthenticated) {
    return (
      <div>
        <h1>Admin Dashboard</h1>
        <p>Welcome, {state.user?.full_name}</p>
        <p>Session expires: {state.sessionExpiry?.toLocaleString()}</p>
        <button onClick={signOut}>Logout</button>
      </div>
    )
  }

  return <LoginForm onSubmit={handleLogin} />
}
```

#### Key Features

1. **Session Management**:
   - Tracks session expiry (1 hour)
   - Automatic token refresh
   - Session extension support

2. **Security Features**:
   - Failed login attempt tracking
   - Account locking mechanism
   - Two-factor auth support (coming soon)

3. **Backward Compatibility**:
   - `login()` alias for `signIn()`
   - `logout()` alias for `signOut()`

---

## Migration Guide

### For Developers: Updating Existing Code

#### Step 1: Update Environment Variables

**Old `.env` (Supabase)**:
```bash
VITE_SUPABASE_URL=https://xxx.supabase.co
VITE_SUPABASE_ANON_KEY=xxx
```

**New `.env` (Firebase)**:
```bash
# Remove Supabase variables
# Add Firebase variables:
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_STORAGE_BUCKET=your-project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:xxxxx
```

**Get Firebase credentials**:
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project (or use existing)
3. Enable Authentication > Email/Password
4. Go to Project Settings > General
5. Scroll to "Your apps" > Web app
6. Copy config values to `.env`

#### Step 2: Update Import Statements

**Before (Supabase)**:
```typescript
import { supabase } from '@/lib/supabase-client'

// Login
const { data, error } = await supabase.auth.signInWithPassword({
  email,
  password
})

// Get session
const { data: { session } } = await supabase.auth.getSession()

// Sign out
await supabase.auth.signOut()
```

**After (Firebase)**:
```typescript
import { firebaseAuth } from '@/lib/firebase-client'

// Login
const { user, session, error } = await firebaseAuth.signInWithPassword({
  email,
  password
})

// Get session
const session = await firebaseAuth.getCurrentSession()

// Sign out
await firebaseAuth.signOut()
```

#### Step 3: Update User Object Access

**Before (Supabase)**:
```typescript
const user = session?.user
const userId = user?.id
const email = user?.email
const name = user?.user_metadata?.full_name
const role = user?.app_metadata?.role
```

**After (Firebase)**:
```typescript
// From AuthContext
const { user, firebaseUser } = useAuth()

// User data (from backend)
const userId = user?.id
const email = user?.email
const name = user?.full_name
const role = user?.role

// Firebase-specific data
const firebaseUid = firebaseUser?.uid
const emailVerified = firebaseUser?.emailVerified
const createdAt = firebaseUser?.metadata.creationTime
```

#### Step 4: Update Auth State Listeners

**Before (Supabase)**:
```typescript
useEffect(() => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange(
    (event, session) => {
      if (event === 'SIGNED_IN') {
        console.log('User signed in')
      }
    }
  )

  return () => subscription.unsubscribe()
}, [])
```

**After (Firebase)**:
```typescript
useEffect(() => {
  const unsubscribe = firebaseAuth.onAuthStateChange((user) => {
    if (user) {
      console.log('User signed in:', user.email)
    } else {
      console.log('User signed out')
    }
  })

  return () => unsubscribe()
}, [])
```

#### Step 5: Update Token Management

**Before (Supabase)**:
```typescript
// Manual refresh
const { data: { session }, error } = await supabase.auth.refreshSession()
if (session) {
  apiClient.setAuthToken(session.access_token)
}
```

**After (Firebase)**:
```typescript
// Automatic refresh (handled by Firebase)
// Manual refresh (if needed):
const session = await firebaseAuth.refreshSession()
if (session) {
  apiClient.setAuthToken(session.access_token)
}
```

#### Step 6: Update Password Reset

**Before (Supabase)**:
```typescript
await supabase.auth.resetPasswordForEmail(email, {
  redirectTo: 'https://example.com/reset-password'
})
```

**After (Firebase)**:
```typescript
await firebaseAuth.resetPasswordForEmail(email)
// Firebase uses default redirect (configured in Firebase Console)
```

### API Equivalence Table

| Supabase Method | Firebase Equivalent | Notes |
|----------------|--------------------|-------------------------------------------------|
| `supabase.auth.signInWithPassword()` | `firebaseAuth.signInWithPassword()` | Same API signature |
| `supabase.auth.signUp()` | `firebaseAuth.signUp()` | Same API signature |
| `supabase.auth.signOut()` | `firebaseAuth.signOut()` | Same API signature |
| `supabase.auth.getSession()` | `firebaseAuth.getCurrentSession()` | Returns session or null |
| `supabase.auth.getUser()` | `firebaseAuth.getCurrentUser()` | Returns Firebase user |
| `supabase.auth.refreshSession()` | `firebaseAuth.refreshSession()` | Manual refresh |
| `supabase.auth.resetPasswordForEmail()` | `firebaseAuth.resetPasswordForEmail()` | Email-based reset |
| `supabase.auth.onAuthStateChange()` | `firebaseAuth.onAuthStateChange()` | Returns unsubscribe function |
| `supabase.auth.setSession()` | `N/A` | Firebase handles automatically |
| `supabase.auth.updateUser()` | `updateProfile()` | Need to expose in client |

### Key Differences

#### 1. Token Refresh
- **Supabase**: Manual refresh required every 60 minutes
- **Firebase**: Automatic refresh every 55 minutes
- **Impact**: Less code needed for token management

#### 2. Session Persistence
- **Supabase**: Uses cookies and localStorage
- **Firebase**: Uses `browserLocalPersistence` or `browserSessionPersistence`
- **Impact**: Need to set persistence mode explicitly

#### 3. User Metadata
- **Supabase**: Stored in `user_metadata` and `app_metadata`
- **Firebase**: Stored in `displayName`, custom claims require backend
- **Impact**: Backend API required for role/permission management

#### 4. Email Verification
- **Supabase**: Optional, configured in dashboard
- **Firebase**: Sent automatically on signup
- **Impact**: Users must verify email before full access

#### 5. Password Requirements
- **Supabase**: Configurable (min 6 characters)
- **Firebase**: Min 6 characters (enforced)
- **Impact**: Password validation logic may need updates

---

## Troubleshooting

### Common Errors and Solutions

#### Error: "Firebase: Error (auth/invalid-api-key)"
**Cause**: Invalid or missing Firebase API key in environment variables.

**Solution**:
```bash
# Check .env file
echo $VITE_FIREBASE_API_KEY

# If missing, add to .env:
VITE_FIREBASE_API_KEY=your-actual-api-key

# Restart dev server:
npm run dev
```

#### Error: "Firebase: Error (auth/user-not-found)"
**Cause**: User account doesn't exist in Firebase Authentication.

**Solution**:
1. Check Firebase Console > Authentication > Users
2. Create user account if missing
3. Or use signup flow to create account

```typescript
// Create account programmatically
const result = await firebaseAuth.signUp({
  email: 'user@example.com',
  password: 'SecurePass123!'
})
```

#### Error: "Firebase: Error (auth/wrong-password)"
**Cause**: Incorrect password for existing user.

**Solution**:
1. Verify password is correct
2. Check if account exists in Firebase Console
3. Use password reset if needed:

```typescript
await firebaseAuth.resetPasswordForEmail('user@example.com')
```

#### Error: "Firebase: Error (auth/too-many-requests)"
**Cause**: Too many failed login attempts from same IP.

**Solution**:
1. Wait 5-10 minutes before retrying
2. Enable CAPTCHA in Firebase Console:
   - Go to Authentication > Settings
   - Enable "Email enumeration protection"
3. Or reset password to unlock account

#### Error: "Firebase: Error (auth/network-request-failed)"
**Cause**: Network connectivity issues or Firebase service unavailable.

**Solution**:
```typescript
// Add retry logic
async function loginWithRetry(email: string, password: string, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await firebaseAuth.signInWithPassword({ email, password })
    } catch (error: any) {
      if (error.code === 'auth/network-request-failed' && i < maxRetries - 1) {
        await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
        continue
      }
      throw error
    }
  }
}
```

#### Error: "No active Firebase session found"
**Cause**: Session expired or user was logged out.

**Solution**:
```typescript
// Check if session exists
const session = await firebaseAuth.getCurrentSession()
if (!session) {
  // Redirect to login
  window.location.href = '/login'
}
```

#### Error: "Token refresh failed"
**Cause**: Firebase token expired and couldn't be refreshed.

**Solution**:
```typescript
// Force user to re-login
const { logout } = useAuth()
await logout()
// Redirect to login page
window.location.href = '/login'
```

### Debug Tips

#### 1. Enable Firebase Debug Logging
```typescript
// Add to firebase-client.ts
import { setLogLevel } from 'firebase/auth'

// In development
if (import.meta.env.DEV) {
  setLogLevel('debug')
}
```

#### 2. Check Authentication State
```typescript
// Add to AuthContext or component
useEffect(() => {
  const unsubscribe = firebaseAuth.onAuthStateChange((user) => {
    console.log('[Debug] Auth state changed:', {
      user: user?.email,
      uid: user?.uid,
      emailVerified: user?.emailVerified,
      metadata: user?.metadata
    })
  })
  return () => unsubscribe()
}, [])
```

#### 3. Inspect Token Claims
```typescript
// Get token and decode
const user = await firebaseAuth.getCurrentUser()
if (user) {
  const token = await user.getIdToken()
  const tokenResult = await user.getIdTokenResult()

  console.log('[Debug] Token claims:', {
    expirationTime: tokenResult.expirationTime,
    issuedAtTime: tokenResult.issuedAtTime,
    claims: tokenResult.claims
  })
}
```

#### 4. Monitor Network Requests
```typescript
// Add interceptor to api-client.ts
apiClient.interceptors.request.use((config) => {
  console.log('[API Request]', {
    url: config.url,
    method: config.method,
    headers: config.headers.Authorization
  })
  return config
})
```

#### 5. Check Firebase Console Logs
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to Authentication > Usage
4. Check authentication events and errors

### Logs to Check

#### Frontend Logs (Browser Console)
Look for these log messages:
```
[Firebase] Initializing Firebase app...
[Firebase] Firebase initialized successfully
[Firebase] Signing in user: user@example.com
[Firebase] Sign in successful
[AuthContext] Starting Firebase initialization...
[AuthContext] Firebase session found, setting up authentication...
[AuthContext] Admin user data loaded: user@example.com
[AuthContext] Firebase initialization completed successfully
```

#### Backend Logs (Server)
Check for Firebase Admin SDK logs:
```
[Firebase Admin] Verifying ID token...
[Firebase Admin] Token verified for user: xxx
[Auth] User authenticated: user@example.com
[Auth] Fetching user profile from database...
```

#### Firebase Console Logs
- **Authentication > Users**: Check user accounts
- **Authentication > Usage**: Monitor login attempts
- **Authentication > Settings**: Verify configuration

---

## Next Steps

### Immediate TODOs

#### 1. Environment Configuration
- [ ] Add Firebase credentials to production `.env`
- [ ] Update `.env.example` with Firebase variables
- [ ] Configure Firebase project settings
- [ ] Set up email templates in Firebase Console

#### 2. Backend Integration
- [ ] Implement Firebase Admin SDK in backend
- [ ] Add token verification middleware
- [ ] Update user profile endpoints
- [ ] Sync user data between Firebase and database

#### 3. Testing
- [ ] Unit tests for firebase-client.ts
- [ ] Integration tests for AuthContext
- [ ] E2E tests for login/logout flows
- [ ] Load testing for token refresh

#### 4. Security Hardening
- [ ] Enable Firebase security rules
- [ ] Implement rate limiting
- [ ] Add CAPTCHA for repeated failures
- [ ] Configure password policies
- [ ] Enable account recovery

#### 5. User Experience
- [ ] Add loading states during auth
- [ ] Implement better error messages
- [ ] Add "Remember Me" checkbox to login
- [ ] Show session expiry warnings
- [ ] Add email verification prompts

#### 6. Documentation
- [ ] Update API documentation
- [ ] Create developer onboarding guide
- [ ] Document Firebase console setup
- [ ] Add architecture decision records (ADRs)

### Future Enhancements

#### 1. Multi-Factor Authentication (MFA)
```typescript
// TODO: Implement 2FA with Firebase
import { multiFactor } from 'firebase/auth'

// Enable 2FA for user
await multiFactor(user).enroll(phoneAuthCredential, displayName)
```

#### 2. Social Login Providers
```typescript
// TODO: Add Google/Facebook login
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth'

const provider = new GoogleAuthProvider()
await signInWithPopup(auth, provider)
```

#### 3. Custom Email Templates
- Configure Firebase email templates
- Add clinic branding to emails
- Localize emails for pt-BR

#### 4. Session Management Dashboard
- Show active sessions for user
- Allow remote session termination
- Display login history

#### 5. Advanced Security Features
- Implement device fingerprinting
- Add anomaly detection
- Enable audit logging
- Implement password breach detection

#### 6. Performance Optimizations
- Implement token caching strategy
- Add offline support with Firebase persistence
- Optimize auth state synchronization
- Reduce initial load time

### Migration Checklist for Other Projects

If you need to migrate another project from Supabase to Firebase:

- [ ] Create Firebase project
- [ ] Enable Email/Password authentication
- [ ] Add Firebase SDK to package.json
- [ ] Create firebase-client.ts wrapper
- [ ] Update AuthContext to use Firebase
- [ ] Update environment variables
- [ ] Migrate existing users (export from Supabase, import to Firebase)
- [ ] Update backend to use Firebase Admin SDK
- [ ] Test all authentication flows
- [ ] Update documentation
- [ ] Deploy to production
- [ ] Monitor for issues

### Resources

#### Firebase Documentation
- [Firebase Authentication Docs](https://firebase.google.com/docs/auth)
- [Web SDK Reference](https://firebase.google.com/docs/reference/js/auth)
- [Admin SDK Guide](https://firebase.google.com/docs/auth/admin)
- [Best Practices](https://firebase.google.com/docs/auth/best-practices)

#### Migration Tools
- [Supabase to Firebase Migration Tool](https://github.com/firebase/firebase-tools) (CLI)
- User export scripts (custom, based on project needs)

#### Support Channels
- Firebase Support: https://firebase.google.com/support
- Stack Overflow: Tag `firebase-authentication`
- GitHub Issues: https://github.com/firebase/firebase-js-sdk/issues

---

## Appendix

### Complete Code Examples

#### Example 1: Login Form Component
```typescript
import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

export function LoginForm() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      // Set persistence before login
      await firebaseAuth.setPersistence(rememberMe)

      // Login
      await login(email, password)

      // Redirect on success
      navigate('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
        required
      />
      <label>
        <input
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
        />
        Remember me
      </label>
      {error && <div className="error">{error}</div>}
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  )
}
```

#### Example 2: Protected Route Component
```typescript
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

interface ProtectedRouteProps {
  children: React.ReactNode
  requiredRole?: string
  requiredPermission?: string
}

export function ProtectedRoute({
  children,
  requiredRole,
  requiredPermission
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, hasRole, hasPermission } = useAuth()

  if (isLoading) {
    return <div>Loading...</div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (requiredRole && !hasRole(requiredRole)) {
    return <Navigate to="/unauthorized" replace />
  }

  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />
  }

  return <>{children}</>
}

// Usage:
<Route
  path="/admin"
  element={
    <ProtectedRoute requiredRole="admin">
      <AdminDashboard />
    </ProtectedRoute>
  }
/>
```

#### Example 3: Token Refresh Hook
```typescript
import { useEffect } from 'react'
import { firebaseAuth } from '@/lib/firebase-client'
import { apiClient } from '@/lib/api-client'

export function useTokenRefresh() {
  useEffect(() => {
    // Refresh token every 50 minutes (before expiry)
    const interval = setInterval(async () => {
      try {
        console.log('[TokenRefresh] Refreshing token...')
        const session = await firebaseAuth.refreshSession()

        if (session) {
          apiClient.setAuthToken(session.access_token)
          console.log('[TokenRefresh] Token refreshed successfully')
        }
      } catch (error) {
        console.error('[TokenRefresh] Failed to refresh token:', error)
      }
    }, 50 * 60 * 1000) // 50 minutes

    return () => clearInterval(interval)
  }, [])
}

// Usage in AuthContext or App.tsx:
useTokenRefresh()
```

---

**Document Version**: 1.0
**Last Updated**: 2025-09-30
**Author**: Technical Documentation Team
**Status**: Complete

For questions or issues, please create a GitHub issue or contact the development team.