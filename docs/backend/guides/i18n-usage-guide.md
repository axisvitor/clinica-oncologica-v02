# Internationalization (i18n) Usage Guide

## Overview

The i18n system provides comprehensive internationalization support for error messages and user-facing text in Portuguese (pt-BR) and English (en-US).

## Quick Start

### 1. Using Translatable Exceptions

Replace hardcoded error messages with i18n-aware exceptions:

```python
# ❌ Before (hardcoded message)
from fastapi import HTTPException

raise HTTPException(
    status_code=404,
    detail="Patient not found"
)

# ✅ After (i18n exception)
from app.exceptions.i18n_exceptions import PatientNotFoundException

raise PatientNotFoundException(patient_id="123")
```

### 2. Using Translation Function

For dynamic messages:

```python
from app.config.i18n import t

# Simple translation
message = t('errors.patient.not_found')
# Portuguese: "Paciente não encontrado"
# English: "Patient not found"

# Translation with variables
message = t('errors.patient.duplicate_cpf', cpf='123.456.789-00')
# Portuguese: "CPF 123.456.789-00 já cadastrado no sistema"
# English: "CPF 123.456.789-00 is already registered in the system"
```

### 3. Setting Locale

```python
from app.config.i18n import set_locale

# Set locale for current request
set_locale('en-US')
```

## Available Exceptions

### Patient Exceptions

```python
from app.exceptions.i18n_exceptions import (
    PatientNotFoundException,
    DuplicateCPFException,
    DuplicateEmailException,
    DuplicatePhoneException,
    InvalidCPFException,
    InvalidPhoneException,
    PatientAccessDeniedException,
)

# Usage examples
raise PatientNotFoundException(patient_id="uuid")
raise DuplicateCPFException(cpf="123.456.789-00")
raise DuplicateEmailException(email="user@example.com")
raise InvalidPhoneException(phone="+55 11 98765-4321")
```

### Authentication Exceptions

```python
from app.exceptions.i18n_exceptions import (
    InvalidCredentialsException,
    TokenExpiredException,
    SessionExpiredException,
    UnauthorizedException,
    ForbiddenException,
)

# Usage examples
raise InvalidCredentialsException()
raise TokenExpiredException()
raise SessionExpiredException()
```

### Quiz Exceptions

```python
from app.exceptions.i18n_exceptions import (
    QuizSessionNotFoundException,
    QuizSessionExpiredException,
    QuizAlreadyCompletedException,
    InvalidQuizAnswerException,
)

# Usage examples
raise QuizSessionExpiredException()
raise InvalidQuizAnswerException(question_id="q1")
```

### Webhook Exceptions

```python
from app.exceptions.i18n_exceptions import (
    InvalidWebhookSignatureException,
    WebhookRateLimitException,
)

# Usage examples
raise InvalidWebhookSignatureException()
raise WebhookRateLimitException(retry_after=60)
```

### Saga Exceptions

```python
from app.exceptions.i18n_exceptions import (
    SagaExecutionFailedException,
    SagaCompensationFailedException,
    SagaTimeoutException,
)

# Usage examples
raise SagaExecutionFailedException(saga_id="saga-123")
raise SagaTimeoutException(timeout=30)
```

### Flow Exceptions

```python
from app.exceptions.i18n_exceptions import (
    FlowNotFoundException,
    InvalidFlowStateException,
)

# Usage examples
raise FlowNotFoundException(patient_id="uuid")
raise InvalidFlowStateException(state="invalid_state")
```

### Validation Exceptions

```python
from app.exceptions.i18n_exceptions import (
    RequiredFieldException,
    InvalidFormatException,
)

# Usage examples
raise RequiredFieldException(field='email')
raise InvalidFormatException(field='cpf')
```

### Server Exceptions

```python
from app.exceptions.i18n_exceptions import (
    InternalServerErrorException,
    ServiceUnavailableException,
    DatabaseErrorException,
)

# Usage examples
raise InternalServerErrorException()
raise ServiceUnavailableException()
```

## Pydantic Validation Error Translation

Automatically translate Pydantic validation errors:

