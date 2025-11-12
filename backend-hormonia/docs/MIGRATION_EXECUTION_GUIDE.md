# Documentation Migration - Execution Guide

**Quick Reference for Implementing the New Documentation Structure**

---

## Overview

This guide provides step-by-step instructions to reorganize backend-hormonia documentation from 85+ scattered files into a hierarchical, purpose-driven structure.

**Read First**:
- `_NEW_STRUCTURE_PROPOSAL.md` (comprehensive proposal)
- `FILE_CATEGORIZATION_REFERENCE.md` (file-by-file mapping)

---

## Phase 1: Preparation (Day 1)

### 1.1 Team Review & Approval
- [ ] Share `_NEW_STRUCTURE_PROPOSAL.md` with team
- [ ] Discuss in team meeting
- [ ] Get approval to proceed
- [ ] Assign person to lead migration

### 1.2 Create Git Branch
```bash
cd C:\Meu Projetos\clinica-oncologica-v02-1
git checkout -b docs/structure-reorganization
```

### 1.3 Create Backup
```bash
# Backup entire docs folder
mkdir docs/_backup_$(date +%s)
cp -r docs/*.md docs/_backup_$(date +%s)/
echo "Backup created successfully"
```

### 1.4 Document Current State
```bash
# Record current file count
find docs -type f -name "*.md" | wc -l
# Create file listing
find docs -type f -name "*.md" > docs/_CURRENT_FILE_LIST.txt
```

---

## Phase 2: Folder Structure Creation (Day 2)

### 2.1 Create New Folder Hierarchy
```bash
cd backend-hormonia/docs

# Main categories
mkdir -p guides/{deployment,database,security,monitoring,troubleshooting}
mkdir -p api/{v1,webhooks,upload,errors}
mkdir -p architecture/{COMPONENTS,DATABASE,PATTERNS}
mkdir -p operations/{deployment,monitoring,security,backup-recovery,scaling,runbooks}
mkdir -p reference
mkdir -p archive/{migration-reports,phase-reports,implementation-details,quick-references,bug-fixes,other}
```

### 2.2 Create README Files for Each Folder
```bash
# Create a template README for each folder
for dir in guides api architecture operations reference archive; do
    cat > "$dir/README.md" << 'EOF'
# Documentation

See main [README.md](../README.md) for navigation and structure overview.
EOF
done
```

### 2.3 Verify Structure
```bash
# List new structure
tree docs -d -L 2
# or
find docs -type d | sort
```

---

## Phase 3: File Migration (Days 3-4)

### 3.1 Move API Files
```bash
# From root to api/
mv docs/QUIZ_PUBLIC_API.md docs/api/v1/quiz.md
mv docs/upload_api_guide.md docs/api/upload/UPLOAD_API_GUIDE.md
mv docs/upload_security.md docs/api/upload/UPLOAD_SECURITY.md
mv docs/IDEMPOTENCY.md docs/api/webhooks/IDEMPOTENCY.md
mv docs/WEBHOOK_IDEMPOTENCY.md docs/api/webhooks/IDEMPOTENCY.md  # Consolidate
mv docs/WEBHOOK_SECURITY.md docs/api/webhooks/WEBHOOK_SECURITY.md
mv docs/WEBHOOK_ENDPOINT_FIX.md docs/api/webhooks/WEBHOOK_GUIDE.md
mv docs/RATE_LIMITING.md docs/api/RATE_LIMITING.md
mv docs/api/API.md docs/api/OVERVIEW.md
```

### 3.2 Move Architecture Files
```bash
# From root to architecture/
mv docs/QUERY_OPTIMIZATION.md docs/architecture/PATTERNS/QUERY_PATTERNS.md
mv docs/QUERY_CACHE_IMPLEMENTATION.md docs/architecture/COMPONENTS/CACHING.md
mv docs/i18n-architecture.md docs/architecture/INTERNATIONALIZATION.md
mv docs/EAGER_LOADING_QUICK_REFERENCE.md docs/architecture/DATABASE/EAGER_LOADING.md
mv docs/GIN_INDEXES_QUICK_REFERENCE.md docs/architecture/DATABASE/INDEXING_STRATEGY.md

# Keep database folder structure
mv docs/database/DATA_FLOW_GUIDE.md docs/architecture/DATA_FLOW.md
mv docs/database/DATABASE_OVERVIEW.md docs/architecture/DATABASE/SCHEMA.md
mv docs/database/SCHEMA_REFERENCE.md docs/architecture/DATABASE/SCHEMA.md  # Consolidate
mv docs/database/PERFORMANCE_GUIDE.md docs/architecture/DATABASE/PERFORMANCE.md
```

