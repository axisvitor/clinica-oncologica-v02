# Development Workflow

**Project**: Clínica Oncológica - Sistema Hormonia
**Last Updated**: 2025-11-12

## Overview

This document outlines the development workflow, coding standards, and best practices for contributing to Sistema Hormonia.

## Git Workflow

### Branch Strategy

We follow a Git Flow-inspired branching model:

```
main (production)
  │
  ├── develop (staging)
  │     │
  │     ├── feature/user-authentication
  │     ├── feature/quiz-templates
  │     ├── bugfix/message-delivery
  │     └── hotfix/security-patch
  │
  └── hotfix/critical-fix (emergency production fixes)
```

### Branch Naming Conventions

- **Feature**: `feature/short-description`
- **Bugfix**: `bugfix/issue-description`
- **Hotfix**: `hotfix/critical-issue`
- **Refactor**: `refactor/component-name`
- **Docs**: `docs/documentation-update`
- **Test**: `test/test-description`

### Commit Message Convention

Follow Conventional Commits specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

**Examples**:

```bash
# Feature
git commit -m "feat(auth): add JWT refresh token support"

# Bug fix
git commit -m "fix(quiz): resolve session timeout issue"

# Documentation
git commit -m "docs(api): update authentication endpoints"

# Multiple changes
git commit -m "feat(backend): add patient search functionality

- Implement full-text search on patient names
- Add filtering by treatment type
- Optimize query performance with indexes

Closes #123"
```

### Pull Request Process

#### 1. Create Feature Branch

```bash
# Start from develop
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/your-feature-name
```

#### 2. Make Changes

```bash
# Make your changes
# Write tests
# Update documentation

# Add changes
git add .

# Commit with conventional commit message
git commit -m "feat(component): add new feature"
```

#### 3. Keep Branch Updated

```bash
# Regularly sync with develop
git checkout develop
git pull origin develop
git checkout feature/your-feature-name
git rebase develop
```

#### 4. Push and Create PR

```bash
# Push to remote
git push origin feature/your-feature-name

# Create pull request on GitHub
# Use PR template
# Request reviews from team members
```

#### 5. Code Review Process

- **Self-review**: Review your own PR first
- **Automated checks**: Ensure CI/CD passes
- **Peer review**: At least 1 approval required
- **Address feedback**: Make requested changes
- **Final check**: Verify all checks pass

#### 6. Merge

```bash
# After approval, merge using GitHub UI
# Squash and merge for feature branches
# Regular merge for hotfixes

# Delete feature branch after merge
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

## Development Environment

### Local Development Setup

```bash
# Backend
cd backend-hormonia
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload

# Frontend
cd frontend-hormonia
npm run dev

# Quiz Interface
cd quiz-mensal-interface
npm run dev
```

### Using Makefile Commands

Backend Makefile commands:

```bash
# Setup environment
make setup

# Start development server
make dev

# Run tests
make test

# Run tests with coverage
make test-cov

# Format code
make format

# Lint code
make lint

# Type check
make typecheck

# All checks (format + lint + typecheck + test)
make check

# Database migrations
make migrate
make migration name="add_new_column"

# Docker
make docker-up
make docker-down
```

## Code Standards

### Python (Backend)

#### Style Guide

Follow PEP 8 with these additions:

```python
# Imports order
import os
import sys
from typing import Optional, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.models import Patient
from app.schemas import PatientCreate
from app.core.database import get_db


# Type hints required
def get_patient(patient_id: int, db: Session) -> Optional[Patient]:
    return db.query(Patient).filter(Patient.id == patient_id).first()


# Docstrings for public functions
def create_patient(data: PatientCreate, db: Session) -> Patient:
    """
    Create a new patient record.

    Args:
        data: Patient creation data
        db: Database session

    Returns:
        Created patient instance

    Raises:
        ValueError: If patient data is invalid
    """
    patient = Patient(**data.dict())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


# Constants in UPPERCASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30


# Private functions with leading underscore
def _internal_helper():
    pass
```

#### Code Organization

```python
# File structure
"""Module docstring."""

# Standard library imports

# Third-party imports

# Local imports

# Constants

# Type definitions

# Functions/Classes

# Main execution (if script)
if __name__ == "__main__":
    pass
```

#### Testing

```python
# Test file: test_<module>.py
import pytest
from app.services.patient_service import create_patient