```python
from pydantic import BaseModel, EmailStr, ValidationError
from app.utils.pydantic_i18n import (
    translate_pydantic_errors,
    format_validation_error_response,
    get_first_error_message,
)

class PatientCreate(BaseModel):
    email: EmailStr
    name: str
    cpf: str

try:
    patient = PatientCreate(**data)
except ValidationError as e:
    # Option 1: Get translated errors as dict
    errors = translate_pydantic_errors(e)
    # {
    #   "errors": [
    #     {"field": "email", "message": "Email inválido", "type": "value_error.email"}
    #   ]
    # }

    # Option 2: Format as API response
    response = format_validation_error_response(e)
    raise HTTPException(status_code=422, detail=response)

    # Option 3: Get first error only
    message = get_first_error_message(e)
    raise HTTPException(status_code=422, detail=message)
```

## Locale Detection

The i18n middleware automatically detects locale from:

1. **Query Parameter** (highest priority): `?lang=en-US`
2. **Accept-Language Header**: `Accept-Language: en-US,en;q=0.9`
3. **Cookie**: `locale=en-US`
4. **Default**: `pt-BR`

### Example Requests

```bash
# Using query parameter
curl "http://api.example.com/patients/123?lang=en-US"

# Using header
curl -H "Accept-Language: en-US" "http://api.example.com/patients/123"

# Using cookie
curl -b "locale=en-US" "http://api.example.com/patients/123"
```

## Adding New Translations

### 1. Add to Translation Files

Edit `app/locales/pt-BR.json`:

```json
{
  "errors": {
    "medication": {
      "not_found": "Medicamento não encontrado",
      "invalid_dosage": "Dosagem inválida: {dosage}"
    }
  }
}
```

Edit `app/locales/en-US.json`:

```json
{
  "errors": {
    "medication": {
      "not_found": "Medication not found",
      "invalid_dosage": "Invalid dosage: {dosage}"
    }
  }
}
```

### 2. Create Exception Class

Create in `app/exceptions/i18n_exceptions.py`:

```python
class MedicationNotFoundException(TranslatableHTTPException):
    """Raised when medication is not found."""

    def __init__(self):
        super().__init__(
            status_code=404,
            translation_key='errors.medication.not_found'
        )


class InvalidMedicationDosageException(TranslatableHTTPException):
    """Raised when medication dosage is invalid."""

    def __init__(self, dosage: str):
        super().__init__(
            status_code=400,
            translation_key='errors.medication.invalid_dosage',
            dosage=dosage
        )
```

### 3. Use in Your Code

```python
from app.exceptions.i18n_exceptions import (
    MedicationNotFoundException,
    InvalidMedicationDosageException,
)

def get_medication(medication_id: str):
    medication = db.query(Medication).filter(
        Medication.id == medication_id
    ).first()

    if not medication:
        raise MedicationNotFoundException()

    return medication

def validate_dosage(dosage: str):
    if not is_valid_dosage(dosage):
        raise InvalidMedicationDosageException(dosage=dosage)
```

## Extracting Hardcoded Strings

Use the extraction script to find hardcoded error messages:

```bash
# Extract strings from source code
python scripts/extract_translatable_strings.py

# Output files:
# - docs/translations/missing_translations.json (template)
# - docs/translations/extraction_report.txt (report)
```

The script will:
1. Scan all Python files in `app/`
2. Extract strings from `HTTPException` and `raise` statements
3. Categorize messages by type (patient, auth, quiz, etc.)
4. Generate a translation template
5. Create a detailed report

## Testing i18n

### Unit Tests

```python
from app.config.i18n import t, set_locale
from app.exceptions.i18n_exceptions import PatientNotFoundException

def test_error_message_in_portuguese():
    """Test error messages in Portuguese."""
    set_locale('pt-BR')

    with pytest.raises(PatientNotFoundException) as exc_info:
        raise PatientNotFoundException()

    assert 'não encontrado' in str(exc_info.value.detail).lower()


def test_error_message_in_english():
    """Test error messages in English."""
    set_locale('en-US')

    with pytest.raises(PatientNotFoundException) as exc_info:
        raise PatientNotFoundException()

    assert 'not found' in str(exc_info.value.detail).lower()
```

### Integration Tests

