# Authentication & Authorization Guide - Sistema Hormonia

**Last Updated:** 2025-09-29
**Version:** 2.0.0

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Authentication Flow](#authentication-flow)
3. [Authorization & Role-Based Access Control](#authorization--role-based-access-control)
4. [Row-Level Security (RLS)](#row-level-security-rls)
5. [Implementation Guide](#implementation-guide)
6. [Security Best Practices](#security-best-practices)
7. [Troubleshooting](#troubleshooting)
8. [Testing Authentication](#testing-authentication)

---

## Overview

Sistema Hormonia implements a **multi-layered security architecture** combining:

- **JWT-based Authentication** - Token-based stateless authentication
- **Role-Based Access Control (RBAC)** - Permission management by user roles
- **Row-Level Security (RLS)** - Database-level access control via Supabase
- **OAuth2 Standards** - Industry-standard authentication protocols

### Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Client Request                      │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│            JWT Token Validation (FastAPI)                │
│  • Verify signature                                      │
│  • Check expiration                                      │
│  • Extract user claims                                   │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│         Role-Based Access Control (Application)          │
│  • Check user role (admin/doctor/patient)                │
│  • Verify endpoint permissions                           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│          Row-Level Security (Database/Supabase)          │
│  • Apply RLS policies                                    │
│  • Filter data by ownership                              │
│  • Enforce data isolation                                │
└─────────────────────────────────────────────────────────┘
```

### Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Token Format** | JWT (JSON Web Tokens) | Stateless authentication |
| **Token Algorithm** | HS256 (HMAC-SHA256) | Token signing |
| **Database Auth** | Supabase Auth + RLS | Data access control |
| **Password Hashing** | bcrypt | Secure password storage |
| **Token Storage** | HTTP-only cookies / localStorage | Client-side token management |
| **Session Management** | Redis (optional) | Token blacklisting and caching |

---

## Authentication Flow

### 1. User Login

**Endpoint:** `POST /api/v1/auth/login`

**Request:**
```http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json

{
  "email": "doctor@hormonia.app",
  "password": "SecurePassword123!"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "doctor@hormonia.app",
    "name": "Dr. Maria Silva",
    "role": "doctor",
    "avatar_url": null
  }
}
```

**Process Flow:**

1. **Client submits credentials** (email + password)
2. **Backend validates credentials** against database
3. **Password verification** using bcrypt
4. **Generate tokens**:
   - `access_token`: Short-lived (30 minutes) for API access
   - `refresh_token`: Long-lived (7 days) for token renewal
5. **Return tokens and user info**

**Python Example:**
```python
import requests

def login(email: str, password: str):
    """Login and receive authentication tokens."""
    response = requests.post(
        "https://api.hormonia.app/api/v1/auth/login",
        json={"email": email, "password": password}
    )

    if response.status_code == 200:
        data = response.json()
        return {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "user": data["user"]
        }
    else:
        raise Exception(f"Login failed: {response.json()['detail']}")

# Usage
tokens = login("doctor@hormonia.app", "SecurePassword123!")
print(f"Access Token: {tokens['access_token'][:50]}...")
```

**TypeScript/JavaScript Example:**
```typescript
async function login(email: string, password: string) {
  const response = await fetch('https://api.hormonia.app/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  if (!response.ok) {
    throw new Error(`Login failed: ${response.statusText}`);
  }

  const data = await response.json();

  // Store tokens securely
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
  localStorage.setItem('user', JSON.stringify(data.user));

  return data;
}

// Usage
const { user } = await login('doctor@hormonia.app', 'SecurePassword123!');
console.log(`Logged in as: ${user.name}`);
```

---

### 2. Authenticated Requests

**All protected endpoints require the access token in the Authorization header:**

```http
GET /api/v1/patients HTTP/1.1
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Python Example:**
```python
import requests

def get_patients(access_token: str):
    """Fetch patients with authentication."""
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(
        "https://api.hormonia.app/api/v1/patients",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    elif response.status_code == 401:
        raise Exception("Token expired or invalid")
    else:
        raise Exception(f"Request failed: {response.json()}")

# Usage
patients = get_patients(tokens['access_token'])
print(f"Found {len(patients['items'])} patients")
```

**JavaScript Example:**
```javascript
async function getPatients() {
  const token = localStorage.getItem('access_token');

  const response = await fetch('https://api.hormonia.app/api/v1/patients', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (response.status === 401) {
    // Token expired, refresh it
    await refreshToken();
    return getPatients(); // Retry
  }

  return await response.json();
}
```

---

### 3. Token Refresh

**Endpoint:** `POST /api/v1/auth/refresh`

When the access token expires (after 30 minutes), use the refresh token to get a new access token **without requiring the user to log in again**.

**Request:**
```http
POST /api/v1/auth/refresh HTTP/1.1
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Automatic Token Refresh Implementation:**

```typescript
// TypeScript/React example with axios
import axios from 'axios';

// Create axios instance
const api = axios.create({
  baseURL: 'https://api.hormonia.app/api/v1'
});

// Request interceptor: Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: Handle 401 and refresh token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If 401 and not already retried
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Get new access token
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post(
          'https://api.hormonia.app/api/v1/auth/refresh',
          { refresh_token: refreshToken }
        );

        // Save new access token
        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, logout user
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

---

### 4. Logout

**Endpoint:** `POST /api/v1/auth/logout`

**Request:**
```http
POST /api/v1/auth/logout HTTP/1.1
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

**What happens during logout:**
1. Token is added to blacklist (if Redis is enabled)
2. Client clears stored tokens
3. User must re-authenticate to access protected resources

**Client-side Logout:**
```typescript
async function logout() {
  const token = localStorage.getItem('access_token');

  try {
    // Call logout endpoint (blacklist token)
    await fetch('https://api.hormonia.app/api/v1/auth/logout', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
  } catch (error) {
    console.error('Logout API call failed:', error);
  } finally {
    // Always clear local storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');

    // Redirect to login
    window.location.href = '/login';
  }
}
```

---

## Authorization & Role-Based Access Control

Sistema Hormonia implements **Role-Based Access Control (RBAC)** with four user roles:

### Role Definitions

| Role | Description | Access Level |
|------|-------------|-------------|
| **admin** | System administrator | Full access to all resources and settings |
| **doctor** | Healthcare professional | Access to assigned patients and their data |
| **patient** | End user | Access only to own data |
| **service_provider** | External service integrator | Limited API access for integrations |

### Permission Matrix

#### Patient Management

| Action | Admin | Doctor | Patient | Service Provider |
|--------|-------|--------|---------|------------------|
| View all patients | ✅ | ❌ | ❌ | ❌ |
| View assigned patients | ✅ | ✅ | ❌ | ❌ |
| View own data | ✅ | ✅ | ✅ | ❌ |
| Create patient | ✅ | ✅ | ❌ | ❌ |
| Update any patient | ✅ | ❌ | ❌ | ❌ |
| Update assigned patient | ✅ | ✅ | ❌ | ❌ |
| Update own data | ✅ | ✅ | ✅ | ❌ |
| Delete patient | ✅ | ❌ | ❌ | ❌ |

#### Medical Records

| Action | Admin | Doctor | Patient | Service Provider |
|--------|-------|--------|---------|------------------|
| View all records | ✅ | ❌ | ❌ | ❌ |
| View assigned patient records | ✅ | ✅ | ❌ | ❌ |
| View own records | ✅ | ✅ | ✅ | ❌ |
| Create record | ✅ | ✅ | ❌ | ❌ |
| Update record | ✅ | ✅ | ❌ | ❌ |
| Delete record | ✅ | ✅ | ❌ | ❌ |

#### User Management

| Action | Admin | Doctor | Patient | Service Provider |
|--------|-------|--------|---------|------------------|
| Create users | ✅ | ❌ | ❌ | ❌ |
| View all users | ✅ | ❌ | ❌ | ❌ |
| Update user roles | ✅ | ❌ | ❌ | ❌ |
| Delete users | ✅ | ❌ | ❌ | ❌ |
| Update own profile | ✅ | ✅ | ✅ | ✅ |

#### System Settings

| Action | Admin | Doctor | Patient | Service Provider |
|--------|-------|--------|---------|------------------|
| Configure WhatsApp | ✅ | ❌ | ❌ | ❌ |
| Configure AI settings | ✅ | ❌ | ❌ | ❌ |
| View system metrics | ✅ | ❌ | ❌ | ❌ |
| Manage conversation flows | ✅ | ✅ | ❌ | ❌ |

---

### Implementing Role-Based Access Control

#### Backend Implementation (FastAPI)

**1. Define Dependencies for Role Checking:**

```python
# Backend/app/api/dependencies/auth.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from typing import List

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user from database
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def require_role(allowed_roles: List[str]):
    """Dependency factory to check if user has required role."""
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


# Convenience dependencies for specific roles
require_admin = require_role(["admin"])
require_doctor_or_admin = require_role(["doctor", "admin"])
require_patient_or_higher = require_role(["patient", "doctor", "admin"])
```

**2. Apply Role-Based Access Control to Endpoints:**

```python
# Backend/app/api/v1/endpoints/patients.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies.auth import (
    get_current_active_user,
    require_admin,
    require_doctor_or_admin
)
from app.db.session import get_db
from app.models.user import User
from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientResponse

router = APIRouter()


@router.get(
    "/patients",
    response_model=List[PatientResponse],
    dependencies=[Depends(require_doctor_or_admin)]
)
async def get_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get patients list.
    - Admins: See all patients
    - Doctors: See only assigned patients
    """
    if current_user.role == "admin":
        # Admin sees all patients
        patients = db.query(Patient).all()
    elif current_user.role == "doctor":
        # Doctor sees only assigned patients
        patients = db.query(Patient).filter(
            Patient.doctor_id == current_user.id
        ).all()
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    return patients


@router.post(
    "/patients",
    response_model=PatientResponse,
    status_code=201,
    dependencies=[Depends(require_doctor_or_admin)]
)
async def create_patient(
    patient: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new patient (doctors and admins only)."""
    new_patient = Patient(**patient.dict())

    # If doctor, automatically assign to themselves
    if current_user.role == "doctor":
        new_patient.doctor_id = current_user.id

    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)

    return new_patient


@router.get(
    "/patients/{patient_id}",
    response_model=PatientResponse
)
async def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get specific patient (with access control)."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Access control
    if current_user.role == "admin":
        # Admin can view any patient
        pass
    elif current_user.role == "doctor":
        # Doctor can only view assigned patients
        if patient.doctor_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not your patient")
    elif current_user.role == "patient":
        # Patient can only view own data
        if patient.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        raise HTTPException(status_code=403, detail="Forbidden")

    return patient


@router.delete(
    "/patients/{patient_id}",
    dependencies=[Depends(require_admin)]
)
async def delete_patient(
    patient_id: str,
    db: Session = Depends(get_db)
):
    """Delete patient (admin only)."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    db.delete(patient)
    db.commit()

    return {"message": "Patient deleted successfully"}
```

---

## Row-Level Security (RLS)

Sistema Hormonia uses **Supabase Row-Level Security (RLS)** for database-level access control. RLS policies are enforced directly in PostgreSQL, providing an additional security layer beyond application-level checks.

### What is RLS?

Row-Level Security is a PostgreSQL feature that allows you to define policies controlling which rows users can access in database tables. This ensures data isolation even if application code has vulnerabilities.

### RLS Architecture

```
┌─────────────────────────────────────────────────────┐
│          Application (FastAPI Backend)               │
│  Uses: SERVICE_ROLE_KEY (bypasses RLS)              │
└───────────────────┬─────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│              PostgreSQL Database                     │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  Table: patients (RLS ENABLED)               │  │
│  │  • Policy: admin_all_access                  │  │
│  │  • Policy: doctor_assigned_only              │  │
│  │  • Policy: patient_own_data_only             │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### RLS Policy Examples

#### 1. Enable RLS on Table

```sql
-- Enable RLS on patients table
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
```

#### 2. Admin Full Access Policy

```sql
-- Admins can do anything
CREATE POLICY "Admin full access" ON patients
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'admin'
    )
  );
```

#### 3. Doctor Access to Assigned Patients

```sql
-- Doctors can only access their assigned patients
CREATE POLICY "Doctor assigned patients only" ON patients
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'doctor'
      AND patients.doctor_id = users.id
    )
  );

-- Doctors can update their assigned patients
CREATE POLICY "Doctor can update assigned" ON patients
  FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'doctor'
      AND patients.doctor_id = users.id
    )
  );
```

#### 4. Patient Access Own Data Only

```sql
-- Patients can only view their own data
CREATE POLICY "Patient own data only" ON patients
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.id = auth.uid()
      AND users.role = 'patient'
      AND patients.user_id = users.id
    )
  );
```

#### 5. Service Role Bypass (Backend)

```sql
-- Service role (backend) bypasses RLS entirely
-- This is configured by using SUPABASE_SERVICE_ROLE_KEY in backend
-- No explicit policy needed - service role has superuser privileges
```

### Testing RLS Policies

**1. Test as Admin:**
```sql
-- Set role to admin user
SET LOCAL ROLE authenticated;
SET LOCAL "request.jwt.claim.sub" = 'admin-user-uuid';
SET LOCAL "request.jwt.claim.role" = 'admin';

-- Should return all patients
SELECT * FROM patients;
```

**2. Test as Doctor:**
```sql
-- Set role to doctor user
SET LOCAL ROLE authenticated;
SET LOCAL "request.jwt.claim.sub" = 'doctor-user-uuid';
SET LOCAL "request.jwt.claim.role" = 'doctor';

-- Should return only assigned patients
SELECT * FROM patients;
```

**3. Test as Patient:**
```sql
-- Set role to patient user
SET LOCAL ROLE authenticated;
SET LOCAL "request.jwt.claim.sub" = 'patient-user-uuid';
SET LOCAL "request.jwt.claim.role" = 'patient';

-- Should return only own data
SELECT * FROM patients WHERE user_id = 'patient-user-uuid';
```

### RLS Best Practices

1. **Always enable RLS on sensitive tables**
2. **Use service role key in backend** (bypasses RLS for admin operations)
3. **Test policies thoroughly** before production deployment
4. **Document all policies** and their purpose
5. **Audit policy changes** regularly
6. **Use least privilege** principle - grant minimum necessary access

---

## Implementation Guide

### Backend Setup

**1. Install Dependencies:**
```bash
pip install fastapi python-jose[cryptography] passlib[bcrypt] python-multipart
```

**2. Configure Environment Variables:**
```bash
# Backend/.env

# JWT Configuration
SECRET_KEY=your-super-secret-key-minimum-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key
```

**3. Create JWT Utility Functions:**

```python
# Backend/app/core/security.py

from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt
```

**4. Implement Authentication Endpoints:**

```python
# Backend/app/api/v1/endpoints/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from app.api.dependencies.auth import get_current_user
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token
)
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token, TokenRefresh

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login endpoint - returns access and refresh tokens."""

    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()

    # Verify credentials
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Create tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role
        }
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
    try:
        payload = jwt.decode(
            token_data.refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Create new access token
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """Logout endpoint - blacklist token if Redis is enabled."""
    # TODO: Add token to Redis blacklist if enabled
    return {"message": "Successfully logged out"}
```

### Frontend Setup

**1. Create Authentication Service:**

```typescript
// Frontend-v2/src/services/auth.service.ts

import api from './api'; // Axios instance with interceptors

interface LoginCredentials {
  email: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
  };
}

class AuthService {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await api.post<AuthResponse>('/auth/login', credentials);

    // Store tokens
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    localStorage.setItem('user', JSON.stringify(response.data.user));

    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      // Always clear local storage
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
    }
  }

  async refreshToken(): Promise<string> {
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await api.post<AuthResponse>('/auth/refresh', {
      refresh_token: refreshToken
    });

    // Update access token
    localStorage.setItem('access_token', response.data.access_token);

    return response.data.access_token;
  }

  getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  }

  getUser(): any {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
  }

  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  hasRole(role: string): boolean {
    const user = this.getUser();
    return user && user.role === role;
  }

  hasAnyRole(roles: string[]): boolean {
    const user = this.getUser();
    return user && roles.includes(user.role);
  }
}

export default new AuthService();
```

**2. Create Protected Route Component:**

```typescript
// Frontend-v2/src/components/ProtectedRoute.tsx

import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import authService from '../services/auth.service';

interface ProtectedRouteProps {
  allowedRoles?: string[];
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRoles }) => {
  const isAuthenticated = authService.isAuthenticated();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && allowedRoles.length > 0) {
    const hasPermission = authService.hasAnyRole(allowedRoles);
    if (!hasPermission) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return <Outlet />;
};

