# ADR-0009: Clean Architecture with Layered Separation

## Status

Accepted

Date: 2024-01-23

## Context

The Clínica Hormonia system requires a maintainable architecture that can:
- **Scale independently**: Different layers can evolve separately
- **Support testing**: Easy to test business logic without infrastructure
- **Enable migrations**: Switch databases or frameworks without rewriting logic
- **Maintain clarity**: Clear separation of concerns
- **Support team growth**: Multiple developers can work on different layers
- **Comply with regulations**: HIPAA requires audit trails and data isolation

Current challenges:
- Growing codebase complexity (20,000+ lines)
- Multiple external integrations (WhatsApp, Firebase, Email)
- Business logic mixed with infrastructure code
- Difficult to test without database
- Framework coupling makes upgrades risky

We need an architecture that:
- Separates business rules from infrastructure
- Makes dependencies explicit and unidirectional
- Enables testing without external services
- Supports gradual refactoring
- Aligns with Python best practices

## Decision

We will adopt **Clean Architecture** with a layered approach, organized into four main layers:

1. **Domain Layer** (Innermost)
   - Business entities and rules
   - Domain events
   - Value objects
   - No external dependencies

2. **Application Layer**
   - Use cases / application services
   - DTOs and interfaces
   - Orchestrates domain objects
   - Depends only on domain layer

3. **Infrastructure Layer**
   - Database access (repositories)
   - External APIs (WhatsApp, Firebase)
   - File system, email, caching
   - Implements interfaces from application layer

4. **Presentation Layer** (Outermost)
   - REST API endpoints (FastAPI)
   - Request/response models (Pydantic)
   - Authentication middleware
   - Depends on application layer

## Consequences

### Positive Consequences

- **Testability**: Business logic testable without database
- **Maintainability**: Clear separation of concerns
- **Flexibility**: Easy to swap implementations (e.g., PostgreSQL → MySQL)
- **Independent development**: Teams can work on different layers
- **Framework independence**: Business logic not tied to FastAPI
- **Clear dependencies**: Dependency inversion principle enforced
- **Domain-driven**: Business logic is the center of attention
- **Gradual migration**: Can refactor incrementally

### Negative Consequences

- **Initial complexity**: More files and abstractions
- **Learning curve**: Team needs to understand architecture
- **Boilerplate**: More interfaces and DTOs
- **Over-engineering risk**: Simple features become complex
- **Migration effort**: Existing code needs refactoring

### Risks

- **Performance overhead**: Extra layers could add latency
- **Abstraction fatigue**: Developers might bypass architecture
- **Incomplete migration**: Mixed old/new patterns create confusion
- **Testing gaps**: Integration tests still needed despite unit tests
- **Documentation burden**: Need to maintain architecture docs

## Alternatives Considered

### Alternative 1: Django-style Monolithic MVC

**Description**: Models, Views, Controllers in single layer

**Pros**:
- Simple and familiar
- Fast development for small projects
- Less boilerplate
- Good Django ORM

**Cons**:
- Business logic mixed with framework
- Hard to test without database
- Framework coupling
- Difficult to scale architecture
- Not FastAPI-compatible

**Why rejected**: Too coupled to framework, hard to test business logic

### Alternative 2: Microservices from Day 1

**Description**: Split into separate services immediately

**Pros**:
- Independent scaling
- Technology diversity
- Clear service boundaries

**Cons**:
- Premature optimization
- Operational complexity
- Distributed transactions
- Higher latency
- More infrastructure cost

**Why rejected**: Over-engineering for current scale

### Alternative 3: Transaction Script Pattern

**Description**: Each endpoint has its own procedure

**Pros**:
- Very simple
- Direct and explicit
- Easy to understand
- Low overhead

**Cons**:
- Code duplication
- No business object modeling
- Procedural, not object-oriented
- Hard to maintain as complexity grows

**Why rejected**: Doesn't scale to our domain complexity

