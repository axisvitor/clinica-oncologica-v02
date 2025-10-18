---
title: "Archive v1 Endpoints After v2 Migration Complete"
labels: ["cleanup", "deprecation", "breaking-change", "p4-backlog"]
assignees: []
milestone: "v1 Sunset"
---

## 🎯 Objective
Remove v1 endpoints after v2 migration complete and validated in production.

## 📋 Prerequisites
- [ ] All v2 endpoints deployed and stable
- [ ] Frontend 100% migrated to v2
- [ ] 30-day grace period after deprecation warnings
- [ ] Zero v1 API usage in production logs

## ✅ Acceptance Criteria
- [ ] Add 410 Gone responses to all v1 endpoints
- [ ] Monitor production for v1 usage (30 days)
- [ ] Remove v1 router code
- [ ] Remove v1 tests
- [ ] Update all documentation
- [ ] Announce in changelog and release notes

## ⏱️ Estimated Effort
**8 hours** (after 30-day grace period)

## 🚨 Rollback Plan
Keep v1 code in git history for 90 days in case rollback needed.
