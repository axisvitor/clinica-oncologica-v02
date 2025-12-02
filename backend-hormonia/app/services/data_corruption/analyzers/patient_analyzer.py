"""
Patient Analyzer
Analyzes patient-specific corruption patterns.
"""
import logging
from typing import Optional
from .base import BaseAnalyzer
from .field_analyzer import FieldAnalyzer
from .temporal_analyzer import TemporalAnalyzer
from .encoding_analyzer import EncodingAnalyzer
from ..validators import FormatValidator

logger = logging.getLogger(__name__)


class PatientAnalyzer(BaseAnalyzer):
    """Analyzes patient data for corruption"""

    def __init__(self):
        super().__init__()
        self.field_analyzer = FieldAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        self.encoding_analyzer = EncodingAnalyzer()
        self.format_validator = FormatValidator()

    async def analyze(self, patient) -> list:
        """Analyze patient for corruption patterns"""
        try:
            # Analyze name field
            await self.field_analyzer.analyze_text_field(patient.name, 'patient.name', patient.id)

            # Analyze email field
            if patient.email:
                self.format_validator.validate_email(patient.email, 'patient.email', patient.id)

            # Analyze phone field
            self.format_validator.validate_phone(patient.phone, 'patient.phone', patient.id)

            # Analyze metadata corruption
            if patient.patient_data:
                await self.field_analyzer.analyze_metadata(patient.patient_data, 'patient.metadata', patient.id)

            # Analyze temporal consistency
            await self.temporal_analyzer.analyze_patient_temporal(patient)

            # Analyze encoding issues
            fields_to_check = [
                ('name', patient.name),
                ('email', patient.email)
            ]
            for field_name, field_value in fields_to_check:
                if field_value:
                    await self.encoding_analyzer.check_encoding(field_value, f"patient.{field_name}", patient.id)

            # Collect all patterns
            all_patterns = (
                self.field_analyzer.corruption_patterns +
                self.temporal_analyzer.corruption_patterns +
                self.encoding_analyzer.corruption_patterns +
                self.format_validator.corruption_patterns
            )

            return all_patterns

        except Exception as e:
            logger.error(f"Patient analysis failed for patient {patient.id}: {e}")
            return []