### Alternative 4: Hexagonal Architecture (Ports & Adapters)

**Description**: Similar to Clean Architecture, but different terminology

**Pros**:
- Similar benefits to Clean Architecture
- Well-documented pattern
- Explicit ports and adapters

**Cons**:
- Same complexity as Clean Architecture
- Less Python community adoption
- Different terminology than our team knows

**Why rejected**: Clean Architecture more familiar to team

## Implementation Notes

### Directory Structure

```
backend-hormonia/
├── app/
│   ├── domain/                # Domain Layer (Pure business logic)
│   │   ├── entities/          # Business entities
│   │   │   ├── patient.py
│   │   │   ├── quiz.py
│   │   │   └── physician.py
│   │   ├── value_objects/     # Immutable value objects
│   │   │   ├── email.py
│   │   │   └── phone_number.py
│   │   ├── events/            # Domain events
│   │   │   └── quiz_completed.py
│   │   └── exceptions/        # Domain-specific exceptions
│   │       └── business_rules.py
│   │
│   ├── application/           # Application Layer (Use cases)
│   │   ├── use_cases/         # Application services
│   │   │   ├── create_patient.py
│   │   │   ├── send_quiz.py
│   │   │   └── generate_report.py
│   │   ├── interfaces/        # Repository and service interfaces
│   │   │   ├── patient_repository.py
│   │   │   └── email_service.py
│   │   └── dtos/              # Data transfer objects
│   │       ├── patient_dto.py
│   │       └── quiz_dto.py
│   │
│   ├── infrastructure/        # Infrastructure Layer
│   │   ├── database/          # Database implementations
│   │   │   ├── repositories/  # Repository implementations
│   │   │   │   ├── patient_repository_impl.py
│   │   │   │   └── quiz_repository_impl.py
│   │   │   └── models/        # SQLAlchemy models
│   │   │       ├── patient_model.py
│   │   │       └── quiz_model.py
│   │   ├── external/          # External service implementations
│   │   │   ├── email_service_impl.py
│   │   │   ├── whatsapp_service_impl.py
│   │   │   └── firebase_service_impl.py
│   │   ├── cache/             # Caching implementations
│   │   │   └── redis_cache.py
│   │   └── messaging/         # Message queue implementations
│   │       └── celery_tasks.py
│   │
│   └── api/                   # Presentation Layer (FastAPI)
│       ├── v2/                # API version 2
│       │   ├── endpoints/     # Route handlers
│       │   │   ├── patients.py
│       │   │   └── quizzes.py
│       │   ├── schemas/       # Pydantic request/response models
│       │   │   ├── patient_schema.py
│       │   │   └── quiz_schema.py
│       │   └── dependencies/  # FastAPI dependencies
│       │       └── auth.py
│       └── middleware/        # HTTP middleware
│           ├── auth.py
│           └── logging.py
```

### Domain Entity Example

```python
# app/domain/entities/patient.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.domain.value_objects.email import Email
from app.domain.value_objects.phone_number import PhoneNumber
from app.domain.exceptions import BusinessRuleViolation

@dataclass
class Patient:
    """Pure domain entity - no infrastructure dependencies"""

    id: UUID
    physician_id: UUID
    full_name: str
    email: Email
    phone: PhoneNumber
    created_at: datetime
    last_quiz_date: Optional[datetime] = None

    def can_receive_quiz(self) -> bool:
        """Business rule: Patient can receive quiz if 30 days passed"""
        if not self.last_quiz_date:
            return True

        days_since_last_quiz = (now_sao_paulo() - self.last_quiz_date).days
        return days_since_last_quiz >= 30

    def mark_quiz_sent(self) -> None:
        """Update last quiz date"""
        if not self.can_receive_quiz():
            raise BusinessRuleViolation(
                f"Patient {self.id} received quiz less than 30 days ago"
            )
        self.last_quiz_date = now_sao_paulo()
```