### 3.3 Move Operations Files
```bash
# From root to operations/
mv docs/DEPLOYMENT_CONFIGURATION.md docs/operations/deployment/DEPLOYMENT_GUIDE.md
mv docs/PRODUCTION_MONITORING_CHECKLIST.md docs/operations/PRODUCTION_CHECKLIST.md
mv docs/MONITORING.md docs/operations/monitoring/MONITORING_GUIDE.md
mv docs/SECURITY_HEADERS.md docs/operations/security/SECURITY_HEADERS.md
mv docs/SYSTEM_CONFIGURATION_ANALYSIS.md docs/operations/deployment/SYSTEM_CONFIG.md
```

### 3.4 Move Guide Files
```bash
# From root to guides/
mv docs/PATIENT_ONBOARDING_CONFIGURATION.md docs/guides/GETTING_STARTED.md
mv docs/QUICK_START_MIGRATIONS.md docs/guides/database/MIGRATIONS_QUICKSTART.md
mv docs/GIN_INDEX_MIGRATION_GUIDE.md docs/guides/database/DATA_MIGRATION_GUIDE.md
mv docs/PYTHON_313_UPGRADE.md docs/reference/PYTHON_313_MIGRATION.md
mv docs/CONFIG_ENDPOINT.md docs/reference/CONFIG_SCHEMA.md
mv docs/TROUBLESHOOTING_WELCOME_MESSAGE.md docs/guides/troubleshooting/COMMON_ISSUES.md
```

### 3.5 Move Archive Files (Migration Reports)
```bash
mkdir -p docs/archive/migration-reports

# Move all v2 migration reports
mv docs/analytics-migration-guide.md docs/archive/migration-reports/
mv docs/analytics-refactoring-report.md docs/archive/migration-reports/
mv docs/dashboard-v2-migration.md docs/archive/migration-reports/
mv docs/enhanced-messages-v2-migration-report.md docs/archive/migration-reports/
mv docs/ENHANCED_MONITORING_V2_MIGRATION_REPORT.md docs/archive/migration-reports/
mv docs/LOCALIZATION_V2_MIGRATION_COMPLETE.md docs/archive/migration-reports/
mv docs/PHYSICIAN_MANAGEMENT_V2_MIGRATION.md docs/archive/migration-reports/
mv docs/V2_TEMPLATES_MIGRATION_REPORT.md docs/archive/migration-reports/
mv docs/v2-platform-sync-migration.md docs/archive/migration-reports/
mv docs/CONSOLIDATION_EXECUTIVE_SUMMARY.md docs/archive/migration-reports/
mv docs/MIGRATION_AND_VALIDATION_SUMMARY.md docs/archive/migration-reports/
mv docs/api/v2/TASKS_MIGRATION.md docs/archive/migration-reports/
```

### 3.6 Move Archive Files (Phase Reports)
```bash
mkdir -p docs/archive/phase-reports

mv docs/QW-020-PHASE4-COMPLETE.md docs/archive/phase-reports/
mv docs/QW-020-PHASE4-SESSION-SUMMARY.md docs/archive/phase-reports/
mv docs/QW-020-PHASE4-SESSION2-SUMMARY.md docs/archive/phase-reports/
mv docs/QW-020-PHASE4-SESSION3-SUMMARY.md docs/archive/phase-reports/
mv docs/QW-020-PHASE4-TESTING-PROGRESS.md docs/archive/phase-reports/
mv docs/QW-020-PHASE5-DAY1-PROGRESS.md docs/archive/phase-reports/
mv docs/QW-020-TESTING-PLAN.md docs/archive/phase-reports/
mv docs/QW-020-TESTING-STATUS.md docs/archive/phase-reports/
```

