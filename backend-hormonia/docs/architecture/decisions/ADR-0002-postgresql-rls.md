# ADR-0002: PostgreSQL with Row-Level Security for Multi-Tenancy

## Status

Accepted

Date: 2024-01-16

## Context

The Clínica Hormonia system manages sensitive medical data for multiple physicians and their patients. Requirements:
- **Data isolation**: Each physician can only access their own patients' data
- **HIPAA compliance**: Strong access controls and audit trails
- **Performance**: Efficient queries without complex application-level filtering
- **Scalability**: Support for 1000+ physicians and 100,000+ patients
- **Data integrity**: ACID transactions for critical medical operations
- **Audit requirements**: Track all data access and modifications
- **Compliance**: Meet healthcare data protection regulations

The database must provide both security at the database level and flexibility for complex medical data queries.

## Decision

We will use **PostgreSQL 15+ with Row-Level Security (RLS)** as the primary database, implementing multi-tenancy through RLS policies rather than application-level filtering.

Key implementation:
1. **RLS Policies**: Automatic row-level filtering based on user context
2. **SET LOCAL**: Session variables to set current user context
3. **Policies per table**: Different access rules for physicians, patients, admins
4. **Audit logging**: Trigger-based audit trails for all data modifications
5. **GIN indexes**: Fast JSONB queries for flexible medical metadata
6. **Partitioning**: Table partitioning for historical data

## Consequences

### Positive Consequences

- **Security by default**: Impossible to accidentally query other physicians' data
- **Database-level enforcement**: Security enforced even if application has bugs
- **Performance**: Database can optimize filtered queries better than application
- **Simplified code**: No need for complex WHERE clauses in every query
- **Audit compliance**: Built-in audit trail at database level
- **Flexibility**: Easy to add new access patterns via policies
- **JSONB support**: Store flexible medical metadata with fast queries
- **Reliability**: ACID guarantees for critical medical operations

### Negative Consequences

- **Complexity**: RLS policies can be difficult to debug
- **Migration overhead**: Existing queries need RLS context setup
- **Performance monitoring**: Need to monitor policy evaluation overhead
- **Testing complexity**: Tests must set proper context
- **Policy management**: Policies need careful review and maintenance

### Risks

- **Performance degradation**: Poorly written policies can slow queries
- **Policy conflicts**: Multiple policies could interact unexpectedly
- **Bypass risks**: Superuser accounts bypass RLS (must be protected)
- **Migration challenges**: Complex data migrations with RLS enabled
- **Developer confusion**: Team needs training on RLS patterns

## Alternatives Considered

### Alternative 1: Separate Database per Tenant

**Description**: Dedicated PostgreSQL database for each physician

**Pros**:
- Complete data isolation
- Easy to scale individual tenants
- Simple backup/restore per tenant
- No RLS complexity

**Cons**:
- Operational nightmare with 1000+ databases
- Expensive resource usage
- Difficult to run cross-tenant analytics
- Schema migrations become complex
- Connection pool management issues

**Why rejected**: Not scalable for our expected 1000+ physicians

### Alternative 2: Schema-Based Multi-Tenancy

**Description**: Separate PostgreSQL schema for each physician

**Pros**:
- Good data isolation
- Single database to manage
- Easier than separate databases

**Cons**:
- Still 1000+ schemas to manage
- Complex schema migrations
- Connection routing complexity
- No performance benefit over RLS
- Search path configuration issues

**Why rejected**: Similar complexity to RLS with fewer benefits

### Alternative 3: Application-Level Filtering

**Description**: Filter by physician_id in all application queries

**Pros**:
- Simple to understand
- No database-specific features
- Easy to test
- Framework agnostic

**Cons**:
- Easy to forget WHERE clause (security risk)
- No database-level enforcement
- Cannot leverage database optimizations
- Repeated code in every query
- Audit trail requires application logic

**Why rejected**: Too risky for HIPAA-compliant medical data

### Alternative 4: MongoDB (Document Database)

**Description**: Use document database with flexible schemas

**Pros**:
- Flexible schema for medical data
- Good for nested structures
- Horizontal scalability

**Cons**:
- No native RLS support
- Weaker ACID guarantees
- Less mature audit logging
- Complex transactions
- Team unfamiliar with MongoDB

**Why rejected**: ACID requirements and team expertise favor PostgreSQL

## Implementation Notes

### RLS Policy Structure

```sql
-- Enable RLS on patient table
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;

-- Policy for physicians to see only their patients
CREATE POLICY physician_isolation_policy ON patients
    FOR ALL
    TO authenticated_role
    USING (physician_id = current_setting('app.current_physician_id')::uuid)
    WITH CHECK (physician_id = current_setting('app.current_physician_id')::uuid);

-- Policy for admins to see all patients
CREATE POLICY admin_full_access_policy ON patients
    FOR ALL
    TO admin_role
    USING (true);
```

### Session Context Setup

```python
# Set RLS context in FastAPI middleware
async def set_rls_context(request: Request, call_next):
    physician_id = get_current_physician_id(request)
    async with db.begin():
        await db.execute(
            text(f"SET LOCAL app.current_physician_id = '{physician_id}'")
        )
        response = await call_next(request)
    return response
```

### Performance Optimization

1. **Indexes on RLS columns**: Index physician_id for fast filtering
2. **GIN indexes**: For JSONB metadata queries
3. **Partial indexes**: For status-based queries
4. **Materialized views**: For complex reporting
5. **Connection pooling**: PgBouncer for efficient connection management

### Migration Strategy

1. ✅ PostgreSQL 15+ deployed
2. ✅ RLS policies created for all tables
3. ✅ Audit triggers implemented
4. ✅ GIN indexes on JSONB columns
5. ✅ Middleware for session context setup
6. ✅ Integration tests with RLS context
7. 🔄 Performance monitoring dashboard
8. 🔄 Policy review process established

### Testing Approach

- Unit tests with explicit context setup
- Integration tests verify data isolation
- Performance tests for policy overhead
- Security tests attempt to bypass RLS
- Audit trail validation tests

## References

- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [RLS Best Practices](https://www.cybertec-postgresql.com/en/row-level-security-postgresql/)
- [Multi-Tenant Patterns](https://docs.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenancy-models)
- [HIPAA Database Requirements](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)

## Metadata

- **Author**: Database Architecture Team
- **Reviewers**: Security Team, Backend Team, Compliance Officer
- **Last Updated**: 2024-01-16
- **Related ADRs**: ADR-0001 (FastAPI), ADR-0009 (Clean Architecture), ADR-0010 (Security)
- **Tags**: database, security, multi-tenancy, compliance, postgresql
