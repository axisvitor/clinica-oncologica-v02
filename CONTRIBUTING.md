# Contributing to Sistema Hormonia

Thank you for considering contributing to Sistema Hormonia! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [How to Contribute](#how-to-contribute)
4. [Development Process](#development-process)
5. [Coding Standards](#coding-standards)
6. [Testing Guidelines](#testing-guidelines)
7. [Documentation](#documentation)
8. [Pull Request Process](#pull-request-process)
9. [Community](#community)

## Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Examples of behavior that contributes to a positive environment:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Examples of unacceptable behavior:**
- Use of sexualized language or imagery
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

## Getting Started

### Prerequisites

Before contributing, ensure you have:

1. **Development Environment**: Set up per [Setup Guide](docs/guides/SETUP_GUIDE.md)
2. **Git Knowledge**: Basic understanding of Git and GitHub
3. **Project Understanding**: Familiarize yourself with the codebase
4. **Issue Tracking**: Check [existing issues](https://github.com/axisvitor/clinica-oncologica-v02/issues)

### Your First Contribution

1. **Find an Issue**: Look for issues labeled `good first issue` or `help wanted`
2. **Ask Questions**: Comment on the issue if you need clarification
3. **Claim the Issue**: Let maintainers know you're working on it
4. **Fork & Clone**: Fork the repository and clone to your machine
5. **Create Branch**: Create a feature branch for your work
6. **Make Changes**: Implement your solution
7. **Test**: Ensure all tests pass
8. **Submit PR**: Create a pull request

## How to Contribute

### Reporting Bugs

**Before submitting a bug report:**
- Check the documentation for solutions
- Search existing issues to avoid duplicates
- Collect relevant information (error messages, logs, steps to reproduce)

**Bug Report Template:**

```markdown
**Description**
A clear and concise description of the bug.

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. Windows 10, macOS 12.0]
- Browser: [e.g. Chrome 96, Firefox 95]
- Version: [e.g. 1.0.0]

**Screenshots**
If applicable, add screenshots.

**Additional Context**
Any other relevant information.
```

### Suggesting Features

**Before suggesting a feature:**
- Check if it already exists
- Ensure it aligns with project goals
- Consider the scope and complexity

**Feature Request Template:**

```markdown
**Feature Description**
Clear description of the proposed feature.

**Problem it Solves**
What problem does this feature address?

**Proposed Solution**
How would you implement this feature?

**Alternatives Considered**
What other solutions did you consider?

**Additional Context**
Mockups, diagrams, or examples.
```

### Contributing Code

**Types of contributions we accept:**
- Bug fixes
- New features
- Performance improvements
- Documentation improvements
- Test coverage improvements
- Code refactoring

## Development Process

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/clinica-oncologica-v02.git
cd clinica-oncologica-v02-1

# Add upstream remote
git remote add upstream https://github.com/axisvitor/clinica-oncologica-v02.git
```

### 2. Create a Branch

```bash
# Update your local develop branch
git checkout develop
git pull upstream develop

# Create feature branch
git checkout -b feature/your-feature-name
```

### 3. Make Changes

```bash
# Make your changes
# Follow coding standards
# Write tests
# Update documentation
```

### 4. Commit Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat(component): add new feature

- Detailed description of changes
- Why this change is needed
- Any breaking changes

Closes #issue-number"
```

### 5. Keep Branch Updated

```bash
# Regularly sync with upstream
git fetch upstream
git rebase upstream/develop
```

### 6. Push and Create PR

```bash
# Push to your fork
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## Coding Standards

### Python (Backend)

Follow [PEP 8](https://pep8.org/) and project conventions:

```python
# Type hints required
def create_patient(data: PatientCreate, db: Session) -> Patient:
    """Create a new patient record."""
    pass

# Use descriptive names
def calculate_quiz_score(responses: Dict[str, Any]) -> float:
    pass

# Constants in UPPERCASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Docstrings for public functions
def process_data(data: Dict) -> Result:
    """
    Process incoming data and return result.

    Args:
        data: Dictionary containing input data

    Returns:
        Processed result object

    Raises:
        ValidationError: If data is invalid
    """
    pass
```

### TypeScript/React (Frontend)

```typescript
// Use TypeScript for type safety
interface Patient {
  id: number;
  name: string;
  email: string;
}

// Functional components
export const PatientCard: React.FC<PatientCardProps> = ({ patient }) => {
  return <div>{patient.name}</div>;
};

// Custom hooks for reusable logic
const usePatientData = (id: number) => {
  const [patient, setPatient] = useState<Patient | null>(null);
  // ...
  return { patient };
};
```

### Code Formatting

```bash
# Python
black .
isort .
flake8

# TypeScript/React
npm run format
npm run lint
```

## Testing Guidelines

### Writing Tests

**All new code must include tests.**

**Backend Tests:**

```python
# tests/test_patient_service.py
import pytest
from app.services.patient_service import create_patient

class TestPatientService:
    def test_create_patient_success(self, db_session, patient_data):
        """Test successful patient creation."""
        patient = create_patient(patient_data, db_session)
        assert patient.id is not None
        assert patient.name == patient_data.name

    def test_create_patient_duplicate_email_fails(self, db_session, patient_data):
        """Test creation with duplicate email fails."""
        create_patient(patient_data, db_session)

        with pytest.raises(ValueError, match="Email already exists"):
            create_patient(patient_data, db_session)
```

**Frontend Tests:**

```typescript
// PatientCard.test.tsx
import { render, screen } from '@testing-library/react';
import { PatientCard } from './PatientCard';

describe('PatientCard', () => {
  it('renders patient information', () => {
    const patient = { id: 1, name: 'John Doe', email: 'john@example.com' };
    render(<PatientCard patient={patient} />);
    expect(screen.getByText('John Doe')).toBeInTheDocument();
  });
});
```

### Running Tests

```bash
# Backend
cd backend-hormonia
pytest --cov=app --cov-report=html

# Frontend
cd frontend-hormonia
npm test
npm run test:e2e
```

### Coverage Requirements

- **Overall**: 80% minimum
- **New code**: 90% minimum
- **Critical paths**: 95% minimum

## Documentation

### Code Documentation

```python
def complex_function(param1: str, param2: int) -> Dict:
    """
    Brief description of function.

    Detailed explanation of what the function does,
    including any important details or caveats.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary containing results

    Raises:
        ValueError: If parameters are invalid

    Example:
        >>> result = complex_function("test", 42)
        >>> result["status"]
        "success"
    """
    pass
```

### Documentation Files

Update relevant documentation when:
- Adding new features
- Changing APIs
- Modifying configuration
- Updating deployment process

## Pull Request Process

### Before Submitting

**Checklist:**
- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] Branch is up to date with develop
- [ ] No merge conflicts
- [ ] Self-review completed

### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issue
Closes #issue-number

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing
Describe how you tested your changes.

## Screenshots
If applicable.

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated Checks**: CI/CD must pass
2. **Code Review**: At least 1 approval required
3. **Testing**: Reviewer should test changes
4. **Feedback**: Address all review comments
5. **Approval**: Once approved, maintainer will merge

### After Merge

- [ ] Delete feature branch
- [ ] Update issue status
- [ ] Monitor for any issues

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **Pull Requests**: Code contributions and reviews
- **Discussions**: General questions and ideas

### Getting Help

- **Documentation**: Check `/docs` folder first
- **Issues**: Search existing issues
- **Questions**: Open a discussion or issue

### Recognition

Contributors are recognized in:
- Project README
- Release notes
- Contributor list

## Additional Resources

- [Setup Guide](docs/guides/SETUP_GUIDE.md)
- [Development Workflow](docs/development/DEVELOPMENT_WORKFLOW.md)
- [Architecture Overview](docs/architecture/SYSTEM_OVERVIEW.md)
- [Security Guidelines](docs/security/SECURITY_AUTHENTICATION.md)

## License

By contributing, you agree that your contributions will be licensed under the project's license.

---

**Thank you for contributing to Sistema Hormonia!**

We appreciate your time and effort in helping make this project better.
