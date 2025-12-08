# ADR-0001: FastAPI as Backend Framework

## Status

Accepted

Date: 2024-01-15

## Context

The Clínica Hormonia oncology management system requires a modern, high-performance backend framework to support:
- Complex async operations for WhatsApp integration, email notifications, and background tasks
- RESTful API with automatic OpenAPI documentation
- Strong type safety and validation for medical data
- High concurrency for handling multiple patient interactions simultaneously
- Easy integration with PostgreSQL, Redis, and Celery
- Python 3.13+ compatibility for latest performance improvements

The framework must support HIPAA compliance requirements and provide robust security features out of the box.

## Decision

We will use **FastAPI** as the primary backend framework for the Clínica Hormonia system.

Key reasons:
1. **Native async/await support**: Critical for handling concurrent WhatsApp messages, email notifications, and database operations
2. **Automatic validation**: Pydantic models ensure data integrity for sensitive medical information
3. **Auto-generated documentation**: OpenAPI/Swagger UI for API consumers
4. **Type safety**: Python type hints provide compile-time checks and IDE support
5. **Performance**: One of the fastest Python frameworks (comparable to NodeJS)
6. **Modern Python**: Full support for Python 3.13+ features
7. **Dependency injection**: Clean separation of concerns and testability
8. **Active ecosystem**: Strong community and extensive third-party integrations

## Consequences

### Positive Consequences

- **Developer productivity**: Reduced boilerplate code and automatic validation
- **API documentation**: Always up-to-date OpenAPI specs
- **Type safety**: Fewer runtime errors in production
- **Performance**: Can handle 10,000+ requests/second with proper optimization
- **Testing**: Built-in test client and dependency override mechanisms
- **Security**: Built-in OAuth2, JWT, and CORS support
- **Async operations**: Efficient handling of I/O-bound operations (database, external APIs)

### Negative Consequences

- **Learning curve**: Team needs to understand async/await patterns
- **Async complexity**: Potential for async-related bugs if not careful
- **Less mature**: Younger than Django/Flask (though rapidly evolving)
- **ORM integration**: Not as tight as Django ORM (using SQLAlchemy instead)

### Risks

- **Breaking changes**: FastAPI is still evolving (currently 0.x versions)
- **Dependency on Pydantic**: Major Pydantic updates could require refactoring
- **Async gotchas**: Blocking operations in async contexts can degrade performance
- **Community size**: Smaller than Django, though growing rapidly

## Alternatives Considered

### Alternative 1: Django + Django REST Framework

**Description**: Traditional Django with DRF for API development

**Pros**:
- Mature ecosystem with extensive packages
- Built-in admin panel
- Excellent ORM
- Large community and extensive documentation
- Battle-tested in production

**Cons**:
- Synchronous by default (Django 4.x async support is limited)
- More boilerplate code for APIs
- Heavier framework with features we don't need
- Slower performance for high-concurrency scenarios

**Why rejected**: Synchronous architecture doesn't align with our async-heavy requirements (WhatsApp webhooks, background tasks, real-time notifications)

### Alternative 2: Flask + Extensions

**Description**: Lightweight Flask with extensions for REST, validation, etc.

**Pros**:
- Lightweight and flexible
- Large ecosystem of extensions
- Easy to learn
- Good for microservices

**Cons**:
- No built-in async support
- Requires many extensions for features FastAPI includes
- Manual OpenAPI documentation
- Less type safety without additional tooling
- More boilerplate for validation

**Why rejected**: Lacks native async support and requires too many extensions to match FastAPI's feature set

### Alternative 3: Sanic

**Description**: Async Python web framework focused on speed

**Pros**:
- True async/await support
- Very fast performance
- Similar syntax to Flask

**Cons**:
- Smaller community
- Less mature ecosystem
- No automatic validation or documentation
- Fewer integrations
- Less type safety

**Why rejected**: Lacks automatic validation, documentation, and has smaller ecosystem compared to FastAPI

## Implementation Notes

### Migration Path

1. ✅ Core FastAPI application structure implemented
2. ✅ Pydantic models for all data validation
3. ✅ SQLAlchemy 2.0 with async support
4. ✅ Alembic for database migrations
5. ✅ Background tasks with Celery integration
6. ✅ Authentication with Firebase Admin SDK
7. ✅ OpenAPI documentation at `/docs` and `/redoc`

### Testing Strategy

- Use FastAPI's TestClient for endpoint testing
- pytest-asyncio for async test functions
- Mock external services (WhatsApp, email)
- Integration tests with test database

### Performance Optimization

- Use async database drivers (asyncpg)
- Connection pooling for PostgreSQL
- Redis caching for frequently accessed data
- Background tasks for non-critical operations
- Proper async context management

## References

- [FastAPI Official Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Python Async/Await Guide](https://docs.python.org/3/library/asyncio.html)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)

## Metadata

- **Author**: System Architecture Team
- **Reviewers**: Backend Team, Security Team
- **Last Updated**: 2024-01-15
- **Related ADRs**: ADR-0002 (PostgreSQL), ADR-0003 (Redis), ADR-0004 (Celery)
- **Tags**: backend, framework, performance, async