### Use Case Example

```python
# app/application/use_cases/send_quiz_to_patient.py
from dataclasses import dataclass
from uuid import UUID

from app.application.interfaces.patient_repository import PatientRepository
from app.application.interfaces.quiz_repository import QuizRepository
from app.application.interfaces.whatsapp_service import WhatsAppService
from app.domain.exceptions import BusinessRuleViolation

@dataclass
class SendQuizToPatientRequest:
    patient_id: UUID
    quiz_template_id: UUID

@dataclass
class SendQuizToPatientResponse:
    quiz_id: UUID
    sent_at: datetime
    status: str

class SendQuizToPatientUseCase:
    """Application service - orchestrates domain objects and infrastructure"""

    def __init__(
        self,
        patient_repo: PatientRepository,
        quiz_repo: QuizRepository,
        whatsapp_service: WhatsAppService
    ):
        self.patient_repo = patient_repo
        self.quiz_repo = quiz_repo
        self.whatsapp_service = whatsapp_service

    async def execute(
        self, request: SendQuizToPatientRequest
    ) -> SendQuizToPatientResponse:
        # Load domain objects
        patient = await self.patient_repo.get_by_id(request.patient_id)
        template = await self.quiz_repo.get_template(request.quiz_template_id)

        # Execute business rule
        if not patient.can_receive_quiz():
            raise BusinessRuleViolation("Patient cannot receive quiz yet")

        # Create quiz instance
        quiz = template.create_instance_for_patient(patient)

        # Update patient state
        patient.mark_quiz_sent()

        # Persist changes
        await self.quiz_repo.save(quiz)
        await self.patient_repo.update(patient)

        # Send notification (infrastructure)
        await self.whatsapp_service.send_quiz_link(
            phone=patient.phone,
            quiz_url=quiz.access_url
        )

        return SendQuizToPatientResponse(
            quiz_id=quiz.id,
            sent_at=now_sao_paulo(),
            status="sent"
        )
```

### Repository Interface and Implementation

```python
# app/application/interfaces/patient_repository.py
from abc import ABC, abstractmethod
from uuid import UUID
from typing import List, Optional

from app.domain.entities.patient import Patient

class PatientRepository(ABC):
    """Repository interface - defined in application layer"""

    @abstractmethod
    async def get_by_id(self, patient_id: UUID) -> Optional[Patient]:
        pass

    @abstractmethod
    async def find_by_physician(self, physician_id: UUID) -> List[Patient]:
        pass

    @abstractmethod
    async def save(self, patient: Patient) -> None:
        pass

    @abstractmethod
    async def update(self, patient: Patient) -> None:
        pass

# app/infrastructure/database/repositories/patient_repository_impl.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.interfaces.patient_repository import PatientRepository
from app.domain.entities.patient import Patient
from app.infrastructure.database.models.patient_model import PatientModel

class SQLAlchemyPatientRepository(PatientRepository):
    """Repository implementation - in infrastructure layer"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, patient_id: UUID) -> Optional[Patient]:
        result = await self.session.execute(
            select(PatientModel).where(PatientModel.id == patient_id)
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    def _to_entity(self, model: PatientModel) -> Patient:
        """Convert ORM model to domain entity"""
        return Patient(
            id=model.id,
            physician_id=model.physician_id,
            full_name=model.full_name,
            email=Email(model.email),
            phone=PhoneNumber(model.phone),
            created_at=model.created_at,
            last_quiz_date=model.last_quiz_date
        )
```

### API Endpoint Example

