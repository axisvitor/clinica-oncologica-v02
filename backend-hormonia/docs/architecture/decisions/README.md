# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the Clínica Hormonia project.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## Why ADRs?

- **Knowledge preservation**: Capture the rationale behind decisions
- **Onboarding**: Help new team members understand why things are the way they are
- **Decision review**: Enable re-evaluation of past decisions
- **Compliance**: Document technical decisions for audits
- **Communication**: Share architectural thinking across the team

## ADR Index

### Active ADRs

| ADR | Title | Date | Status | Tags |
|-----|-------|------|--------|------|
| [ADR-0001](./ADR-0001-fastapi-framework.md) | FastAPI as Backend Framework | 2024-01-15 | Accepted | backend, framework, async |
| [ADR-0002](./ADR-0002-postgresql-rls.md) | PostgreSQL with Row-Level Security | 2024-01-16 | Accepted | database, security, multi-tenancy |
| [ADR-0003](./ADR-0003-redis-caching.md) | Redis for Caching and Rate Limiting | 2024-01-17 | Accepted | caching, performance, redis |
| [ADR-0004](./ADR-0004-celery-background-tasks.md) | Celery + Beat for Background Tasks | 2024-01-18 | Accepted | async, background-tasks, celery |
| [ADR-0005](./ADR-0005-evolution-api-whatsapp.md) | Evolution API for WhatsApp Integration | 2024-01-19 | Accepted | integration, whatsapp, messaging |
| [ADR-0006](./ADR-0006-firebase-authentication.md) | Firebase Admin SDK for Authentication | 2024-01-20 | Accepted | security, authentication, firebase |
| [ADR-0007](./ADR-0007-sparc-methodology.md) | SPARC Methodology for Development | 2024-01-21 | Accepted | methodology, process, tdd |
| [ADR-0008](./ADR-0008-hive-mind-coordination.md) | Hive Mind for Agent Coordination | 2024-01-22 | Accepted | ai, agents, coordination |
| [ADR-0009](./ADR-0009-clean-architecture.md) | Clean Architecture with Layered Separation | 2024-01-23 | Accepted | architecture, clean-architecture |
| [ADR-0010](./ADR-0010-multi-layer-security.md) | Multi-Layer Security Scanning (7 Layers) | 2024-01-24 | Accepted | security, compliance, scanning |

### Template

- [ADR-0000](./ADR-0000-template.md) - Template for new ADRs

## ADRs by Category

### Backend & Infrastructure
- ADR-0001: FastAPI Framework
- ADR-0002: PostgreSQL with RLS
- ADR-0003: Redis Caching
- ADR-0004: Celery Background Tasks

### Security & Compliance
- ADR-0006: Firebase Authentication
- ADR-0010: Multi-Layer Security Scanning

### Integration & External Services
- ADR-0005: Evolution API (WhatsApp)

### Development Process
- ADR-0007: SPARC Methodology
- ADR-0008: Hive Mind Coordination

### Architecture & Design
- ADR-0009: Clean Architecture

## ADR Lifecycle

### Status Values

- **Proposed**: Under discussion, not yet accepted
- **Accepted**: Decision made and being implemented
- **Rejected**: Considered but not chosen
- **Deprecated**: No longer relevant (replaced by newer decision)
- **Superseded**: Replaced by a newer ADR (link to replacement)

### Creating a New ADR

1. Copy the template:
   ```bash
   ./scripts/adr/new-adr.sh "Your Decision Title"
   ```

2. Fill in all sections of the ADR:
   - Context: Why is this decision needed?
   - Decision: What did we decide?
   - Consequences: What are the trade-offs?
   - Alternatives: What else did we consider?

3. Review with team and stakeholders

4. Update status to "Accepted" when approved

5. Add to index table above

### Modifying an Existing ADR

**Don't modify accepted ADRs**. Instead:

1. If the decision needs to change, create a new ADR that supersedes the old one
2. Update the old ADR's status to "Superseded" with a link to the new one
3. Document why the decision changed in the new ADR's context

### Reviewing ADRs

ADRs should be reviewed:
- When onboarding new team members
- Before making major architectural changes
- Quarterly to ensure they're still relevant
- When compliance/audit requirements change

## Scripts

Automation scripts are available in `/scripts/adr/`:

- `new-adr.sh`: Create a new ADR from template
- `validate-adr.py`: Validate ADR format and completeness
- `generate-index.py`: Auto-generate this README index

## Best Practices

### Writing Good ADRs

1. **Be specific**: "Use PostgreSQL 15+" not "Use a database"
2. **Explain context**: Why is this decision needed now?
3. **Show trade-offs**: Every decision has pros and cons
4. **Consider alternatives**: Show you evaluated options
5. **Keep it concise**: Aim for 1-2 pages per ADR
6. **Use clear language**: Write for developers joining in 2 years

### When to Create an ADR

Create an ADR when making decisions about:
- Technology choices (frameworks, databases, tools)
- Architecture patterns (layering, service boundaries)
- Development processes (testing, deployment, workflows)
- Security and compliance approaches
- Integration strategies with external systems

### When NOT to Create an ADR

Don't create ADRs for:
- Implementation details within a component
- Temporary workarounds or experiments
- Decisions that can be easily changed
- Standard industry practices (e.g., "use git for version control")

## Related Documentation

- [System Architecture Overview](../README.md)
- [API Documentation](../../api/README.md)
- [Development Guide](../../guides/README.md)
- [Operations Guide](../../operations/README.md)

## References

- [ADR GitHub Organization](https://adr.github.io/)
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [Architecture Decision Records (ThoughtWorks)](https://www.thoughtworks.com/radar/techniques/lightweight-architecture-decision-records)

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2024-01-24 | Added ADR-0010 (Multi-Layer Security) | Security Team |
| 2024-01-23 | Added ADR-0009 (Clean Architecture) | Architecture Team |
| 2024-01-22 | Added ADR-0008 (Hive Mind) | AI Engineering Team |
| 2024-01-21 | Added ADR-0007 (SPARC) | Engineering Leadership |
| 2024-01-20 | Added ADR-0006 (Firebase Auth) | Security Team |
| 2024-01-19 | Added ADR-0005 (Evolution API) | Integration Team |
| 2024-01-18 | Added ADR-0004 (Celery) | Backend Team |
| 2024-01-17 | Added ADR-0003 (Redis) | Infrastructure Team |
| 2024-01-16 | Added ADR-0002 (PostgreSQL RLS) | Database Team |
| 2024-01-15 | Added ADR-0001 (FastAPI) | Backend Team |
| 2024-01-15 | Initial ADR structure and template | Architecture Team |

---

**Maintainer**: Architecture Team
**Last Updated**: 2024-01-24
**Next Review**: 2024-04-24 (quarterly)
