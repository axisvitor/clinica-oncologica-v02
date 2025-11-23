# ADR-007: API Versioning Strategy

## Status
Accepted - Janeiro 2025

## Context

### Current State
- Only `/api/v2/` endpoints exist
- No formal versioning strategy or deprecation process
- Cannot safely evolve API without breaking existing integrations
- Multiple client types (web, mobile, WhatsApp bot)
- No tracking of deprecated endpoint usage

### Problems
1. **Breaking Changes Risk**: Any API change could break existing clients
2. **No Deprecation Process**: Cannot gracefully sunset old endpoints
3. **Client Migration**: No tools to help clients migrate between versions
4. **Usage Visibility**: No metrics on which API versions are being used
5. **Backward Compatibility**: Difficult to maintain multiple versions

## Decision

### 1. URL-Based Versioning

Use URL path versioning: `/api/v{major}/`

**Rationale:**
- ✅ **Clear and explicit**: Version is immediately visible in URL
- ✅ **Easy to route**: Simple FastAPI routing based on path prefix
- ✅ **Browser-friendly**: Can test endpoints directly in browser
- ✅ **Industry standard**: Used by Stripe, GitHub, AWS, Twilio
- ✅ **Cache-friendly**: Different URLs = different cache entries
- ✅ **Documentation clarity**: Easy to separate docs by version

**Example:**
```
/api/v2/patients
/api/v3/patients
```

**Alternatives Considered:**

| Method | Pros | Cons | Decision |
|--------|------|------|----------|
| Header-based (`Accept: application/vnd.clinica.v3+json`) | Clean URLs | Not browser-friendly | ❌ Rejected |
| Query param (`?version=3`) | Easy to add | Non-standard | ❌ Rejected |
| Custom header (`X-API-Version: 3`) | Flexible | Hidden from URL | ❌ Rejected |
| URL path (`/api/v3/`) | Clear, standard | URLs change | ✅ **Selected** |

### 2. Versioning Rules

#### Major Version (v2 → v3)

Increment major version when making **breaking changes**:

- ❌ Removing endpoints
- ❌ Removing request/response fields (required or optional)
- ❌ Changing field types (string → integer, date format changes)
- ❌ Changing authentication/authorization mechanisms
- ❌ Changing HTTP status code semantics
- ❌ Changing error response format
- ❌ Renaming fields
- ❌ Changing pagination mechanism
- ❌ Changing rate limiting rules significantly

**Example Breaking Change:**
```python
# v2 - Old
{
  "telefone": "+5511999999999"  # Field name in Portuguese
}

# v3 - New (BREAKING)
{
  "phone": "+5511999999999"  # Field renamed
}
```

#### Minor Changes (Non-Breaking)

Can be done within the **same version**:

- ✅ Adding new endpoints
- ✅ Adding **optional** fields to requests
- ✅ Adding fields to responses (clients should ignore unknown fields)
- ✅ Bug fixes that don't change behavior
- ✅ Performance improvements
- ✅ Adding new query parameters (optional)
- ✅ More permissive validation (accepting more formats)
- ✅ Deprecation warnings (headers)

**Example Non-Breaking Change:**
```python
# v3 - Original
{
  "patient_id": "123",
  "name": "João Silva"
}

# v3 - Enhanced (NON-BREAKING)
{
  "patient_id": "123",
  "name": "João Silva",
  "created_at": "2025-01-15T10:30:00Z"  # New field added
}
```

### 3. Deprecation Process

**Timeline: 6 months minimum**

#### Phase 1: Announce (Months 1-3)

**Actions:**
- Add `Sunset` header (RFC 8594) to all deprecated endpoints
- Add deprecation notice to API documentation
- Send email notifications to registered API clients
- Create migration guide with examples

**Example Response Headers:**
```http
HTTP/1.1 200 OK
Sunset: Wed, 01 Jul 2025 00:00:00 GMT
Deprecation: true
Link: </api/v3>; rel="successor-version"
X-API-Warn: API version v2 will be sunset in 152 days. Please migrate to v3.
```

#### Phase 2: Warn (Months 4-6)

**Actions:**
- Continue deprecation headers
- Log all usage of deprecated endpoints
- Dashboard showing deprecation usage by client
- Send monthly reminder emails to clients still using deprecated API
- Offer migration support/office hours

**Metrics Tracked:**
- Total calls to deprecated endpoints
- Unique clients using deprecated endpoints
- Most used deprecated endpoints
- Client migration progress

#### Phase 3: Sunset (Month 7+)

**Actions:**
- Remove deprecated version code
- Return **410 Gone** for all deprecated endpoints
- Redirect to migration guide

**Example Sunset Response:**
```json
{
  "error": {
    "code": "API_VERSION_SUNSET",
    "message": "API v2 was sunset on 2025-07-01. Please use v3.",
    "sunset_date": "2025-07-01T00:00:00Z",
    "current_version": "v3",
    "migration_guide": "https://api.clinica.com/docs/v2-to-v3"
  }
}
```

