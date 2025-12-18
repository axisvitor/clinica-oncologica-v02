"""
Pydantic Validation Error Internationalization

Utilities for translating Pydantic validation errors to the current locale.

Usage:
    from app.utils.pydantic_i18n import translate_pydantic_errors
    from pydantic import ValidationError

    try:
        patient = PatientCreate(**data)
    except ValidationError as e:
        translated_errors = translate_pydantic_errors(e)
        raise HTTPException(status_code=422, detail=translated_errors)
"""

from pydantic import ValidationError
from typing import Dict, List, Any
import logging

from app.config.i18n import t

logger = logging.getLogger(__name__)


# Map Pydantic error types to translation keys
PYDANTIC_ERROR_TYPE_MAP = {
    # Missing/required field errors
    "value_error.missing": "errors.validation.required_field",
    "type_error.none.not_allowed": "errors.validation.required_field",
    # Type errors
    "type_error.integer": "errors.validation.invalid_format",
    "type_error.float": "errors.validation.invalid_format",
    "type_error.string": "errors.validation.invalid_format",
    "type_error.boolean": "errors.validation.invalid_format",
    "type_error.uuid": "errors.validation.invalid_uuid",
    # String validation
    "value_error.str.regex": "errors.validation.invalid_format",
    "value_error.email": "errors.validation.invalid_email",
    # Number validation
    "value_error.number.not_gt": "errors.validation.min_value",
    "value_error.number.not_ge": "errors.validation.min_value",
    "value_error.number.not_lt": "errors.validation.max_value",
    "value_error.number.not_le": "errors.validation.max_value",
    # String length validation
    "value_error.any_str.min_length": "errors.validation.min_length",
    "value_error.any_str.max_length": "errors.validation.max_length",
    # List validation
    "value_error.list.min_items": "errors.validation.min_value",
    "value_error.list.max_items": "errors.validation.max_value",
    # Enum validation
    "type_error.enum": "errors.validation.invalid_enum",
    # Date/datetime validation
    "value_error.date": "errors.validation.invalid_date",
    "value_error.datetime": "errors.validation.invalid_date",
    # Generic validation error
    "value_error": "errors.validation.value_error",
}


def translate_pydantic_errors(exc: ValidationError) -> Dict[str, Any]:
    """
    Translate Pydantic validation errors to current locale.

    Args:
        exc: Pydantic ValidationError exception

    Returns:
        Dictionary with translated error messages

    Example:
        {
            "errors": [
                {
                    "field": "email",
                    "message": "Email inválido",
                    "type": "value_error.email"
                },
                {
                    "field": "name",
                    "message": "O campo 'name' é obrigatório",
                    "type": "value_error.missing"
                }
            ]
        }
    """
    errors = []

    for error in exc.errors():
        # Extract field path
        field = ".".join(str(loc) for loc in error["loc"])

        # Get error type
        error_type = error["type"]

        # Get translation key for error type
        translation_key = PYDANTIC_ERROR_TYPE_MAP.get(error_type)

        if not translation_key:
            # Check for partial match (e.g., 'value_error.number.not_gt' → 'value_error')
            for key_prefix in PYDANTIC_ERROR_TYPE_MAP.keys():
                if error_type.startswith(key_prefix):
                    translation_key = PYDANTIC_ERROR_TYPE_MAP[key_prefix]
                    break

        # If still no translation key, use generic validation error
        if not translation_key:
            translation_key = "errors.validation.value_error"

        # Extract constraint values from error context
        ctx = error.get("ctx", {})

        # Build translation parameters
        params = {"field": field, **ctx}

        # Handle specific error types that need context
        if "min_length" in error_type or "max_length" in error_type:
            if "limit_value" in ctx:
                if "min" in error_type:
                    params["min"] = ctx["limit_value"]
                else:
                    params["max"] = ctx["limit_value"]

        if "enum" in error_type:
            if "enum_values" in ctx:
                params["allowed"] = ", ".join(str(v) for v in ctx["enum_values"])
            params["value"] = error.get("input", "")

        # Translate the error message
        try:
            message = t(translation_key, **params)
        except Exception as e:
            logger.error(f"Error translating Pydantic error: {e}")
            # Fallback to original error message
            message = error["msg"]

        errors.append(
            {
                "field": field,
                "message": message,
                "type": error_type,
                "input": error.get("input"),
            }
        )

    return {"errors": errors}


def format_validation_error_response(exc: ValidationError) -> Dict[str, Any]:
    """
    Format Pydantic validation error as API response.

    Args:
        exc: Pydantic ValidationError exception

    Returns:
        Formatted error response with translated messages

    Example:
        {
            "detail": "Validation failed",
            "errors": [
                {
                    "field": "email",
                    "message": "Email inválido",
                    "type": "value_error.email"
                }
            ]
        }
    """
    translated = translate_pydantic_errors(exc)

    return {
        "detail": t("errors.validation.value_error", message="Validation failed"),
        **translated,
    }


def get_first_error_message(exc: ValidationError) -> str:
    """
    Get first error message from Pydantic validation error.

    Useful for simple error responses that only show the first error.

    Args:
        exc: Pydantic ValidationError exception

    Returns:
        First translated error message
    """
    translated = translate_pydantic_errors(exc)
    errors = translated.get("errors", [])

    if errors:
        return errors[0]["message"]

    return t("errors.validation.value_error", message="Validation failed")


def translate_field_errors(
    errors: List[Dict[str, Any]], field_map: Dict[str, str] = None
) -> List[Dict[str, Any]]:
    """
    Translate field names in error messages using a field map.

    Useful for translating field names to user-friendly labels.

    Args:
        errors: List of error dictionaries
        field_map: Mapping of field names to translated labels
            Example: {'birth_date': 'Data de Nascimento', 'cpf': 'CPF'}

    Returns:
        List of errors with translated field names
    """
    if not field_map:
        return errors

    translated_errors = []

    for error in errors:
        field = error.get("field", "")

        # Replace field name with translated label
        if field in field_map:
            error = error.copy()
            error["field_label"] = field_map[field]

            # Also update message if it contains the field name
            message = error.get("message", "")
            if field in message:
                message = message.replace(field, field_map[field])
                error["message"] = message

        translated_errors.append(error)

    return translated_errors


# Portuguese field name translations (common fields)
PT_BR_FIELD_MAP = {
    "name": "Nome",
    "email": "Email",
    "phone": "Telefone",
    "cpf": "CPF",
    "birth_date": "Data de Nascimento",
    "password": "Senha",
    "confirm_password": "Confirmação de Senha",
    "address": "Endereço",
    "city": "Cidade",
    "state": "Estado",
    "zip_code": "CEP",
    "treatment_type": "Tipo de Tratamento",
    "diagnosis": "Diagnóstico",
    "doctor_notes": "Observações do Médico",
    "treatment_start_date": "Data de Início do Tratamento",
    "treatment_phase": "Fase do Tratamento",
}

# English field name translations (common fields)
EN_US_FIELD_MAP = {
    "name": "Name",
    "email": "Email",
    "phone": "Phone",
    "cpf": "CPF",
    "birth_date": "Birth Date",
    "password": "Password",
    "confirm_password": "Password Confirmation",
    "address": "Address",
    "city": "City",
    "state": "State",
    "zip_code": "ZIP Code",
    "treatment_type": "Treatment Type",
    "diagnosis": "Diagnosis",
    "doctor_notes": "Doctor Notes",
    "treatment_start_date": "Treatment Start Date",
    "treatment_phase": "Treatment Phase",
}
