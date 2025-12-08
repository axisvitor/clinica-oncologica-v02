"""
Unit tests for patient age validation (LOW-004).

Tests the birth_date validator in PatientCreate and PatientUpdate schemas
to ensure patients are between 18 and 120 years old.

Reference: LOW-004 - birth_date Minimum Age Validation

Test Coverage:
- Valid ages (18-120 years)
- Edge cases (exactly 18, exactly 120)
- Invalid ages (under 18, over 120, future dates)
- Null/None birth_date handling
"""

import pytest
from datetime import date, timedelta
from pydantic import ValidationError

from app.schemas.patient import PatientCreate, PatientUpdate


# =========================================================================
# TEST DATA HELPERS
# =========================================================================


def get_birth_date_for_age(age_years: float) -> date:
    """Get a birth date for a specific age in years."""
    today = date.today()
    return today - timedelta(days=int(age_years * 365.25))


def create_valid_patient_data(**overrides) -> dict:
    """Create valid patient data for testing."""
    data = {
        "phone": "+5511999999999",
        "name": "Test Patient",
        "email": "test@example.com",
        "birth_date": get_birth_date_for_age(30),  # Default: 30 years old
    }
    data.update(overrides)
    return data


# =========================================================================
# VALID AGE TESTS (18-120 years)
# =========================================================================


def test_valid_age_30_years():
    """Patient aged 30 years old is valid."""
    data = create_valid_patient_data(birth_date=get_birth_date_for_age(30))
    patient = PatientCreate(**data)
    assert patient.birth_date is not None


def test_valid_age_18_years_exactly():
    """Patient exactly 18 years old (edge case) is valid."""
    # Exactly 18 years ago (18 * 365.25 days)
    data = create_valid_patient_data(birth_date=get_birth_date_for_age(18))
    patient = PatientCreate(**data)
    assert patient.birth_date is not None


def test_valid_age_18_years_plus_one_day():
    """Patient 18 years + 1 day old is valid."""
    birth_date = get_birth_date_for_age(18) - timedelta(days=1)
    data = create_valid_patient_data(birth_date=birth_date)
    patient = PatientCreate(**data)
    assert patient.birth_date == birth_date


def test_valid_age_65_years():
    """Patient aged 65 years is valid."""
    data = create_valid_patient_data(birth_date=get_birth_date_for_age(65))
    patient = PatientCreate(**data)
    assert patient.birth_date is not None


def test_valid_age_90_years():
    """Patient aged 90 years is valid."""
    data = create_valid_patient_data(birth_date=get_birth_date_for_age(90))
    patient = PatientCreate(**data)
    assert patient.birth_date is not None


def test_valid_age_120_years_exactly():
    """Patient exactly 120 years old (edge case) is valid."""
    birth_date = get_birth_date_for_age(120)
    data = create_valid_patient_data(birth_date=birth_date)
    patient = PatientCreate(**data)
    assert patient.birth_date == birth_date


def test_valid_age_119_years():
    """Patient aged 119 years is valid."""
    data = create_valid_patient_data(birth_date=get_birth_date_for_age(119))
    patient = PatientCreate(**data)
    assert patient.birth_date is not None


# =========================================================================
# INVALID AGE TESTS - UNDER 18
# =========================================================================


def test_invalid_age_17_years():
    """Patient under 18 years old raises ValidationError."""
    birth_date = get_birth_date_for_age(17)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("at least 18 years old" in str(e["msg"]) for e in errors)


def test_invalid_age_17_years_minus_one_day():
    """Patient 17 years - 1 day old raises ValidationError."""
    birth_date = get_birth_date_for_age(17) + timedelta(days=1)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("at least 18 years old" in str(e["msg"]) for e in errors)


def test_invalid_age_10_years():
    """Patient aged 10 years raises ValidationError."""
    birth_date = get_birth_date_for_age(10)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("at least 18 years old" in str(e["msg"]) for e in errors)


def test_invalid_age_1_year():
    """Patient aged 1 year raises ValidationError."""
    birth_date = get_birth_date_for_age(1)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("at least 18 years old" in str(e["msg"]) for e in errors)


# =========================================================================
# INVALID AGE TESTS - OVER 120
# =========================================================================