### 4. Version Support Policy

| Version | Status | Support Until | Notes |
|---------|--------|---------------|-------|
| v1 | ❌ Sunset | 2023-12-31 | Removed |
| v2 | ⚠️ Deprecated | 2025-07-01 | Use v3 |
| v3 | ✅ Current | TBD | Recommended |

**Support Commitment:**
- Minimum 6 months notice before sunset
- Security fixes for deprecated versions during notice period
- Critical bug fixes for deprecated versions (case-by-case)
- No new features in deprecated versions

### 5. Version Negotiation

Support multiple ways to specify version (fallback order):

1. **URL Path** (Primary): `/api/v3/patients`
2. **Accept Header**: `Accept: application/vnd.clinica.v3+json`
3. **Custom Header**: `X-API-Version: 3`
4. **Default**: Latest stable version (v3)

**Implementation Priority:**
- URL path takes precedence (most explicit)
- Header-based negotiation as fallback
- Default to latest when no version specified

## Consequences

### Positive

✅ **Client Safety**: Clients won't break unexpectedly from API changes
✅ **Graceful Migration**: 6+ months to migrate between versions
✅ **Clear Communication**: Headers and metrics show deprecation status
✅ **Business Continuity**: Multiple versions can coexist
✅ **Developer Experience**: Clear migration guides and timelines
✅ **Monitoring**: Metrics show which clients need to migrate

### Negative

❌ **Maintenance Burden**: Must maintain multiple API versions simultaneously
❌ **Code Duplication**: Some logic duplicated between versions
❌ **Testing Complexity**: Must test all supported versions
❌ **Documentation**: Must maintain docs for multiple versions

### Mitigation Strategies

**For Maintenance Burden:**
- Share common business logic between versions
- Use adapters/transformers for version-specific changes
- Limit to 2 active versions maximum (current + deprecated)

**For Code Duplication:**
- Version-specific routers, but shared services
- Use dependency injection for version-specific logic
- Extract common validation/transformation logic

**For Testing:**
- Automated compatibility tests
- Version-specific test suites
- Contract tests between versions

## Implementation Plan

### Phase 1: Infrastructure (Week 1)
- ✅ Create `VersionedRouter` class
- ✅ Implement deprecation header middleware
- ✅ Setup Prometheus metrics for version tracking
- ✅ Create Grafana dashboard

### Phase 2: v3 API (Weeks 2-3)
- ✅ Define v3 API structure
- ✅ Implement v3 endpoints (starting with patients, quiz)
- ✅ Create v3 schemas/models
- ✅ Write migration guide

### Phase 3: Deprecation Tooling (Week 4)
- ✅ Implement automated email notifications
- ✅ Create client migration dashboard
- ✅ Setup deprecation tracking
- ✅ Write compatibility tests

### Phase 4: Documentation (Week 4)
- ✅ Update OpenAPI spec with versions
- ✅ Create migration guide (v2 → v3)
- ✅ Document versioning policy
- ✅ Client communication templates

## Metrics & Monitoring

### Key Metrics

1. **Version Distribution**
   - `api_version_usage_total{version="v2|v3"}`
   - Track: Which versions are being used

2. **Deprecated Endpoint Calls**
   - `api_deprecated_endpoint_calls_total{version, endpoint, client_id}`
   - Track: Who is still using deprecated APIs

3. **Client Migration Progress**
   - `api_clients_migrated{from_version, to_version}`
   - Track: How many clients have migrated

4. **Days Until Sunset**
   - `api_version_sunset_days_remaining{version}`
   - Track: Time remaining for deprecated versions

### Alerts

```yaml
- alert: DeprecatedAPIHighUsage
  expr: rate(api_deprecated_endpoint_calls_total[5m]) > 100
  for: 1h
  annotations:
    summary: "High usage of deprecated API v2"
    description: "Still receiving >100 req/min on deprecated v2"

- alert: DeprecationSunsetApproaching
  expr: api_version_sunset_days_remaining{version="v2"} < 30
  annotations:
    summary: "API v2 sunset in <30 days"
    description: "Check client migration status"
```

## References

- [RFC 8594 - Sunset HTTP Header](https://www.rfc-editor.org/rfc/rfc8594)
- [Stripe API Versioning](https://stripe.com/docs/api/versioning)
- [GitHub API Versioning](https://docs.github.com/en/rest/overview/api-versions)
- [Semantic Versioning](https://semver.org/)

## Related ADRs

- ADR-001: API Design Principles
- ADR-003: Error Handling Strategy
- ADR-006: API Rate Limiting

## Approval

- **Architect:** ✅ Approved
- **Backend Lead:** ✅ Approved
- **DevOps:** ✅ Approved
- **Date:** 2025-01-16