```python
# app/api/v2/endpoints/quizzes.py
from fastapi import APIRouter, Depends
from uuid import UUID

from app.application.use_cases.send_quiz_to_patient import (
    SendQuizToPatientUseCase,
    SendQuizToPatientRequest
)
from app.api.v2.schemas.quiz_schema import SendQuizRequest, SendQuizResponse
from app.api.v2.dependencies.use_cases import get_send_quiz_use_case

router = APIRouter(prefix="/quizzes", tags=["quizzes"])

@router.post("/send", response_model=SendQuizResponse)
async def send_quiz(
    request: SendQuizRequest,
    use_case: SendQuizToPatientUseCase = Depends(get_send_quiz_use_case)
):
    """Presentation layer - converts HTTP to use case"""

    # Convert API schema to use case request
    use_case_request = SendQuizToPatientRequest(
        patient_id=request.patient_id,
        quiz_template_id=request.template_id
    )

    # Execute use case
    result = await use_case.execute(use_case_request)

    # Convert use case response to API schema
    return SendQuizResponse(
        quiz_id=result.quiz_id,
        sent_at=result.sent_at,
        status=result.status
    )
```

### Dependency Injection

```python
# app/api/v2/dependencies/use_cases.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.repositories.patient_repository_impl import (
    SQLAlchemyPatientRepository
)
from app.infrastructure.external.whatsapp_service_impl import EvolutionWhatsAppService
from app.application.use_cases.send_quiz_to_patient import SendQuizToPatientUseCase

async def get_send_quiz_use_case(
    db: AsyncSession = Depends(get_db)
) -> SendQuizToPatientUseCase:
    """Dependency injection - wire up layers"""
    patient_repo = SQLAlchemyPatientRepository(db)
    quiz_repo = SQLAlchemyQuizRepository(db)
    whatsapp = EvolutionWhatsAppService()

    return SendQuizToPatientUseCase(
        patient_repo=patient_repo,
        quiz_repo=quiz_repo,
        whatsapp_service=whatsapp
    )
```

### Testing Strategy

```python
# tests/unit/application/test_send_quiz_use_case.py
import pytest
from unittest.mock import AsyncMock

from app.application.use_cases.send_quiz_to_patient import (
    SendQuizToPatientUseCase,
    SendQuizToPatientRequest
)

@pytest.mark.asyncio
async def test_send_quiz_to_patient_success():
    # Mock repositories (no real database needed)
    patient_repo = AsyncMock()
    quiz_repo = AsyncMock()
    whatsapp = AsyncMock()

    # Setup mock returns
    patient_repo.get_by_id.return_value = create_test_patient()
    quiz_repo.get_template.return_value = create_test_template()

    # Create use case with mocks
    use_case = SendQuizToPatientUseCase(patient_repo, quiz_repo, whatsapp)

    # Execute
    result = await use_case.execute(
        SendQuizToPatientRequest(
            patient_id=UUID("..."),
            quiz_template_id=UUID("...")
        )
    )

    # Verify business logic executed
    assert result.status == "sent"
    assert patient_repo.update.called
    assert whatsapp.send_quiz_link.called
```

### Migration Path

1. ✅ Directory structure created
2. ✅ Domain entities extracted
3. ✅ Repository interfaces defined
4. 🔄 Use cases migrated from services
5. 🔄 Repository implementations updated
6. 🔄 API endpoints refactored
7. 🔄 Dependency injection configured
8. 🔄 Tests updated for new architecture

## References

- [Clean Architecture Book](https://www.amazon.com/Clean-Architecture-Craftsmans-Software-Structure/dp/0134494164)
- [Clean Architecture in Python](https://www.thedigitalcatonline.com/blog/2016/11/14/clean-architectures-in-python-a-step-by-step-example/)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Domain-Driven Design](https://www.domainlanguage.com/ddd/)
- [Dependency Inversion Principle](https://en.wikipedia.org/wiki/Dependency_inversion_principle)

## Metadata

- **Author**: Architecture Team
- **Reviewers**: Backend Team, Tech Lead
- **Last Updated**: 2024-01-23
- **Related ADRs**: ADR-0001 (FastAPI), ADR-0007 (SPARC), ADR-0002 (PostgreSQL)
- **Tags**: architecture, clean-architecture, design-patterns, maintainability
