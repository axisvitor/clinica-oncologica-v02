# Phone Validation Standardization

## Overview

This document describes the standardized phone number validation implementation across API versions v1 and v2 in the backend-hormonia application.

## Problem Statement

**Issue**: Inconsistent phone validation between API versions
- **v1** (`app/schemas/patient.py`): Required strict E.164 format (must start with `+`)
- **v2** (`app/schemas/v2/patient.py`): Accepted both E.164 and Brazilian formats
- **Risk**: Data accepted in v2 could be rejected in v1, causing synchronization bugs

## Solution

Created a shared validation module at `/app/schemas/validators/phone.py` with standardized validators used by both API versions.

### Module Structure

```
app/schemas/validators/
├── __init__.py           # Public API exports
└── phone.py              # Phone validation logic
```

## Validation Modes

The module supports 4 validation modes via `PhoneValidationMode` enum:

### 1. `E164_STRICT` (v1 API)
- **Format**: `+5511987654321`
- **Rules**:
  - Must start with `+` followed by country code
  - Contains only digits (10-15 after `+`)
  - No spaces, dashes, or parentheses in output
- **Use case**: v1 API backward compatibility

### 2. `BR_FLEXIBLE` (Brazilian local)
- **Format**: `11987654321` or `(11) 98765-4321`
- **Rules**:
  - DDD (area code) + number = 10-11 digits
  - DDD must be 11-99
  - Cannot include country code
  - Preserves original formatting
- **Use case**: Brazilian-only applications

### 3. `HYBRID` (v2 API - Default)
- **Accepts**: Both E.164 and Brazilian formats
- **Rules**:
  - E.164: Validates and normalizes to `+5511987654321`
  - Brazilian: Validates and preserves format `(11) 98765-4321`
- **Use case**: v2 API flexibility for international and local users

### 4. `BR_TO_E164` (Normalization)
- **Input**: Brazilian format
- **Output**: E.164 format with `+55` prefix
- **Use case**: Converting Brazilian phones to E.164 for storage/API calls

## Implementation Details

### Core Functions

#### 1. `validate_phone_e164(phone: str, allow_none: bool = False) -> Optional[str]`

Validates and normalizes phone to E.164 format.

```python
from app.schemas.validators.phone import validate_phone_e164

# Valid
phone = validate_phone_e164("+55 11 98765-4321")
# Returns: "+5511987654321"

# Invalid (missing +)
phone = validate_phone_e164("11987654321")
# Raises: ValueError("Phone number must start with country code (+)")
```

#### 2. `validate_phone_br(phone: str, allow_none: bool = False) -> Optional[str]`

Validates Brazilian phone format, preserving original formatting.

```python
from app.schemas.validators.phone import validate_phone_br

# Valid - preserves format
phone = validate_phone_br("(11) 98765-4321")
# Returns: "(11) 98765-4321"

# Invalid (includes country code)
phone = validate_phone_br("+5511987654321")
# Raises: ValueError("Brazilian phone format should not include country code")
```

#### 3. `normalize_phone(phone: str, mode: PhoneValidationMode, allow_none: bool = False) -> Optional[str]`

Main validation function with mode selection.

```python
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

# E.164 strict
phone = normalize_phone("+5511987654321", PhoneValidationMode.E164_STRICT)

# Brazilian flexible
phone = normalize_phone("11987654321", PhoneValidationMode.BR_FLEXIBLE)

# Hybrid (accepts both)
phone = normalize_phone("(11) 98765-4321", PhoneValidationMode.HYBRID)

# Convert BR to E.164
phone = normalize_phone("11987654321", PhoneValidationMode.BR_TO_E164)
# Returns: "+5511987654321"
```

#### 4. `format_phone_display(phone: str) -> str`

Formats phone for user display with Brazilian mask.

```python
from app.schemas.validators.phone import format_phone_display

# E.164 to display
phone = format_phone_display("+5511987654321")
# Returns: "(11) 98765-4321"

# Already formatted
phone = format_phone_display("(11) 98765-4321")
# Returns: "(11) 98765-4321"
```

## Schema Integration

### v1 API (`app/schemas/patient.py`)

**Behavior**: Strict E.164 enforcement

```python
from pydantic import field_validator
from app.schemas.validators.phone import validate_phone_e164

class PatientBase(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number in E.164 format."""
        return validate_phone_e164(v, allow_none=False)
```

**Examples**:
- ✅ `"+5511987654321"` → Valid
- ❌ `"11987654321"` → Raises ValueError
- ❌ `"(11) 98765-4321"` → Raises ValueError

### v2 API (`app/schemas/v2/patient.py`)

**Behavior**: Hybrid mode (accepts both formats)

```python
from pydantic import field_validator
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

class PatientV2Base(BaseModel):
    phone: Optional[str]

    @field_validator("phone")
    @classmethod
    def validate_phone_format(cls, v):
        """Validate phone number for E.164 or Brazilian format."""
        if not v:
            return v
        return normalize_phone(v, mode=PhoneValidationMode.HYBRID, allow_none=True)
```