class TestPatientService:
    """Test patient service functionality."""

    def test_create_patient_success(self, db_session, patient_data):
        """Test successful patient creation."""
        patient = create_patient(patient_data, db_session)
        assert patient.id is not None
        assert patient.name == patient_data.name

    def test_create_patient_duplicate_email(self, db_session, patient_data):
        """Test patient creation with duplicate email fails."""
        create_patient(patient_data, db_session)

        with pytest.raises(ValueError, match="Email already exists"):
            create_patient(patient_data, db_session)
```

### TypeScript/React (Frontend)

#### Style Guide

```typescript
// Use TypeScript for type safety
interface Patient {
  id: number;
  name: string;
  email: string;
  treatmentType: TreatmentType;
}

// Functional components with TypeScript
interface PatientCardProps {
  patient: Patient;
  onEdit: (id: number) => void;
}

export const PatientCard: React.FC<PatientCardProps> = ({ patient, onEdit }) => {
  return (
    <div className="card">
      <h3>{patient.name}</h3>
      <button onClick={() => onEdit(patient.id)}>Edit</button>
    </div>
  );
};

// Custom hooks for reusable logic
const usePatientData = (patientId: number) => {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPatient(patientId)
      .then(setPatient)
      .finally(() => setLoading(false));
  }, [patientId]);

  return { patient, loading };
};

// Constants in UPPER_SNAKE_CASE
const API_BASE_URL = 'http://localhost:8000';
const MAX_RETRY_ATTEMPTS = 3;
```

#### Component Structure

```typescript
// Component file structure
import React from 'react';
import { useQuery } from '@tanstack/react-query';

// Type definitions
interface Props {
  // ...
}

// Helper functions
const helper = () => {};

// Main component
export const Component: React.FC<Props> = ({ ...props }) => {
  // Hooks
  const [state, setState] = useState();
  const query = useQuery();

  // Effects
  useEffect(() => {}, []);

  // Handlers
  const handleClick = () => {};

  // Render
  return <div />;
};

// Sub-components (if small and related)
const SubComponent = () => {};
```

#### Testing

```typescript
// Test file: Component.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { PatientCard } from './PatientCard';

describe('PatientCard', () => {
  it('renders patient information', () => {
    const patient = {
      id: 1,
      name: 'John Doe',
      email: 'john@example.com',
    };

    render(<PatientCard patient={patient} onEdit={() => {}} />);

    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });

  it('calls onEdit when edit button clicked', () => {
    const onEdit = jest.fn();
    const patient = { id: 1, name: 'John', email: 'john@example.com' };

    render(<PatientCard patient={patient} onEdit={onEdit} />);

    fireEvent.click(screen.getByText('Edit'));
    expect(onEdit).toHaveBeenCalledWith(1);
  });
});
```

## Testing Strategy

### Test Pyramid

```
       /\
      /E2E\        ← End-to-End (10%)
     /      \
    / Integr \     ← Integration (30%)
   /          \
  /   Unit     \   ← Unit Tests (60%)
 /______________\
```

### Backend Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_auth.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run with markers
pytest -m "not slow"  # Skip slow tests
pytest -m "integration"  # Only integration tests
```

### Frontend Testing

```bash
# Run unit tests
npm test

# Run with coverage
npm run test:coverage

# Run E2E tests
npm run test:e2e

# Run E2E in headed mode (see browser)
npm run test:e2e:headed

# Run specific test file
npm test PatientCard.test.tsx
```

### Test Coverage Requirements

- **Overall**: 80% minimum
- **Critical paths**: 95% minimum
- **New code**: 90% minimum

## Code Review Guidelines

### As a Reviewer

1. **Check functionality**: Does it work as intended?
2. **Review tests**: Are there adequate tests?
3. **Check style**: Follows coding standards?
4. **Security**: Any security concerns?
5. **Performance**: Any performance issues?
6. **Documentation**: Is documentation updated?

### Review Checklist

```markdown
- [ ] Code follows style guidelines
- [ ] Tests are included and pass
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] No performance regressions
- [ ] Commit messages follow convention
- [ ] PR description is clear
- [ ] No merge conflicts
```

### Providing Feedback

