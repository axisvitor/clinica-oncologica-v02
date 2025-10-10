"""
Flow Pre-flight Validation Service

Validates patient data completeness before starting flows to prevent
incorrect treatment monitoring due to missing or invalid data.

Critical P7 Fix: Ensures flows don't start with incomplete patient information.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, date
import re
import logging
from uuid import UUID

from app.models.patient import Patient, FlowState
from app.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ValidationRule:
    """Base class for validation rules."""

    def __init__(self, field_name: str, severity: str = "error"):
        """
        Initialize validation rule.

        Args:
            field_name: Name of the field being validated
            severity: 'error' (blocks flow) or 'warning' (allows flow)
        """
        self.field_name = field_name
        self.severity = severity

    def validate(self, value: Any, patient: Patient) -> Optional[Dict[str, str]]:
        """
        Validate a value.

        Args:
            value: Value to validate
            patient: Patient instance for context

        Returns:
            Dict with error details if validation fails, None if passes
        """
        raise NotImplementedError("Subclasses must implement validate()")


class RequiredFieldRule(ValidationRule):
    """Validates that a field is not empty."""

    def __init__(self, field_name: str, display_name: str, severity: str = "error"):
        super().__init__(field_name, severity)
        self.display_name = display_name

    def validate(self, value: Any, patient: Patient) -> Optional[Dict[str, str]]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return {
                'field': self.field_name,
                'message': f"{self.display_name} não informado",
                'severity': self.severity,
                'code': 'REQUIRED_FIELD_MISSING'
            }
        return None


class CPFValidationRule(ValidationRule):
    """Validates Brazilian CPF format."""

    def __init__(self):
        super().__init__('cpf', 'error')

    def validate(self, value: Any, patient: Patient) -> Optional[Dict[str, str]]:
        if not value:
            return {
                'field': 'cpf',
                'message': 'CPF não informado',
                'severity': 'error',
                'code': 'CPF_MISSING'
            }

        # Extract only digits
        cpf_digits = ''.join(filter(str.isdigit, str(value)))

        # Check length
        if len(cpf_digits) != 11:
            return {
                'field': 'cpf',
                'message': f'CPF com formato inválido (deve ter 11 dígitos): {value}',
                'severity': 'error',
                'code': 'CPF_INVALID_LENGTH',
                'actual_length': len(cpf_digits)
            }

        # Check for known invalid CPFs (all same digit)
        if len(set(cpf_digits)) == 1:
            return {
                'field': 'cpf',
                'message': f'CPF inválido (todos os dígitos iguais): {value}',
                'severity': 'error',
                'code': 'CPF_INVALID_FORMAT'
            }

        # Validate CPF checksum
        if not self._validate_cpf_checksum(cpf_digits):
            return {
                'field': 'cpf',
                'message': f'CPF com dígitos verificadores inválidos: {value}',
                'severity': 'error',
                'code': 'CPF_INVALID_CHECKSUM'
            }

        return None

    def _validate_cpf_checksum(self, cpf: str) -> bool:
        """
        Validate CPF checksum digits.

        Args:
            cpf: 11-digit CPF string

        Returns:
            True if checksum is valid
        """
        # Calculate first digit
        sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digit1 = 11 - (sum1 % 11)
        digit1 = 0 if digit1 > 9 else digit1

        # Calculate second digit
        sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digit2 = 11 - (sum2 % 11)
        digit2 = 0 if digit2 > 9 else digit2

        return int(cpf[9]) == digit1 and int(cpf[10]) == digit2


class PhoneValidationRule(ValidationRule):
    """Validates Brazilian phone number format."""

    def __init__(self):
        super().__init__('phone', 'error')

    def validate(self, value: Any, patient: Patient) -> Optional[Dict[str, str]]:
        if not value:
            return {
                'field': 'phone',
                'message': 'Telefone não informado',
                'severity': 'error',
                'code': 'PHONE_MISSING'
            }

        # Extract only digits
        phone_digits = ''.join(filter(str.isdigit, str(value)))

        # Brazilian phones: 10 digits (landline) or 11 digits (mobile with 9)
        if len(phone_digits) < 10 or len(phone_digits) > 11:
            return {
                'field': 'phone',
                'message': f'Telefone com formato inválido (deve ter 10-11 dígitos): {value}',
                'severity': 'error',
                'code': 'PHONE_INVALID_LENGTH',
                'actual_length': len(phone_digits)
            }

        # Validate area code (DDD)
        area_code = phone_digits[:2]
        valid_area_codes = [
            '11', '12', '13', '14', '15', '16', '17', '18', '19',  # SP
            '21', '22', '24',  # RJ
            '27', '28',  # ES
            '31', '32', '33', '34', '35', '37', '38',  # MG
            '41', '42', '43', '44', '45', '46',  # PR
            '47', '48', '49',  # SC
            '51', '53', '54', '55',  # RS
            '61',  # DF
            '62', '64',  # GO
            '63',  # TO
            '65', '66',  # MT
            '67',  # MS
            '68',  # AC
            '69',  # RO
            '71', '73', '74', '75', '77',  # BA
            '79',  # SE
            '81', '87',  # PE
            '82',  # AL
            '83',  # PB
            '84',  # RN
            '85', '88',  # CE
            '86', '89',  # PI
            '91', '93', '94',  # PA
            '92', '97',  # AM
            '95',  # RR
            '96',  # AP
            '98', '99',  # MA
        ]

        if area_code not in valid_area_codes:
            return {
                'field': 'phone',
                'message': f'Telefone com código de área (DDD) inválido: {area_code}',
                'severity': 'warning',  # Warning only, as new area codes may be added
                'code': 'PHONE_INVALID_AREA_CODE',
                'area_code': area_code
            }

        return None


class TreatmentTypeValidationRule(ValidationRule):
    """Validates treatment type is specified."""

    VALID_TREATMENT_TYPES = [
        'hormone_therapy',
        'chemotherapy',
        'radiotherapy',
        'immunotherapy',
        'targeted_therapy',
        'surgery',
        'palliative_care'
    ]

    def __init__(self):
        super().__init__('treatment_type', 'error')

    def validate(self, value: Any, patient: Patient) -> Optional[Dict[str, str]]:
        if not value:
            return {
                'field': 'treatment_type',
                'message': 'Tipo de tratamento não informado',
                'severity': 'error',
                'code': 'TREATMENT_TYPE_MISSING'
            }

        # Validate against known types (warning only for extensibility)
        if value not in self.VALID_TREATMENT_TYPES:
            return {
                'field': 'treatment_type',
                'message': f'Tipo de tratamento não reconhecido: {value}',
                'severity': 'warning',
                'code': 'TREATMENT_TYPE_UNKNOWN',
                'provided_value': value,
                'valid_types': self.VALID_TREATMENT_TYPES
            }

        return None


class DateValidationRule(ValidationRule):
    """Validates date fields are reasonable."""

    def __init__(self, field_name: str, display_name: str,
                 allow_future: bool = False, allow_past: bool = True,
                 severity: str = "warning"):
        super().__init__(field_name, severity)
        self.display_name = display_name
        self.allow_future = allow_future
        self.allow_past = allow_past

    def validate(self, value: Any, patient: Patient) -> Optional[Dict[str, str]]:
        if value is None:
            return None  # Optional date field

        # Convert to date if datetime
        if isinstance(value, datetime):
            value = value.date()

        if not isinstance(value, date):
            return {
                'field': self.field_name,
                'message': f'{self.display_name} com formato inválido',
                'severity': self.severity,
                'code': 'DATE_INVALID_FORMAT'
            }

        today = date.today()

        # Check future dates
        if not self.allow_future and value > today:
            return {
                'field': self.field_name,
                'message': f'{self.display_name} não pode ser no futuro: {value}',
                'severity': self.severity,
                'code': 'DATE_IN_FUTURE',
                'provided_date': str(value)
            }

        # Check very old dates (likely data entry errors)
        if self.allow_past and value < date(1900, 1, 1):
            return {
                'field': self.field_name,
                'message': f'{self.display_name} com valor muito antigo: {value}',
                'severity': self.severity,
                'code': 'DATE_TOO_OLD',
                'provided_date': str(value)
            }

        # Check birth date specific validations
        if self.field_name == 'birth_date':
            age_years = (today - value).days / 365.25
            if age_years > 150:
                return {
                    'field': self.field_name,
                    'message': f'Data de nascimento implica idade improvável: {age_years:.0f} anos',
                    'severity': self.severity,
                    'code': 'DATE_IMPLAUSIBLE_AGE',
                    'calculated_age': int(age_years)
                }

        return None


class FlowPreflightValidator:
    """
    Pre-flight validation for patient flow starts.

    Ensures all required patient data is present and valid before
    initiating a treatment flow to prevent monitoring failures.
    """

    def __init__(self):
        """Initialize validator with validation rules."""
        self.critical_rules: List[ValidationRule] = [
            CPFValidationRule(),
            PhoneValidationRule(),
            TreatmentTypeValidationRule(),
        ]

        self.recommended_rules: List[ValidationRule] = [
            RequiredFieldRule('name', 'Nome do paciente', severity='warning'),
            DateValidationRule('treatment_start_date', 'Data de início do tratamento',
                             allow_future=True, severity='warning'),
            DateValidationRule('birth_date', 'Data de nascimento', severity='warning'),
            RequiredFieldRule('diagnosis', 'Diagnóstico', severity='warning'),
        ]

    def validate_patient_for_flow(
        self,
        patient: Patient,
        flow_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate patient data before starting a flow.

        Args:
            patient: Patient instance to validate
            flow_type: Optional flow type for flow-specific validation

        Returns:
            Validation result dictionary with:
                - valid: Boolean indicating if validation passed
                - errors: List of critical errors (blocks flow start)
                - warnings: List of warnings (allows flow start)
                - patient_id: Patient UUID
                - checked_fields: Fields that were validated

        Raises:
            ValidationError: If critical validation fails
        """
        errors = []
        warnings = []

        # Run critical validations
        for rule in self.critical_rules:
            value = getattr(patient, rule.field_name, None)
            result = rule.validate(value, patient)
            if result:
                errors.append(result)

        # Run recommended validations
        for rule in self.recommended_rules:
            value = getattr(patient, rule.field_name, None)
            result = rule.validate(value, patient)
            if result:
                warnings.append(result)

        # Flow-specific validations
        if flow_type:
            flow_specific_errors = self._validate_flow_specific_requirements(
                patient, flow_type
            )
            errors.extend(flow_specific_errors)

        # Build validation result
        validation_result = {
            'valid': len(errors) == 0,
            'patient_id': str(patient.id),
            'patient_name': patient.name,
            'errors': errors,
            'warnings': warnings,
            'checked_fields': {
                'critical': [rule.field_name for rule in self.critical_rules],
                'recommended': [rule.field_name for rule in self.recommended_rules]
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        # Log validation results
        if errors:
            error_summary = '; '.join([f"{e['field']}: {e['message']}" for e in errors])
            logger.error(
                f"Patient {patient.id} failed flow pre-flight validation. "
                f"Errors: {error_summary}"
            )

        if warnings:
            warning_summary = '; '.join([f"{w['field']}: {w['message']}" for w in warnings])
            logger.warning(
                f"Patient {patient.id} has validation warnings. "
                f"Warnings: {warning_summary}"
            )

        # Raise exception if critical errors found
        if errors:
            error_messages = [f"{err['field']}: {err['message']}" for err in errors]
            raise ValidationError(
                f"Dados do paciente incompletos ou inválidos. "
                f"Corrija os seguintes erros antes de iniciar o fluxo: "
                f"{'; '.join(error_messages)}",
                details=validation_result
            )

        return validation_result

    def _validate_flow_specific_requirements(
        self,
        patient: Patient,
        flow_type: str
    ) -> List[Dict[str, str]]:
        """
        Validate flow-type specific requirements.

        Args:
            patient: Patient instance
            flow_type: Flow type identifier

        Returns:
            List of error dictionaries
        """
        errors = []

        # Hormone therapy specific validations
        if 'hormona' in flow_type.lower() or 'hormone' in flow_type.lower():
            if not patient.treatment_start_date:
                errors.append({
                    'field': 'treatment_start_date',
                    'message': 'Data de início do tratamento é obrigatória para terapia hormonal',
                    'severity': 'error',
                    'code': 'HORMONE_THERAPY_START_DATE_REQUIRED',
                    'flow_type': flow_type
                })

        # Chemotherapy specific validations
        if 'quimio' in flow_type.lower() or 'chemo' in flow_type.lower():
            if not patient.diagnosis:
                errors.append({
                    'field': 'diagnosis',
                    'message': 'Diagnóstico é obrigatório para quimioterapia',
                    'severity': 'error',
                    'code': 'CHEMOTHERAPY_DIAGNOSIS_REQUIRED',
                    'flow_type': flow_type
                })

        return errors

    def validate_multiple_patients(
        self,
        patients: List[Patient],
        flow_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate multiple patients for batch flow operations.

        Args:
            patients: List of Patient instances
            flow_type: Optional flow type

        Returns:
            Summary of validation results for all patients
        """
        results = {
            'total_patients': len(patients),
            'valid_patients': 0,
            'invalid_patients': 0,
            'patients_with_warnings': 0,
            'validation_details': []
        }

        for patient in patients:
            try:
                validation = self.validate_patient_for_flow(patient, flow_type)
                results['valid_patients'] += 1
                if validation['warnings']:
                    results['patients_with_warnings'] += 1
                results['validation_details'].append({
                    'patient_id': str(patient.id),
                    'patient_name': patient.name,
                    'valid': True,
                    'warnings': validation['warnings']
                })
            except ValidationError as e:
                results['invalid_patients'] += 1
                results['validation_details'].append({
                    'patient_id': str(patient.id),
                    'patient_name': patient.name,
                    'valid': False,
                    'errors': e.details.get('errors', []) if hasattr(e, 'details') else []
                })

        return results


# Global validator instance
_validator_instance = None


def get_flow_validator() -> FlowPreflightValidator:
    """
    Get global flow validator instance (singleton).

    Returns:
        FlowPreflightValidator instance
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = FlowPreflightValidator()
    return _validator_instance