**Examples**:
- ✅ `"+5511987654321"` → `"+5511987654321"` (E.164)
- ✅ `"11987654321"` → `"11987654321"` (Brazilian)
- ✅ `"(11) 98765-4321"` → `"(11) 98765-4321"` (Brazilian formatted)

## Validation Rules Reference

### E.164 Format Requirements
- **Prefix**: Must start with `+`
- **Length**: 10-15 digits after `+`
- **Characters**: Only digits allowed after `+`
- **Normalization**: Removes spaces, dashes, parentheses
- **Example**: `+5511987654321`

### Brazilian Format Requirements
- **DDD (Area Code)**: 2 digits (11-99)
- **Number**: 8-9 digits
  - 8 digits: Landline (e.g., `11 3333-4444`)
  - 9 digits: Mobile (e.g., `11 98765-4321`)
- **Total Length**: 10-11 digits
- **Formatting**: Optional parentheses, spaces, dashes
- **Examples**:
  - `11987654321` (unformatted)
  - `(11) 98765-4321` (formatted mobile)
  - `(11) 3333-4444` (formatted landline)

## Error Messages

The validators provide clear, localized error messages:

| Error | Message | Cause |
|-------|---------|-------|
| Missing + | "Phone number must start with country code (+)" | E.164 without + prefix |
| Invalid length | "Phone number must have 10-15 digits, got X" | E.164 outside range |
| Non-digits | "Phone number must contain only + and digits" | E.164 with letters |
| Country code in BR | "Brazilian phone format should not include country code" | BR format with + |
| Invalid BR length | "Brazilian phone must have 10-11 digits (DDD + number), got X" | BR outside range |
| Invalid DDD | "Invalid DDD (area code): X. Must be between 11-99" | Invalid area code |

## Testing

Comprehensive test suite at `/tests/schemas/test_phone_validation.py`:

- **E.164 validation tests**: 9 test cases
- **Brazilian validation tests**: 8 test cases
- **Normalization tests**: 9 test cases
- **Display formatting tests**: 6 test cases
- **Schema integration tests**: 2 test cases

### Running Tests

```bash
# Run phone validation tests
pytest tests/schemas/test_phone_validation.py -v

# Run with coverage
pytest tests/schemas/test_phone_validation.py --cov=app/schemas/validators/phone
```

## Migration Guide

### For Existing Code

**Step 1**: Replace inline validation logic

```python
# Before (inline validation)
@field_validator("phone")
@classmethod
def validate_phone(cls, v):
    if not v.startswith("+"):
        raise ValueError("Phone must start with +")
    cleaned = re.sub(r"[\s\-\(\)]", "", v)
    return cleaned

# After (using standardized module)
@field_validator("phone")
@classmethod
def validate_phone(cls, v):
    from app.schemas.validators.phone import validate_phone_e164
    return validate_phone_e164(v, allow_none=False)
```

**Step 2**: Choose appropriate mode for your use case

- **Strict E.164**: Use `validate_phone_e164()` or `PhoneValidationMode.E164_STRICT`
- **Brazilian only**: Use `validate_phone_br()` or `PhoneValidationMode.BR_FLEXIBLE`
- **Both formats**: Use `normalize_phone()` with `PhoneValidationMode.HYBRID`
- **Conversion**: Use `PhoneValidationMode.BR_TO_E164`

**Step 3**: Update tests to reflect new validation behavior

### For New Features

Always use the standardized validators:

```python
from app.schemas.validators.phone import normalize_phone, PhoneValidationMode

# For flexible APIs (recommended for v2+)
phone = normalize_phone(user_input, PhoneValidationMode.HYBRID)

# For strict compatibility (v1 API)
phone = normalize_phone(user_input, PhoneValidationMode.E164_STRICT)

# For display formatting
display = format_phone_display(stored_phone)
```

## Benefits

### 1. Consistency
- Same validation logic across all API versions
- Predictable behavior for developers and users

### 2. Maintainability
- Single source of truth for phone validation
- Easy to update rules in one place

### 3. Flexibility
- Different modes for different use cases
- Backward compatible with v1 API
- Forward compatible with international expansion

### 4. Quality
- Comprehensive test coverage
- Clear error messages
- Well-documented behavior

## Future Enhancements

Potential improvements for future versions:

1. **Country code validation**: Validate country codes against ITU-T registry
2. **Regional validation**: Support other country formats (US, UK, etc.)
3. **Phone number parsing**: Use libphonenumber for advanced parsing
4. **Formatting options**: Configurable display formats
5. **Database normalization**: Auto-convert to E.164 on storage

## References

- **E.164 Standard**: [ITU-T Recommendation E.164](https://www.itu.int/rec/T-REC-E.164/)
- **Brazilian Phone Format**: ANATEL regulations
- **Pydantic Validators**: [Pydantic Field Validators](https://docs.pydantic.dev/latest/concepts/validators/)

## Support

For questions or issues:
1. Check test suite for examples: `tests/schemas/test_phone_validation.py`
2. Review module documentation: `app/schemas/validators/phone.py`
3. See error messages for validation failures
