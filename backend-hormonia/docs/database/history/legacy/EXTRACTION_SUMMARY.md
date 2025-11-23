# Database Extraction Summary

**Date:** 2025-11-18
**Source:** PostgreSQL AWS RDS
**Status:** ✅ Successful

## Overview

This document summarizes the results of the complete database schema extraction performed on November 18, 2025.

### Key Statistics

- **Total Tables:** 47
- **Total Relationships:** 57
- **User-Defined Types:** 14
- **Total Columns:** 594
- **Total Indexes:** 260

## Core Architecture Findings

The analysis identified **5 core tables** that form the backbone of the system:

1. **`patients`** (Referenced by 15 tables)
2. **`users`** (Referenced by 15 tables)
3. **`admin_users`** (Referenced by 9 tables)
4. **`flow_template_versions`** (Referenced by 5 tables)
5. **`quiz_templates`** (Referenced by 3 tables)

## Documentation Updates

The following documentation artifacts have been regenerated:

- **[SCHEMA_DOCUMENTATION.md](../../../reference/SCHEMA_DOCUMENTATION.md)**: Comprehensive human-readable documentation.
- **[TABLES_REFERENCE.md](../../../reference/TABLES_REFERENCE.md)**: Detailed column-level reference.
- **[complete_schema.json](../../../reference/complete_schema.json)**: Machine-readable schema definition.
- **[schema_analysis.json](../../../reference/schema_analysis.json)**: Complexity and relationship analysis.
- **[schema_diagram.mmd](../../../reference/schema_diagram.mmd)**: Updated ER diagram.

## Complexity Analysis

The system shows a healthy distribution of complexity:
- **High Complexity:** `admin_users`, `audit_logs`, `admin_audit_log` (Due to security/audit requirements)
- **Medium Complexity:** `patients`, `appointments`, `messages`
- **Low Complexity:** Lookup tables and simple join tables

## Recommendations

1. **Regular Extraction:** Schedule this extraction process to run weekly to keep documentation in sync.
2. **Schema Monitoring:** Monitor the growth of `audit_logs` and `messages` tables as they have high write volumes.
3. **Index Optimization:** Review indexes on `messages` table (18 indexes) to ensure write performance is not degraded.