def test_invalid_age_121_years():
    """Patient over 120 years old raises ValidationError."""
    birth_date = get_birth_date_for_age(121)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("over 120 years old" in str(e["msg"]) for e in errors)


def test_invalid_age_150_years():
    """Patient aged 150 years raises ValidationError."""
    birth_date = get_birth_date_for_age(150)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("over 120 years old" in str(e["msg"]) for e in errors)


def test_invalid_age_200_years():
    """Patient aged 200 years raises ValidationError."""
    birth_date = get_birth_date_for_age(200)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("over 120 years old" in str(e["msg"]) for e in errors)


# =========================================================================
# INVALID AGE TESTS - FUTURE DATES
# =========================================================================


def test_invalid_birth_date_future_tomorrow():
    """Birth date in the future (tomorrow) raises ValidationError."""
    tomorrow = date.today() + timedelta(days=1)
    data = create_valid_patient_data(birth_date=tomorrow)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("cannot be in the future" in str(e["msg"]) for e in errors)


def test_invalid_birth_date_future_one_year():
    """Birth date in the future (1 year) raises ValidationError."""
    future_date = date.today() + timedelta(days=365)
    data = create_valid_patient_data(birth_date=future_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("cannot be in the future" in str(e["msg"]) for e in errors)


def test_birth_date_today_is_invalid():
    """Birth date set to today raises ValidationError (0 years old)."""
    today = date.today()
    data = create_valid_patient_data(birth_date=today)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    assert any("at least 18 years old" in str(e["msg"]) for e in errors)


# =========================================================================
# NULL/NONE HANDLING
# =========================================================================


def test_null_birth_date_is_allowed():
    """Null birth_date is allowed (optional field)."""
    data = create_valid_patient_data(birth_date=None)
    patient = PatientCreate(**data)
    assert patient.birth_date is None


def test_missing_birth_date_is_allowed():
    """Missing birth_date field is allowed (optional)."""
    data = create_valid_patient_data()
    del data["birth_date"]
    patient = PatientCreate(**data)
    assert patient.birth_date is None


# =========================================================================
# PATIENT UPDATE VALIDATION
# =========================================================================


def test_patient_update_valid_age():
    """PatientUpdate validates age correctly."""
    birth_date = get_birth_date_for_age(25)
    update = PatientUpdate(birth_date=birth_date)
    assert update.birth_date == birth_date


def test_patient_update_invalid_age_under_18():
    """PatientUpdate rejects age under 18."""
    birth_date = get_birth_date_for_age(17)

    with pytest.raises(ValidationError) as exc_info:
        PatientUpdate(birth_date=birth_date)

    errors = exc_info.value.errors()
    assert any("at least 18 years old" in str(e["msg"]) for e in errors)


def test_patient_update_invalid_age_over_120():
    """PatientUpdate rejects age over 120."""
    birth_date = get_birth_date_for_age(121)

    with pytest.raises(ValidationError) as exc_info:
        PatientUpdate(birth_date=birth_date)

    errors = exc_info.value.errors()
    assert any("over 120 years old" in str(e["msg"]) for e in errors)


def test_patient_update_null_birth_date():
    """PatientUpdate allows null birth_date."""
    update = PatientUpdate(birth_date=None, name="Updated Name")
    assert update.birth_date is None


# =========================================================================
# ERROR MESSAGE VALIDATION
# =========================================================================


def test_under_18_error_includes_actual_age():
    """Error message for under-18 includes calculated age."""
    birth_date = get_birth_date_for_age(17)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    error_msg = str(errors[0]["msg"])

    # Should include the birth date in ISO format
    assert birth_date.isoformat() in error_msg

    # Should mention age is under 18
    assert "17" in error_msg or "age" in error_msg.lower()


def test_over_120_error_includes_actual_age():
    """Error message for over-120 includes calculated age."""
    birth_date = get_birth_date_for_age(150)
    data = create_valid_patient_data(birth_date=birth_date)

    with pytest.raises(ValidationError) as exc_info:
        PatientCreate(**data)

    errors = exc_info.value.errors()
    error_msg = str(errors[0]["msg"])

    # Should include the birth date
    assert birth_date.isoformat() in error_msg

    # Should mention over 120 years
    assert "120" in error_msg
