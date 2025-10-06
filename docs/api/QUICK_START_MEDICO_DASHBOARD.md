# Quick Start: Medico Dashboard Stats

## 🚀 Getting Started

Replace the hardcoded zeros in `MedicoDashboard.tsx` with real-time statistics from the new endpoint.

---

## 1. Update Frontend Component

**File**: `frontend-hormonia/src/pages/MedicoDashboard.tsx`

**Before** (lines 97, 101, 105, 109):
```tsx
<p className="text-3xl font-bold">0</p>
```

**After**:
```tsx
import { useEffect, useState } from 'react';
import { auth } from '@/lib/firebase';

interface DashboardStats {
  pacientes_ativos: number;
  consultas_hoje: number;
  pendencias: number;
  exames_aguardando: number;
  engagement: {
    messages_today: number;
    messages_unread: number;
    response_rate: number;
    avg_response_time_minutes: number | null;
  };
  alerts: {
    total: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}

export function MedicoDashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const token = await auth.currentUser?.getIdToken();
        const response = await fetch(`${import.meta.env.VITE_API_URL}/api/v1/medico/dashboard-stats`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.ok) {
          const data = await response.json();
          setStats(data);
        }
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 120000); // Refresh every 2 minutes
    return () => clearInterval(interval);
  }, []);

  if (loading) return <Skeleton />;

  return (
    <div className="grid grid-cols-4 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Pacientes Ativos</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{stats?.pacientes_ativos ?? 0}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Consultas Hoje</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{stats?.consultas_hoje ?? 0}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pendências</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{stats?.pendencias ?? 0}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Exames Aguardando</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{stats?.exames_aguardando ?? 0}</p>
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 2. Test the Backend

```bash
# 1. Start backend
cd backend-hormonia
source venv/bin/activate
uvicorn app.main:app --reload

# 2. Get Firebase token (login as doctor)
# Use Firebase Console or your frontend to get ID token

# 3. Test endpoint
curl -X GET "http://localhost:8000/api/v1/medico/dashboard-stats" \
  -H "Authorization: Bearer YOUR_FIREBASE_TOKEN" \
  -H "Accept: application/json" | jq

# Expected response:
# {
#   "pacientes_ativos": 45,
#   "consultas_hoje": 8,
#   "pendencias": 12,
#   "exames_aguardando": 0,
#   "engagement": { ... },
#   "alerts": { ... },
#   "timestamp": "2025-10-06T14:30:00Z"
# }
```

---

## 3. Environment Variables

Ensure `.env` has:

```env
# Backend
DATABASE_URL=postgresql://user:pass@localhost:5432/hormonia
REDIS_URL=redis://localhost:6379/0
FIREBASE_ADMIN_PROJECT_ID=your-project-id
FIREBASE_ADMIN_PRIVATE_KEY=your-private-key
FIREBASE_ADMIN_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com

# Frontend
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
```

---

## 4. Verify Redis Caching

```bash
# Connect to Redis
redis-cli

# Check cache key
GET medico:dashboard-stats:<DOCTOR_UUID>

# Expected: JSON string with stats (TTL: 120 seconds)

# Check TTL
TTL medico:dashboard-stats:<DOCTOR_UUID>
# Should return ~120 seconds on first request

# Second request should be faster (cache hit)
```

---

## 5. Production Deployment

### Railway Deployment

```bash
# Set environment variables in Railway dashboard:
DATABASE_URL=<railway-postgres-url>
REDIS_URL=<railway-redis-url>
FIREBASE_ADMIN_PROJECT_ID=<project-id>
FIREBASE_ADMIN_PRIVATE_KEY=<private-key>
FIREBASE_ADMIN_CLIENT_EMAIL=<client-email>

# Deploy
railway up
```

### Frontend Environment

```env
# Production .env
VITE_API_URL=https://api.hormonia.com
```

---

## 6. Troubleshooting

### Error: 401 Unauthorized

**Cause**: Invalid or missing Firebase token

**Solution**:
```typescript
// Ensure token is fresh
const token = await auth.currentUser?.getIdToken(true); // Force refresh
```

### Error: 403 Forbidden

**Cause**: User doesn't have doctor role

**Solution**: Verify user has `role: 'DOCTOR'` in database
```sql
SELECT id, email, role FROM users WHERE email = 'doctor@example.com';
```

### Error: All Stats Return 0

**Cause**: No data in database or doctor_id mismatch

**Solution**:
```sql
-- Check if patients are assigned to this doctor
SELECT COUNT(*) FROM patients WHERE doctor_id = '<DOCTOR_UUID>';

-- Check messages
SELECT COUNT(*) FROM messages m
JOIN patients p ON m.patient_id = p.id
WHERE p.doctor_id = '<DOCTOR_UUID>';
```

### Cache Not Working

**Cause**: Redis connection issues

**Solution**:
```bash
# Check Redis health
curl http://localhost:8000/api/v1/redis/health

# Check Redis connection
redis-cli PING
# Expected: PONG
```

---

## 7. Next Steps

1. **Add Loading States**:
   ```tsx
   {loading ? <Skeleton /> : <StatCard value={stats.pacientes_ativos} />}
   ```

2. **Add Error Handling**:
   ```tsx
   {error && <Alert variant="destructive">{error}</Alert>}
   ```

3. **Add Real-time Updates**:
   - WebSocket notifications for critical alerts
   - Live updates without polling

4. **Enhance UI**:
   - Trend indicators (↑ ↓)
   - Color coding for alerts
   - Charts for engagement metrics

---

## 📚 Related Documentation

- [Full API Documentation](./MEDICO_DASHBOARD_STATS.md)
- [Frontend Integration Guide](../frontend/MEDICO_DASHBOARD.md)
- [Database Schema](../database/SCHEMA.md)

---

## ✅ Verification Checklist

- [ ] Backend endpoint returns 200 with valid token
- [ ] Response matches schema (all fields present)
- [ ] Redis caching works (second request faster)
- [ ] Frontend displays real numbers (not zeros)
- [ ] Auto-refresh works (updates every 2 minutes)
- [ ] Error states handled gracefully
- [ ] Production deployment successful