### 3.7 Move Archive Files (Implementation & Bug Fixes)
```bash
mkdir -p docs/archive/{implementation-details,bug-fixes,quick-references,other}

# Implementation details
mv docs/EAGER_LOADING_IMPLEMENTATION_SUMMARY.md docs/archive/implementation-details/
mv docs/ERROR_HANDLING_INTEGRATION_SUMMARY.md docs/archive/implementation-details/
mv docs/GIN_INDEXES_IMPLEMENTATION_SUMMARY.md docs/archive/implementation-details/
mv docs/QUIZ_ALERT_EVALUATION_IMPLEMENTATION.md docs/archive/implementation-details/
mv docs/SPRINT_1_EAGER_LOADING_IMPLEMENTATION.md docs/archive/implementation-details/
mv docs/STAMP_PRODUCTION_DB_IMPLEMENTATION.md docs/archive/implementation-details/
mv docs/IMPLEMENTATION_PHYSICIAN_RISK_ASSESSMENT.md docs/archive/implementation-details/

# Quick references
mv docs/EAGER_LOADING_QUICK_REFERENCE.md docs/archive/quick-references/
mv docs/MIGRATION_QUICK_REFERENCE.md docs/archive/quick-references/
mv docs/QUIZ_ALERT_QUICK_REFERENCE.md docs/archive/quick-references/
mv docs/WEBHOOK_IDEMPOTENCY_QUICK_START.md docs/archive/quick-references/
mv docs/QUICK_START_PKG_RESOURCES_FIX.md docs/archive/quick-references/

# Bug fixes
mv docs/DASHBOARD_SCHEMA_FIXES_SUMMARY.md docs/archive/bug-fixes/
mv docs/DELIVERY_STATUS_FIX.md docs/archive/bug-fixes/
mv docs/PATIENTS_REDIRECT_FIX.md docs/archive/bug-fixes/
mv docs/PKG_RESOURCES_FIX.md docs/archive/bug-fixes/
mv docs/QUIZ_SESSION_ID_FIX.md docs/archive/bug-fixes/
mv docs/REFACTORING_DUPLICATE_INITIALIZATIONS.md docs/archive/bug-fixes/
mv docs/REMAINING_ROLE_FIXES_SUMMARY.md docs/archive/bug-fixes/
mv docs/SUPABASE_REMOVAL_FIX.md docs/archive/bug-fixes/
mv docs/TRAILING_SLASH_REDIRECT_FIX.md docs/archive/bug-fixes/
mv docs/VALIDATION_RULE_SCHEMA_FIX.md docs/archive/bug-fixes/
mv docs/WEBHOOK_ENDPOINT_FIX.md docs/archive/bug-fixes/

# Other/Miscellaneous
mv docs/BACKEND_TABLE_USAGE_AUDIT.md docs/archive/other/
mv docs/alerts_v2_safety_security_report.md docs/archive/other/
mv docs/RUNBOOK_QUIZ_METRICS.md docs/archive/other/
mv docs/UPGRADE_SUMMARY.md docs/archive/other/
mv docs/MIGRATIONS.md docs/archive/other/
```

### 3.8 Verify Migration
```bash
# Check file count
find docs -type f -name "*.md" | wc -l
# Should still be 88 (minus any consolidated files)

# List all moved files
find docs -type f -name "*.md" | sort > docs/_NEW_FILE_LIST.txt

# Check for any files left in root
ls -la docs/*.md | grep -v "^d" | grep -v "README"
```

---

## Phase 4: Link Updates (Days 4-5)

### 4.1 Update Main README.md
```bash
# Replace old README.md with new template from _NEW_STRUCTURE_PROPOSAL.md Part 3
# Or manually update key sections:
# - Update navigation links
# - Fix broken references
# - Update table of contents
```

### 4.2 Create Link Update Script
```python
#!/usr/bin/env python3
import re
from pathlib import Path

# Define old -> new link mappings
link_mapping = {
    'QUIZ_PUBLIC_API.md': 'api/v1/quiz.md',
    'RATE_LIMITING.md': 'api/RATE_LIMITING.md',
    'DEPLOYMENT_CONFIGURATION.md': 'operations/deployment/DEPLOYMENT_GUIDE.md',
    'MONITORING.md': 'operations/monitoring/MONITORING_GUIDE.md',
    # ... add all mappings
}

def update_links(file_path: Path):
    content = file_path.read_text()
    original = content

    for old, new in link_mapping.items():
        # Update [text](old.md) -> [text](new.md)
        pattern = rf'\](\({re.escape(old)}\))'
        replacement = f']({new})'
        content = re.sub(pattern, replacement, content)

    if content != original:
        file_path.write_text(content)
        return True
    return False

# Apply to all markdown files
docs_dir = Path('backend-hormonia/docs')
updated = 0
for md_file in docs_dir.glob('**/*.md'):
    if update_links(md_file):
        print(f"Updated: {md_file}")
        updated += 1

print(f"Total files updated: {updated}")
```