export default ProtectedRoute;
```

**3. Use Protected Routes:**

```typescript
// Frontend-v2/src/App.tsx

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import PatientsPage from './pages/PatientsPage';
import AdminPage from './pages/AdminPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes - any authenticated user */}
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Route>

        {/* Protected routes - doctors and admins only */}
        <Route element={<ProtectedRoute allowedRoles={['doctor', 'admin']} />}>
          <Route path="/patients" element={<PatientsPage />} />
        </Route>

        {/* Protected routes - admin only */}
        <Route element={<ProtectedRoute allowedRoles={['admin']} />}>
          <Route path="/admin" element={<AdminPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

---

## Security Best Practices

### 1. Token Security

✅ **DO:**
- Use HTTPS in production (always encrypt tokens in transit)
- Set strong SECRET_KEY (minimum 32 characters, random)
- Implement token expiration (short-lived access tokens)
- Store tokens securely (HTTP-only cookies preferred over localStorage)
- Implement refresh token rotation
- Blacklist tokens on logout (using Redis)

❌ **DON'T:**
- Commit SECRET_KEY to git
- Use predictable SECRET_KEY
- Store tokens in URL parameters
- Log tokens in server logs
- Share tokens between users
- Use same token for different environments

### 2. Password Security

✅ **DO:**
- Use bcrypt for password hashing (already implemented)
- Enforce strong password requirements (minimum 8 characters, mix of types)
- Implement rate limiting on login endpoint
- Use account lockout after failed attempts
- Implement password reset functionality
- Hash passwords before storing

❌ **DON'T:**
- Store plain-text passwords
- Use weak hashing algorithms (MD5, SHA1)
- Display detailed error messages on login failure ("Invalid email or password" is good)
- Allow unlimited login attempts

### 3. API Security

✅ **DO:**
- Validate all input data
- Use parameterized queries (prevent SQL injection)
- Implement rate limiting
- Enable CORS with specific origins (not *)
- Log authentication events
- Implement request size limits
- Use security headers (HSTS, CSP, X-Frame-Options)

❌ **DON'T:**
- Trust client-side data
- Expose sensitive information in error messages
- Allow unrestricted CORS
- Return stack traces in production
- Skip input validation

### 4. RLS Security

✅ **DO:**
- Enable RLS on all sensitive tables
- Test RLS policies thoroughly
- Use least privilege principle
- Document all policies
- Audit policy changes
- Use service role key in backend (bypasses RLS)

❌ **DON'T:**
- Disable RLS in production
- Create overly permissive policies
- Skip policy testing
- Use anon key in backend

### 5. Token Rotation

Implement refresh token rotation for enhanced security:

```python
# When refreshing token, also issue new refresh token
@router.post("/refresh")
async def refresh_token(token_data: TokenRefresh, db: Session = Depends(get_db)):
    # ... token validation ...

    # Create NEW access token
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})

    # Create NEW refresh token (rotation)
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Optionally: Blacklist old refresh token in Redis
    # redis_client.setex(f"blacklist:{token_data.refresh_token}", 86400, "1")

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,  # Return new refresh token
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
```

---

## Troubleshooting

### Common Issues

See the complete [Troubleshooting Guide](../../docs/TROUBLESHOOTING_GUIDE.md#authentication-issues) for authentication-specific problems:

- [401 Unauthorized Errors](../../docs/TROUBLESHOOTING_GUIDE.md#401-unauthorized-errors)
- [403 Forbidden Errors](../../docs/TROUBLESHOOTING_GUIDE.md#403-forbidden-errors)
- [Token Expired](../../docs/TROUBLESHOOTING_GUIDE.md#token-expired)
- [RLS Policies Blocking Queries](../../docs/TROUBLESHOOTING_GUIDE.md#rls-policies-blocking-queries)

---

## Testing Authentication

### 1. Unit Tests

```python
# Backend/tests/test_auth.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_login_success():
    """Test successful login."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "doctor@hormonia.app",
            "password": "TestPassword123!"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "doctor"

def test_login_invalid_credentials():
    """Test login with invalid credentials."""
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "doctor@hormonia.app",
            "password": "WrongPassword"
        }
    )

    assert response.status_code == 401
    assert "detail" in response.json()

def test_access_protected_endpoint():
    """Test accessing protected endpoint with valid token."""
    # First login
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "doctor@hormonia.app",
            "password": "TestPassword123!"
        }
    )
    token = login_response.json()["access_token"]

    # Then access protected endpoint
    response = client.get(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

def test_access_protected_endpoint_no_token():
    """Test accessing protected endpoint without token."""
    response = client.get("/api/v1/patients")
    assert response.status_code == 401

def test_refresh_token():
    """Test token refresh."""
    # Login to get refresh token
    login_response = client.post(
        "/api/v1/auth/login",
        data={
            "username": "doctor@hormonia.app",
            "password": "TestPassword123!"
        }
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token}
    )

    assert refresh_response.status_code == 200
    assert "access_token" in refresh_response.json()
```

### 2. Integration Tests

```python
# Backend/tests/integration/test_rbac.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def get_token(role: str) -> str:
    """Helper to get token for specific role."""
    credentials = {
        "admin": ("admin@hormonia.app", "AdminPass123!"),
        "doctor": ("doctor@hormonia.app", "DoctorPass123!"),
        "patient": ("patient@hormonia.app", "PatientPass123!")
    }

    email, password = credentials[role]
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password}
    )
    return response.json()["access_token"]

def test_admin_can_view_all_patients():
    """Admins should see all patients."""
    token = get_token("admin")
    response = client.get(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    # Admin sees all patients
    patients = response.json()["items"]
    assert len(patients) > 0

def test_doctor_sees_only_assigned_patients():
    """Doctors should only see assigned patients."""
    token = get_token("doctor")
    response = client.get(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    patients = response.json()["items"]

    # All patients should be assigned to this doctor
    doctor_id = "doctor-uuid-here"
    for patient in patients:
        assert patient["doctor_id"] == doctor_id

def test_patient_cannot_view_patients_list():
    """Patients should not access patients list."""
    token = get_token("patient")
    response = client.get(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403

def test_admin_can_delete_patient():
    """Only admins can delete patients."""
    admin_token = get_token("admin")
    doctor_token = get_token("doctor")

    # Admin can delete
    response_admin = client.delete(
        "/api/v1/patients/test-patient-id",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    # Should succeed or return 404 if patient doesn't exist
    assert response_admin.status_code in [200, 404]

    # Doctor cannot delete
    response_doctor = client.delete(
        "/api/v1/patients/test-patient-id",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )
    assert response_doctor.status_code == 403
```

---

## Additional Resources

- [Backend README](../README.md) - Backend setup and architecture
- [API Reference](./API.md) - Complete API documentation
- [Troubleshooting Guide](../../docs/TROUBLESHOOTING_GUIDE.md) - Authentication troubleshooting
- [Security Guide](../../docs/SECURITY.md) - Comprehensive security documentation
- [Database Guide](./DATABASE_COMPLETE_GUIDE.md) - RLS policies and database security

---

**Last Updated:** 2025-09-29
**Maintained By:** Sistema Hormonia Development Team
**Questions?** Create an issue or contact #hormonia-dev on Slack