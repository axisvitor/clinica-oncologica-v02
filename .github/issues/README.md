# GitHub Issues - Follow-Up Tickets

This directory contains 9 pre-written GitHub issues for post-hotfix work.

## 📊 Priority Breakdown

### P0-P1 Critical (18 hours total)
1. **#001** - RBAC Regression Tests (4h)
2. **#002** - Cursor Pagination Tests (6h)
3. **#003** - Session Validation Tests (5h)
4. **#004** - Frontend Empty Response Tests (3h)

### P2 Medium - v2 Migration (28 hours total)
5. **#005** - Auth v2 Migration (8h)
6. **#006** - Analytics v2 Migration (16h)
7. **#007** - Quiz v2 Investigation (4h)

### P3-P4 Low - Code Quality (10 hours total)
8. **#008** - TypeScript Lint Cleanup (2h)
9. **#009** - v1 Deprecation (8h)

**Total Effort:** ~56 hours (~7 days)

---

## 🚀 How to Import Issues

### Option 1: GitHub CLI (Recommended)

```bash
# Install GitHub CLI if needed
# https://cli.github.com/

# Authenticate
gh auth login

# Create all issues
cd .github/issues
for file in *.md; do
  if [ "$file" != "README.md" ]; then
    gh issue create --body-file "$file" --repo OWNER/REPO
  fi
done
```

### Option 2: GitHub Web UI

1. Go to your repository
2. Click "Issues" → "New Issue"
3. Copy content from each `.md` file
4. Paste into issue body
5. Set labels, milestone from frontmatter
6. Create issue

### Option 3: GitHub API

```bash
# Using curl
for file in *.md; do
  if [ "$file" != "README.md" ]; then
    TITLE=$(grep "^title:" $file | cut -d'"' -f2)
    BODY=$(sed '1,/^---$/d' $file | sed '/^---$/,$d')
    
    curl -X POST \
      -H "Authorization: token YOUR_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      https://api.github.com/repos/OWNER/REPO/issues \
      -d "{\"title\":\"$TITLE\",\"body\":\"$BODY\"}"
  fi
done
```

---

## 📋 Sprint Planning Suggestions

### Sprint 1 (Week 1-2): Critical Tests
**Goal:** Production confidence through comprehensive testing

- [ ] #001 - RBAC Tests
- [ ] #002 - Pagination Tests  
- [ ] #003 - Session Tests
- [ ] #004 - Frontend Tests

**Blockers:** None  
**Deliverable:** CI/CD pipeline with regression tests

---

### Sprint 2 (Week 3-4): Auth v2 Migration
**Goal:** Consolidate auth under /api/v2 namespace

- [ ] #005 - Auth v2 Migration

**Blockers:** Sprint 1 completion (tests needed first)  
**Deliverable:** v2 session endpoints with deprecation plan

---

### Sprint 3 (Week 5-7): Analytics & Investigation
**Goal:** Complete v2 migration planning

- [ ] #006 - Analytics v2 Migration
- [ ] #007 - Quiz v2 Investigation

**Blockers:** #005 completion  
**Deliverable:** All core APIs on v2

---

### Sprint 4 (Week 8): Code Quality
**Goal:** Clean up technical debt

- [ ] #008 - TypeScript Lint Cleanup

**Blockers:** None (can run in parallel)  
**Deliverable:** Zero lint errors

---

### Future Backlog: v1 Sunset
**Goal:** Remove deprecated v1 endpoints

- [ ] #009 - v1 Deprecation (after 6-month grace period)

**Blockers:** All v2 migrations complete + monitoring  
**Deliverable:** Clean v2-only API

---

## 🎯 Success Metrics

Track these metrics for each ticket:

- **Tests Written:** Target test count
- **Code Coverage:** Should increase
- **Build Time:** Should not degrade significantly
- **API Performance:** Should maintain or improve
- **Documentation:** Updated and clear

---

## 🔗 Dependencies Graph

```
#001, #002, #003, #004 (Tests)
    ↓
#005 (Auth v2)
    ↓
#006 (Analytics v2), #007 (Quiz Investigation)
    ↓
#009 (v1 Deprecation)

#008 (TypeScript Cleanup) - Can run anytime
```

---

## 📞 Support

Questions about these tickets? Check:
- `FOLLOW_UP_TICKETS.md` - Detailed ticket descriptions
- `DEPLOYMENT_READINESS.md` - Production deployment guide
- Test skeletons in `backend-hormonia/tests/` - Implementation hints

---

**Last Updated:** 2025-10-18  
**Status:** Ready for import
