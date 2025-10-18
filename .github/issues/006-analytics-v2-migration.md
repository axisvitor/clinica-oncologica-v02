---
title: "Migrate Remaining Analytics Endpoints to v2"
labels: ["enhancement", "api-v2", "analytics", "p2-medium", "backend"]
assignees: []
milestone: "API v2 Consolidation"
---

## 🎯 Objective
Migrate 8 secondary analytics endpoints from v1 to v2 with cursor pagination and Redis caching.

## 📋 Endpoints to Migrate
- `/api/v1/analytics/timeseries` → `/api/v2/analytics/timeseries`
- `/api/v1/analytics/reports` → `/api/v2/analytics/reports`
- `/api/v1/analytics/engagement` → `/api/v2/analytics/engagement`
- `/api/v1/analytics/outcomes` → `/api/v2/analytics/outcomes`
- `/api/v1/analytics/appointments` → `/api/v2/analytics/appointments`
- `/api/v1/analytics/messages` → `/api/v2/analytics/messages`
- `/api/v1/analytics/revenue` → `/api/v2/analytics/revenue`
- `/api/v1/analytics/system-usage` → `/api/v2/analytics/system-usage`

## ✅ Acceptance Criteria
- [ ] All 8 v2 endpoints implemented with cursor pagination
- [ ] Redis caching (15 min TTL) for all endpoints
- [ ] RBAC enforcement (doctors see own data, admins see all)
- [ ] Frontend updated to use v2 endpoints
- [ ] Integration tests for all endpoints
- [ ] v1 endpoints marked deprecated

## ⏱️ Estimated Effort
**16 hours** - 2 hours per endpoint

## 📁 Files
**Backend:** `backend-hormonia/app/api/v2/analytics.py`  
**Frontend:** `frontend-hormonia/src/lib/api-client/analytics.ts`