```markdown
# Good feedback
"Consider using a dictionary here for O(1) lookup instead of a list (O(n))."

# Even better
"Consider using a dictionary here for O(1) lookup instead of a list (O(n)). Example:
```python
patient_dict = {p.id: p for p in patients}
return patient_dict.get(patient_id)
```
"

# Not helpful
"This is wrong."
```

## Documentation Standards

### Code Documentation

```python
def process_quiz_response(
    quiz_id: int,
    responses: Dict[str, Any],
    db: Session
) -> QuizResult:
    """
    Process quiz responses and generate results.

    This function validates quiz responses, calculates scores,
    generates insights, and stores results in the database.

    Args:
        quiz_id: ID of the quiz template
        responses: Dictionary of question ID to response value
        db: Database session for persistence

    Returns:
        QuizResult object containing scores and insights

    Raises:
        ValidationError: If responses are invalid
        QuizNotFoundError: If quiz template doesn't exist

    Example:
        >>> responses = {"q1": "yes", "q2": 5}
        >>> result = process_quiz_response(1, responses, db)
        >>> result.total_score
        8.5
    """
    # Implementation
```

### README Files

Each component should have a README:

```markdown
# Component Name

Brief description of the component.

## Features

- Feature 1
- Feature 2

## Installation

```bash
npm install
```

## Usage

```typescript
import { Component } from './Component';

<Component prop="value" />
```

## API

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| prop1 | string | - | Description |

## Examples

[Examples here]

## Testing

```bash
npm test
```
```

## Performance Guidelines

### Backend

- **Database queries**: Use indexes, eager loading
- **API responses**: < 200ms (p95)
- **Caching**: Cache expensive operations
- **Async operations**: Use Celery for long tasks

### Frontend

- **Bundle size**: Keep main bundle < 500KB
- **Code splitting**: Lazy load routes
- **Images**: Optimize and use proper formats
- **Caching**: Use React Query for API caching

## Security Guidelines

### Backend

```python
# ✅ Good: Parameterized queries
db.query(Patient).filter(Patient.id == patient_id).first()

# ❌ Bad: String concatenation (SQL injection risk)
db.execute(f"SELECT * FROM patients WHERE id = {patient_id}")

# ✅ Good: Input validation
from pydantic import validator

class PatientCreate(BaseModel):
    email: str

    @validator('email')
    def validate_email(cls, v):
        if not is_valid_email(v):
            raise ValueError('Invalid email')
        return v

# ✅ Good: Secure password hashing
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd_context.hash(password)
```

### Frontend

```typescript
// ✅ Good: Sanitize user input
import DOMPurify from 'dompurify';
const clean = DOMPurify.sanitize(userInput);

// ✅ Good: Secure token storage
// Store in httpOnly cookies or secure storage
// Never in localStorage for sensitive tokens

// ✅ Good: CSRF protection
const csrfToken = getCsrfToken();
axios.post('/api/endpoint', data, {
  headers: { 'X-CSRF-Token': csrfToken }
});
```

## Deployment Process

### Development → Staging

```bash
# Merge to develop branch
git checkout develop
git merge feature/your-feature
git push origin develop

# Automatic deploy to staging environment
# Wait for CI/CD pipeline to complete
```

### Staging → Production

```bash
# Create release branch
git checkout -b release/v1.2.0 develop

# Final testing
# Update version numbers
# Update CHANGELOG

# Merge to main
git checkout main
git merge release/v1.2.0
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin main --tags

# Merge back to develop
git checkout develop
git merge release/v1.2.0
git push origin develop

# Delete release branch
git branch -d release/v1.2.0
```

## Troubleshooting Development Issues

### Backend Issues

```bash
# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Reset database
alembic downgrade base
alembic upgrade head

# Clear Redis cache
redis-cli FLUSHALL
```

### Frontend Issues

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear build cache
rm -rf .vite dist

# Clear browser cache
# Chrome: Ctrl+Shift+Delete
```

## Resources

- **Backend Documentation**: `/backend-hormonia/docs/`
- **Frontend Documentation**: `/frontend-hormonia/README.md`
- **API Documentation**: `http://localhost:8000/docs`
- **Style Guide**: This document

## Getting Help

- **Documentation**: Check relevant docs first
- **GitHub Issues**: Search existing issues
- **Team Chat**: Ask in development channel
- **Code Review**: Request review from teammates

---

**Last Updated**: 2025-11-12
**Maintained By**: Development Team