### 4.3 Run Link Updates
```bash
python update_links.py
```

### 4.4 Manual Link Review
```bash
# Search for any remaining broken links
grep -r "\[.*\](.*PHASE.*\.md)" docs/
grep -r "\[.*\](.*SESSION.*\.md)" docs/
grep -r "\[.*\](.*FIX\.md)" docs/ --include="*.md" | grep -v archive
```

---

## Phase 5: README Updates & Templates (Day 5)

### 5.1 Update Folder README Files
```bash
# guides/README.md
cat > docs/guides/README.md << 'EOF'
# Getting Started & How-To Guides

This folder contains practical guides for:
- Setting up local development
- Deploying to production
- Configuring security features
- Troubleshooting common issues

Start with [GETTING_STARTED.md](GETTING_STARTED.md)
EOF

# api/README.md
cat > docs/api/README.md << 'EOF'
# API Documentation

Complete REST API specifications:
- [Overview](OVERVIEW.md) - Architecture and design
- [Endpoints](v1/) - REST endpoint specifications
- [Webhooks](webhooks/) - Webhook integration guides
- [Upload API](upload/) - File upload specifications
- [Error Codes](errors/) - Error reference

See [RATE_LIMITING.md](RATE_LIMITING.md) for rate limiting policy.
EOF

# architecture/README.md
cat > docs/architecture/README.md << 'EOF'
# System Architecture & Design

Technical documentation of system design:
- [System Design](SYSTEM_DESIGN.md) - High-level architecture
- [Database](DATABASE/) - Schema, performance, patterns
- [Components](COMPONENTS/) - Individual system components
- [Design Patterns](PATTERNS/) - Common patterns used
- [Data Flow](DATA_FLOW.md) - Data flow through system

See [DOMAIN_ARCHITECTURE.md](DOMAIN_ARCHITECTURE.md) for DDD specifics.
EOF

# operations/README.md
cat > docs/operations/README.md << 'EOF'
# Operations & DevOps

Production operations documentation:
- [Deployment](deployment/) - Deployment procedures
- [Monitoring](monitoring/) - Monitoring and alerting
- [Security](security/) - Security operations
- [Scaling](scaling/) - Performance and scaling
- [Runbooks](runbooks/) - Operational runbooks

Start with [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
EOF

# reference/README.md
cat > docs/reference/README.md << 'EOF'
# Technical Reference

Quick reference materials:
- [Database Schema](DATABASE_SCHEMA.md)
- [Configuration Schema](CONFIG_SCHEMA.md)
- [Python 3.13 Migration](PYTHON_313_MIGRATION.md)
- [Glossary](GLOSSARY.md)
EOF

# archive/README.md
cat > docs/archive/README.md << 'EOF'
# Archived Documentation

This folder contains historical documentation:
- **migration-reports/** - V1→V2 upgrade migration reports
- **phase-reports/** - Phase completion reports
- **implementation-details/** - Feature implementation details
- **quick-references/** - Quick reference guides
- **bug-fixes/** - Bug fix and refactoring reports
- **other/** - Miscellaneous archived documents

These documents are preserved for historical reference only.
EOF
```

### 5.2 Create New Main README.md
Copy the template from Part 3 of `_NEW_STRUCTURE_PROPOSAL.md`

---

## Phase 6: Testing & Verification (Day 6)

### 6.1 Verify File Integrity
```bash
# Count files
find docs -type f -name "*.md" | wc -l

# Compare with backup
diff <(find docs/_backup_*/. -name "*.md" | sort) <(find docs -name "*.md" | grep -v _backup | sort)

# Check for orphaned files in root
ls -la docs/*.md | wc -l
# Should be: README.md + 3 proposal docs = 4 files
```

### 6.2 Test Documentation Links
```bash
# Search for broken links patterns
grep -r "\.md)" docs --include="*.md" | grep -v archive | grep -v "^Binary"

# Common broken patterns
grep -r "\[.*\](.*PHASE.*\.md)" docs/ --include="*.md" | grep -v archive
grep -r "\[.*\](\.\..*FIX\.md)" docs/ --include="*.md" | grep -v archive
grep -r "security/AUTHENTICATION_GUIDE" docs --include="*.md"  # Should have moved
```

### 6.3 Verify Content Integrity
```bash
# Sample random files to verify content wasn't corrupted
head -5 docs/api/v1/quiz.md
head -5 docs/architecture/DATABASE/SCHEMA.md
head -5 docs/operations/deployment/DEPLOYMENT_GUIDE.md
head -5 docs/archive/phase-reports/QW-020-PHASE4-COMPLETE.md
```

