# Frontend Integration Fixes Documentation

## Overview

This document details all frontend changes required to integrate with the updated backend API contracts. All changes are backwards-compatible and follow TypeScript best practices.

## Table of Contents

1. [Admin Users Integration](#admin-users-integration)
2. [Notifications Integration](#notifications-integration)
3. [Dashboard Statistics](#dashboard-statistics)
4. [User Activity Tracking](#user-activity-tracking)
5. [Migration Guide](#migration-guide)
6. [Testing](#testing)

---

## Admin Users Integration

### Backend Change
The `/api/v1/admin/users` endpoint now returns:
```typescript
interface AdminUsersResponse {
  items: UserProfile[];
  total: number;
}
```

Previously returned: `UserProfile[]` directly

### Frontend Updates Required

#### 1. Update `useUserAdmin` Hook

**File:** `frontend-hormonia/src/hooks/useUserAdmin.ts`

**Before:**
```typescript
export function useUserAdmin() {
  return useQuery({
    queryKey: ['admin', 'users'],
    queryFn: async () => {
      const response = await api.get('/admin/users');
      return response.data as UserProfile[];
    },
  });
}
```

**After:**
```typescript
interface AdminUsersResponse {
  items: UserProfile[];
  total: number;
}

export function useUserAdmin(params?: { skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: async () => {
      const response = await api.get<AdminUsersResponse>('/admin/users', {
        params,
      });
      return response.data;
    },
  });
}
```

#### 2. Update Component Usage

**File:** `frontend-hormonia/src/pages/AdminUsers.tsx`

**Before:**
```typescript
const { data: users, isLoading } = useUserAdmin();

return (
  <div>
    {users?.map(user => (
      <UserCard key={user.id} user={user} />
    ))}
  </div>
);
```

**After:**
```typescript
const { data, isLoading } = useUserAdmin({ skip: 0, limit: 20 });

return (
  <div>
    <div className="total-count">Total Users: {data?.total}</div>
    {data?.items.map(user => (
      <UserCard key={user.id} user={user} />
    ))}
    <Pagination total={data?.total || 0} />
  </div>
);
```

#### 3. Add Pagination Support

**New File:** `frontend-hormonia/src/components/UserPagination.tsx`

```typescript
interface UserPaginationProps {
  total: number;
  skip: number;
  limit: number;
  onPageChange: (skip: number) => void;
}

export function UserPagination({ total, skip, limit, onPageChange }: UserPaginationProps) {
  const totalPages = Math.ceil(total / limit);
  const currentPage = Math.floor(skip / limit) + 1;

  return (
    <div className="pagination">
      <button
        disabled={currentPage === 1}
        onClick={() => onPageChange((currentPage - 2) * limit)}
      >
        Previous
      </button>
      <span>Page {currentPage} of {totalPages}</span>
      <button
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage * limit)}
      >
        Next
      </button>
    </div>
  );
}
```

---

## Notifications Integration

### Backend Change
The `/api/v1/notifications` endpoint now returns:
```typescript
interface NotificationsResponse {
  items: Notification[];
  unread_count: number;
}
```

Previously returned: `Notification[]` directly

### Frontend Updates Required

#### 1. Update `useNotifications` Hook

**File:** `frontend-hormonia/src/hooks/useNotifications.ts`

**Before:**
```typescript
export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const response = await api.get('/notifications');
      return response.data as Notification[];
    },
  });
}
```

**After:**
```typescript
interface NotificationsResponse {
  items: Notification[];
  unread_count: number;
}

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: async () => {
      const response = await api.get<NotificationsResponse>('/notifications');
      return response.data;
    },
  });
}
```

#### 2. Update NotificationCenter Component

**File:** `frontend-hormonia/src/components/NotificationCenter.tsx`

**Before:**
```typescript
const { data: notifications } = useNotifications();

return (
  <div className="notification-center">
    <div className="header">
      <h3>Notifications</h3>
      <Badge>{notifications?.filter(n => !n.read).length}</Badge>
    </div>
    {notifications?.map(notification => (
      <NotificationItem key={notification.id} notification={notification} />
    ))}
  </div>
);
```

**After:**
```typescript
const { data } = useNotifications();

return (
  <div className="notification-center">
    <div className="header">
      <h3>Notifications</h3>
      <Badge count={data?.unread_count} />
    </div>
    {data?.items.map(notification => (
      <NotificationItem key={notification.id} notification={notification} />
    ))}
  </div>
);
```

#### 3. Update Notification Badge Component

**File:** `frontend-hormonia/src/components/NotificationBadge.tsx`

```typescript
interface NotificationBadgeProps {
  count?: number;
}

export function NotificationBadge({ count }: NotificationBadgeProps) {
  if (!count || count === 0) return null;

  return (
    <span className="notification-badge" data-count={count}>
      {count > 99 ? '99+' : count}
    </span>
  );
}
```

---

## Dashboard Statistics

### Backend Change
The `/api/v1/admin/dashboard/stats` endpoint now returns metrics with trends:
```typescript
interface SystemStats {
  users: MetricWithTrend;
  appointments: MetricWithTrend;
  revenue: MetricWithTrend;
  active_users: MetricWithTrend;
}

interface MetricWithTrend {
  value: number;
  trend?: {
    percentage: number;
    direction: 'up' | 'down' | 'stable';
  };
}
```

### Frontend Updates Required

#### 1. Update `useSystemStats` Hook

**File:** `frontend-hormonia/src/hooks/useSystemStats.ts`

**New Hook:**
```typescript
interface MetricWithTrend {
  value: number;
  trend?: {
    percentage: number;
    direction: 'up' | 'down' | 'stable';
  };
}

interface SystemStats {
  users: MetricWithTrend;
  appointments: MetricWithTrend;
  revenue: MetricWithTrend;
  active_users: MetricWithTrend;
}

export function useSystemStats() {
  return useQuery({
    queryKey: ['admin', 'dashboard', 'stats'],
    queryFn: async () => {
      const response = await api.get<SystemStats>('/admin/dashboard/stats');
      return response.data;
    },
    refetchInterval: 30000, // Refresh every 30 seconds
  });
}
```

#### 2. Create MetricCard Component

**File:** `frontend-hormonia/src/components/MetricCard.tsx`

```typescript
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MetricCardProps {
  title: string;
  metric: MetricWithTrend;
  format?: 'number' | 'currency' | 'percentage';
}

export function MetricCard({ title, metric, format = 'number' }: MetricCardProps) {
  const formatValue = (value: number) => {
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('pt-BR', {
          style: 'currency',
          currency: 'BRL',
        }).format(value);
      case 'percentage':
        return `${value}%`;
      default:
        return value.toLocaleString('pt-BR');
    }
  };

  const getTrendIcon = () => {
    if (!metric.trend) return null;

    switch (metric.trend.direction) {
      case 'up':
        return <TrendingUp className="trend-icon trend-up" />;
      case 'down':
        return <TrendingDown className="trend-icon trend-down" />;
      default:
        return <Minus className="trend-icon trend-stable" />;
    }
  };

  const getTrendColor = () => {
    if (!metric.trend) return '';

    switch (metric.trend.direction) {
      case 'up':
        return 'text-green-600';
      case 'down':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="metric-card">
      <h4 className="metric-title">{title}</h4>
      <div className="metric-value">{formatValue(metric.value)}</div>
      {metric.trend && (
        <div className={`metric-trend ${getTrendColor()}`}>
          {getTrendIcon()}
          <span>{Math.abs(metric.trend.percentage).toFixed(1)}%</span>
        </div>
      )}
    </div>
  );
}
```

#### 3. Update AdminDashboard Component

**File:** `frontend-hormonia/src/pages/AdminDashboard.tsx`

```typescript
export function AdminDashboard() {
  const { data: stats, isLoading } = useSystemStats();

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="admin-dashboard">
      <h1>Dashboard</h1>
      <div className="metrics-grid">
        <MetricCard title="Total Users" metric={stats!.users} />
        <MetricCard title="Appointments" metric={stats!.appointments} />
        <MetricCard
          title="Revenue"
          metric={stats!.revenue}
          format="currency"
        />
        <MetricCard title="Active Users" metric={stats!.active_users} />
      </div>
    </div>
  );
}
```

---

## User Activity Tracking

### Backend Change
New endpoint: `/api/v1/admin/users/activity`

Returns:
```typescript
interface ActivityLog {
  user_id: string;
  action: string;
  timestamp: string;
  details?: Record<string, any>;
}
```

### Frontend Implementation

#### 1. Create `useUserActivity` Hook

**File:** `frontend-hormonia/src/hooks/useUserActivity.ts`

```typescript
interface ActivityLog {
  user_id: string;
  action: string;
  timestamp: string;
  details?: Record<string, any>;
}

interface UseUserActivityParams {
  userId?: string;
  startDate?: string;
  endDate?: string;
}

export function useUserActivity(params: UseUserActivityParams) {
  return useQuery({
    queryKey: ['admin', 'users', 'activity', params],
    queryFn: async () => {
      const response = await api.get<ActivityLog[]>('/admin/users/activity', {
        params,
      });
      return response.data;
    },
    enabled: !!params.userId, // Only fetch if userId is provided
  });
}
```

#### 2. Create ActivityLog Component

**File:** `frontend-hormonia/src/components/ActivityLog.tsx`

```typescript
import { formatDistanceToNow } from 'date-fns';
import { ptBR } from 'date-fns/locale';

interface ActivityLogProps {
  userId: string;
}

export function ActivityLog({ userId }: ActivityLogProps) {
  const { data: activities, isLoading } = useUserActivity({ userId });

  if (isLoading) return <LoadingSpinner />;
  if (!activities?.length) return <p>No activity found</p>;

  return (
    <div className="activity-log">
      <h3>User Activity</h3>
      <ul className="activity-list">
        {activities.map((activity, index) => (
          <li key={index} className="activity-item">
            <span className="activity-action">{activity.action}</span>
            <span className="activity-time">
              {formatDistanceToNow(new Date(activity.timestamp), {
                addSuffix: true,
                locale: ptBR,
              })}
            </span>
            {activity.details && (
              <pre className="activity-details">
                {JSON.stringify(activity.details, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

---

## Migration Guide

### Step 1: Update Dependencies

```bash
cd frontend-hormonia
npm install date-fns lucide-react
```

### Step 2: Update Type Definitions

Create or update `frontend-hormonia/src/types/api.ts`:

```typescript
// API Response Types
export interface AdminUsersResponse {
  items: UserProfile[];
  total: number;
}

export interface NotificationsResponse {
  items: Notification[];
  unread_count: number;
}

export interface MetricWithTrend {
  value: number;
  trend?: {
    percentage: number;
    direction: 'up' | 'down' | 'stable';
  };
}

export interface SystemStats {
  users: MetricWithTrend;
  appointments: MetricWithTrend;
  revenue: MetricWithTrend;
  active_users: MetricWithTrend;
}

export interface ActivityLog {
  user_id: string;
  action: string;
  timestamp: string;
  details?: Record<string, any>;
}
```

### Step 3: Update Hooks

1. Update `useUserAdmin.ts`
2. Update `useNotifications.ts`
3. Create `useSystemStats.ts`
4. Create `useUserActivity.ts`

### Step 4: Update Components

1. Update `AdminUsers.tsx`
2. Update `NotificationCenter.tsx`
3. Update `AdminDashboard.tsx`
4. Create `MetricCard.tsx`
5. Create `ActivityLog.tsx`
6. Create `UserPagination.tsx`

### Step 5: Add Styles

Update `frontend-hormonia/src/styles/components.css`:

```css
/* Metric Card */
.metric-card {
  padding: 1.5rem;
  background: white;
  border-radius: 0.5rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.metric-title {
  font-size: 0.875rem;
  color: #6b7280;
  margin-bottom: 0.5rem;
}

.metric-value {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.metric-trend {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
}

.trend-up { color: #10b981; }
.trend-down { color: #ef4444; }
.trend-stable { color: #6b7280; }

/* Notification Badge */
.notification-badge {
  background: #ef4444;
  color: white;
  border-radius: 9999px;
  padding: 0.125rem 0.5rem;
  font-size: 0.75rem;
  font-weight: bold;
}

/* Activity Log */
.activity-log {
  background: white;
  padding: 1rem;
  border-radius: 0.5rem;
}

.activity-item {
  padding: 0.75rem;
  border-bottom: 1px solid #e5e7eb;
}

.activity-action {
  font-weight: 600;
  margin-right: 0.5rem;
}

.activity-time {
  color: #6b7280;
  font-size: 0.875rem;
}
```

---

## Testing

### Unit Tests

All hooks and components have corresponding test files in `frontend-hormonia/tests/integration/`.

Run tests:
```bash
cd frontend-hormonia
npm test
```

### Integration Tests

Run integration tests:
```bash
npm run test:integration
```

### E2E Tests

Run E2E tests (requires backend running):
```bash
npm run test:e2e
```

### Manual Testing Checklist

- [ ] Admin users list shows pagination
- [ ] Admin users list shows total count
- [ ] Notifications show unread count badge
- [ ] Dashboard shows all 4 metrics
- [ ] Dashboard shows trend indicators
- [ ] Trend arrows point correct direction
- [ ] Trend percentages display correctly
- [ ] User activity log displays when user selected
- [ ] All API errors handled gracefully

---

## Rollback Procedure

If issues arise, revert changes:

1. Restore hooks from backup
2. Restore components from backup
3. Deploy previous frontend version
4. Backend remains compatible (returns new format)

The backend changes are backwards-compatible, so old frontend code will continue to work (it will just ignore `total`, `unread_count`, and `trend` fields).

---

## Support

For issues or questions:
- Check integration test logs
- Review API contract documentation
- Contact backend team for API issues
- Contact frontend team for UI issues
