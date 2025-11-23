# Rate Limiter Fix - Complete Endpoint List

All 17 endpoints have been fixed with `http_request: Request` parameter.

## File: `app/api/v2/ab_testing.py` (8 endpoints)

| # | Method | Endpoint | Function | Rate Limit | Line |
|---|--------|----------|----------|------------|------|
| 1 | POST | `/api/v2/ab-testing/experiments` | `create_experiment` | RATE_LIMIT_WRITE | 560 |
| 2 | PATCH | `/api/v2/ab-testing/experiments/{experiment_id}` | `update_experiment` | RATE_LIMIT_WRITE | 625 |
| 3 | POST | `/api/v2/ab-testing/experiments/{experiment_id}/control` | `control_experiment` | RATE_LIMIT_WRITE | 693 |
| 4 | POST | `/api/v2/ab-testing/experiments/{experiment_id}/assign` | `assign_variant` | RATE_LIMIT_WRITE | 797 |
| 5 | POST | `/api/v2/ab-testing/conversions` | `track_conversion` | RATE_LIMIT_WRITE | 919 |
| 6 | POST | `/api/v2/ab-testing/experiments/{experiment_id}/winner` | `declare_winner` | RATE_LIMIT_WRITE | 1169 |
| 7 | POST | `/api/v2/ab-testing/experiments/{experiment_id}/export` | `export_experiment_data` | RATE_LIMIT_WRITE | 1428 |
| 8 | POST | `/api/v2/ab-testing/sample-size` | `calculate_sample_size` | RATE_LIMIT_ANALYSIS | 1543 |

## File: `app/api/v2/enhanced_reports.py` (9 endpoints)

| # | Method | Endpoint | Function | Rate Limit | Line |
|---|--------|----------|----------|------------|------|
| 9 | POST | `/api/v2/enhanced-reports/builder` | `build_custom_report` | RATE_LIMIT_STANDARD | 218 |
| 10 | POST | `/api/v2/enhanced-reports/visualizations` | `create_visualization` | RATE_LIMIT_STANDARD | 424 |
| 11 | POST | `/api/v2/enhanced-reports/delivery/schedule` | `create_delivery_schedule` | RATE_LIMIT_HEAVY | 585 |
| 12 | POST | `/api/v2/enhanced-reports/share` | `share_report` | RATE_LIMIT_STANDARD | 750 |
| 13 | POST | `/api/v2/enhanced-reports/public-link` | `create_public_link` | RATE_LIMIT_HEAVY | 801 |
| 14 | POST | `/api/v2/enhanced-reports/export/multi` | `export_multi_format` | RATE_LIMIT_EXPORT | 904 |
| 15 | POST | `/api/v2/enhanced-reports/versions/{report_id}/restore` | `restore_report_version` | RATE_LIMIT_HEAVY | 1130 |
| 16 | POST | `/api/v2/enhanced-reports/dashboards` | `create_dashboard` | RATE_LIMIT_STANDARD | 1183 |
| 17 | POST | `/api/v2/enhanced-reports/dashboards/{dashboard_id}/snapshot` | `create_dashboard_snapshot` | RATE_LIMIT_STANDARD | 1338 |

## Rate Limit Definitions

From `app/api/v2/ab_testing.py` and `app/api/v2/enhanced_reports.py`:

```python
# A/B Testing
RATE_LIMIT_READ = "60/minute"
RATE_LIMIT_WRITE = "30/minute"
RATE_LIMIT_ANALYSIS = "15/minute"

# Enhanced Reports
RATE_LIMIT_STANDARD = "60/minute"
RATE_LIMIT_HEAVY = "10/minute"
RATE_LIMIT_EXPORT = "5/minute"
```

## Testing Each Endpoint

```bash
# Test rate limiting (should return 429 after limit)
export TOKEN="your_auth_token"
export BASE_URL="http://localhost:8000"

# A/B Testing endpoints
curl -X POST "$BASE_URL/api/v2/ab-testing/experiments" -H "Authorization: Bearer $TOKEN"
curl -X PATCH "$BASE_URL/api/v2/ab-testing/experiments/{id}" -H "Authorization: Bearer $TOKEN"
# ... repeat for all endpoints

# Enhanced Reports endpoints
curl -X POST "$BASE_URL/api/v2/enhanced-reports/builder" -H "Authorization: Bearer $TOKEN"
curl -X POST "$BASE_URL/api/v2/enhanced-reports/visualizations" -H "Authorization: Bearer $TOKEN"
# ... repeat for all endpoints
```

## Verification

All endpoints now have:
1. ✅ `http_request: Request` parameter
2. ✅ Schema parameter renamed to `data`
3. ✅ All references updated in function body
4. ✅ Rate limiting functional

---

**Total**: 17 endpoints fixed across 2 files