### 6.4 Documentation Search Test
```bash
# Verify docs can be found by search
find docs -type f -name "*.md" -exec grep -l "deployment\|monitoring\|security" {} \; | head -10
```

---

## Phase 7: Git Commit & Communication (Day 7)

### 7.1 Stage Changes
```bash
git add backend-hormonia/docs/
git status
```

### 7.2 Create Comprehensive Commit Message
```bash
git commit -m "refactor(docs): reorganize documentation into hierarchical structure

This commit reorganizes 88 documentation files from a flat structure into
a purpose-driven hierarchy:

STRUCTURE CHANGES:
- guides/: How-to guides and quick-starts (deployment, database, security)
- api/: API specs and endpoint documentation
- architecture/: System design and technical architecture
- operations/: Production operations and DevOps procedures
- reference/: Technical references and specifications
- archive/: Historical docs, migration reports, and phase reports

FILE MOVEMENT:
- Moved 85+ root-level files to appropriate folders
- Consolidated duplicate documentation (e.g., IDEMPOTENCY.md files)
- Updated all internal links and cross-references
- Created comprehensive README files for each folder

BENEFITS:
- Improved discoverability and navigation
- Clearer organization by purpose
- Easier maintenance and scaling
- Better onboarding experience
- Clear separation of active vs archived documentation

FILES MODIFIED:
- Created new folder structure (30+ subfolders)
- Updated all internal markdown links
- Created new main README.md with navigation
- Updated folder-level README.md files

Migration guide: docs/_NEW_STRUCTURE_PROPOSAL.md
File mapping: docs/FILE_CATEGORIZATION_REFERENCE.md

Closes #XXX (documentation issue)"
```

### 7.3 Create Pull Request
```bash
gh pr create \
  --title "refactor(docs): reorganize into hierarchical structure" \
  --body "See commit message for details. Key proposal in docs/_NEW_STRUCTURE_PROPOSAL.md"
```

### 7.4 Communicate Changes to Team
- Post message in team chat
- Link to PR and proposal document
- Explain benefits
- Ask for feedback
- Schedule brief walkthrough if needed

---

## Phase 8: Post-Migration (Optional Day 8+)

### 8.1 Update Team Documentation
- Update team wiki/handbook with new structure
- Share navigation guide
- Update any CI/CD that references doc paths

### 8.2 Setup Automated Linting (Optional)
```bash
# Create .markdownlint.json to enforce consistency
# Create pre-commit hook to check links
```

### 8.3 Schedule Regular Maintenance
- Monthly: Remove dead links
- Quarterly: Archive old docs (>6 months)
- Quarterly: Review organization
- Annually: Full structure review

---

## Troubleshooting

### Files Disappeared After Move
```bash
# Check backup
ls -la docs/_backup_*/
# Restore from backup
cp -r docs/_backup_*/* docs/
```

### Broken Links After Migration
```bash
# Find remaining broken links
grep -r "^\[.*\](.*\.md)" docs --include="*.md" | \
  grep -v "archive" | \
  cut -d: -f2 | \
  sort | uniq

# Update mapping and rerun link script
```

### Files Won't Move (Permission Issues)
```bash
# Check permissions
ls -la docs/FILENAME.md

# On Windows, try:
move "docs\FILENAME.md" "docs\newfolder\FILENAME.md"
```

---

## Success Criteria

Migration is complete when:
- [ ] All 88+ files are in correct new locations
- [ ] No files remain in root except README.md and proposal docs
- [ ] All internal links work (no 404s)
- [ ] All folder README.md files created
- [ ] Main README.md updated with new structure
- [ ] Git branch clean and ready for PR
- [ ] Team has been informed
- [ ] Changes merged to main branch

---

## Quick Reference Commands

```bash
# Setup
cd backend-hormonia/docs

# Create structure
mkdir -p {guides,api,architecture,operations,reference,archive}/{deployment,database,v1,webhooks,COMPONENTS,DATABASE,PATTERNS,monitoring,security,bug-fixes,other}

# Count files
find . -type f -name "*.md" | wc -l

# Find files in wrong location
find . -maxdepth 1 -type f -name "*.md" | grep -v README

# Verify structure
tree -d -L 2

# Test links
grep -r "\.md)" --include="*.md" | grep -v "^Binary"
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-12
**Status**: Ready to Execute