```python
async def test_locale_from_query_param(client):
    """Test locale selection via query parameter."""
    response = await client.get(
        '/api/v2/patients/00000000-0000-0000-0000-000000000000?lang=en-US'
    )

    assert response.status_code == 404
    assert 'not found' in response.json()['detail'].lower()
    assert response.headers['Content-Language'] == 'en-US'
```

## Best Practices

### 1. Always Use i18n Exceptions

✅ **Do:**
```python
raise PatientNotFoundException(patient_id=patient_id)
```

❌ **Don't:**
```python
raise HTTPException(404, f"Patient {patient_id} not found")
```

### 2. Provide Context Variables

✅ **Do:**
```python
raise DuplicateCPFException(cpf=patient.cpf)
```

❌ **Don't:**
```python
raise DuplicateCPFException()  # Missing CPF value
```

### 3. Use Consistent Translation Keys

Follow the naming pattern: `{namespace}.{category}.{specific_error}`

Examples:
- `errors.patient.not_found`
- `errors.auth.invalid_credentials`
- `errors.quiz.session_expired`
- `success.patient_created`
- `common.loading`

### 4. Keep Messages Concise

✅ **Do:**
```json
{
  "errors": {
    "patient": {
      "not_found": "Patient not found"
    }
  }
}
```

❌ **Don't:**
```json
{
  "errors": {
    "patient": {
      "not_found": "We're sorry, but we couldn't find the patient record you were looking for in our database system. Please check the patient ID and try again."
    }
  }
}
```

### 5. Test Both Locales

Always test error messages in both Portuguese and English:

```python
@pytest.mark.parametrize("locale,expected", [
    ("pt-BR", "não encontrado"),
    ("en-US", "not found"),
])
def test_error_message(locale, expected):
    set_locale(locale)
    message = t('errors.patient.not_found')
    assert expected in message.lower()
```

## Troubleshooting

### Issue: Translation not found

**Symptom:** Translation key is returned instead of translated text

```python
>>> t('errors.patient.not_found')
'errors.patient.not_found'  # Key returned instead of translation
```

**Solution:**
1. Check translation file exists: `app/locales/pt-BR.json`
2. Verify key path in JSON file
3. Ensure i18n module is initialized (import `app.config.i18n`)

### Issue: Wrong locale used

**Symptom:** Getting Portuguese translations when expecting English

**Solution:**
1. Check middleware is installed: `app.add_middleware(I18nMiddleware)`
2. Verify `Accept-Language` header or `?lang=` parameter
3. Check cookie value: `locale=en-US`
4. Verify locale is set: `set_locale('en-US')`

### Issue: Variables not substituted

**Symptom:** Translation shows `{variable}` placeholder instead of value

```python
>>> t('errors.patient.duplicate_cpf', cpf='123.456.789-00')
'CPF {cpf} já cadastrado'  # Variable not substituted
```

**Solution:**
1. Check parameter name matches translation key
2. Verify parameter is passed to `t()` function
3. Ensure translation uses correct placeholder syntax: `{cpf}`

## Migration Checklist

To migrate existing code to use i18n:

- [ ] Install dependencies: `pip install babel python-i18n pydantic-i18n`
- [ ] Add i18n middleware to FastAPI app
- [ ] Run extraction script to find hardcoded strings
- [ ] Add translations to `pt-BR.json` and `en-US.json`
- [ ] Replace `HTTPException` with i18n exception classes
- [ ] Update Pydantic error handling to use `translate_pydantic_errors`
- [ ] Add tests for both locales
- [ ] Update API documentation with locale information
- [ ] Test with different `Accept-Language` headers
- [ ] Verify `Content-Language` header in responses

## Additional Resources

- Translation files: `backend-hormonia/app/locales/`
- Exception classes: `backend-hormonia/app/exceptions/i18n_exceptions.py`
- Configuration: `backend-hormonia/app/config/i18n.py`
- Request locale helpers: `backend-hormonia/app/config/i18n.py` (`i18n_middleware.py` removed on 2026-02-10)
- Tests: `backend-hormonia/tests/api/test_i18n.py`
- Extraction script: `backend-hormonia/scripts/extract_translatable_strings.py`
