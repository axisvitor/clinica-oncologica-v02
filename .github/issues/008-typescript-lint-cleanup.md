---
title: "Fix TypeScript Lint Errors in API Client Core"
labels: ["code-quality", "frontend", "typescript", "p3-low"]
assignees: []
milestone: "Code Quality"
---

## 🎯 Objective
Clean up duplicate exports and type incompatibilities in API client core.

## 📋 Lint Errors to Fix
- Duplicate `ApiError` export declarations
- Duplicate `ApiResponse`, `PaginatedResponse`, `RequestOptions` exports
- `exactOptionalPropertyTypes` violations in request methods (params can be undefined)

## ✅ Acceptance Criteria
- [ ] Remove duplicate export declarations
- [ ] Fix `RequestOptions` type to allow undefined params
- [ ] All TypeScript files compile without errors
- [ ] No lint warnings in api-client directory
- [ ] Tests still pass after changes

## 📁 Files
- `frontend-hormonia/src/lib/api-client/core.ts`
- `frontend-hormonia/src/lib/api-client/index.ts`

## ⏱️ Estimated Effort
**2 hours**
