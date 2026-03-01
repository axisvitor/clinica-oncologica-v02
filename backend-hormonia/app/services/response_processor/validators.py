"""
Response validation logic.
"""

import logging
import re
import unicodedata
from datetime import datetime
from typing import Optional, Any

from app.models.flow import PatientFlowState
from app.utils.constants import YES_PATTERNS, NO_PATTERNS

from .models import (
    ResponseValidationResult,
    ResponseType,
    InboundMessage,
    InteractiveResponse,
)

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Validates patient responses against expected contexts."""

    def __init__(self, message_limit: int = 4096, *, lenient_validation: bool = True):
        """
        Initialize response validator.

        Args:
            message_limit: Maximum message length
        """
        self.message_limit = message_limit
        self.lenient_validation = lenient_validation

    def _normalize_text(self, text: str) -> str:
        """Normalize text for validation comparisons."""
        normalized = unicodedata.normalize("NFKD", text or "")
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        normalized = normalized.replace("\u00a0", " ")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _normalize_for_match(self, text: str) -> str:
        """Normalize text for case-insensitive matching."""
        return self._normalize_text(text).casefold()

    def _parse_number(self, text: str) -> Optional[float]:
        """Parse a localized number string into float."""
        cleaned = self._normalize_text(text)
        if not cleaned:
            return None
        cleaned = re.sub(r"[^\d,.-]", "", cleaned)
        if not cleaned:
            return None
        try:
            return float(cleaned.replace(",", "."))
        except ValueError:
            return None

    def _parse_date(self, text: str, formats: Optional[list[str]] = None) -> Optional[datetime]:
        """Parse a date from common formats."""
        cleaned = self._normalize_text(text)
        if not cleaned:
            return None
        # Extract date-like substrings when text includes extra words.
        date_match = re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", cleaned)
        if date_match:
            cleaned = date_match.group(0)
        formats = formats or ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        return None

    def _extract_expected_rules(self, flow_state: Optional[PatientFlowState]) -> dict[str, Any]:
        """Extract expected validation rules from flow state."""
        if not flow_state or not flow_state.state_data:
            return {}

        state_data = flow_state.state_data
        rules: dict[str, Any] = {}

        rules["expected_response_type"] = state_data.get("expected_response_type")
        rules["expected_responses"] = state_data.get("expected_responses", [])
        rules["expected_format"] = (
            state_data.get("expected_response_format")
            or state_data.get("expected_format")
            or state_data.get("response_format")
        )
        rules["min_value"] = state_data.get("min_value") or state_data.get("min")
        rules["max_value"] = state_data.get("max_value") or state_data.get("max")
        rules["response_regex"] = state_data.get("response_regex")
        rules["date_format"] = state_data.get("date_format")

        validation_rules = state_data.get("validation_rules", [])
        for rule in validation_rules:
            if not isinstance(rule, dict):
                continue
            rule_type = rule.get("type")
            value = rule.get("value", {})
            if rule_type in ["range", "scale", "number_range"]:
                rules["min_value"] = value.get("min", rules.get("min_value"))
                rules["max_value"] = value.get("max", rules.get("max_value"))
            elif rule_type in ["date", "date_format"]:
                rules["expected_format"] = "date"
                rules["date_format"] = value.get("format", rules.get("date_format"))
            elif rule_type in ["regex", "pattern"]:
                rules["response_regex"] = value.get("pattern", rules.get("response_regex"))
            elif rule_type in ["yes_no", "boolean"]:
                rules["expected_format"] = "yes_no"

        return rules

    def _normalize_expected_responses(self, expected_responses: list[Any]) -> set[str]:
        """Normalize expected responses for comparison."""
        normalized = set()
        for item in expected_responses:
            if isinstance(item, dict):
                value = item.get("value") or item.get("title") or item.get("id")
            else:
                value = item
            if value is None:
                continue
            normalized.add(self._normalize_for_match(str(value)))
        return normalized

    async def validate_response(
        self,
        inbound_message: InboundMessage,
        response_type: ResponseType,
        flow_state: Optional[PatientFlowState],
    ) -> ResponseValidationResult:
        """
        Validate response based on expected context.

        Args:
            inbound_message: Inbound message data
            response_type: Type of response
            flow_state: Optional current flow state

        Returns:
            Validation result
        """
        try:
            errors = []
            rules = self._extract_expected_rules(flow_state)

            # Basic content validation
            raw_content = inbound_message.content or ""
            normalized_content = self._normalize_text(raw_content)
            if not normalized_content:
                if response_type == ResponseType.MEDIA:
                    media_url = inbound_message.metadata.get("media_url") or inbound_message.metadata.get("url")
                    if not media_url:
                        errors.append("Mensagem de midia sem arquivo")
                else:
                    errors.append("Mensagem vazia")

            # Flow context validation
            expected_responses = rules.get("expected_responses", [])
            if expected_responses:
                normalized_expected = self._normalize_expected_responses(expected_responses)
                if response_type in [
                    ResponseType.BUTTON,
                    ResponseType.QUICK_REPLY,
                    ResponseType.LIST_SELECTION,
                ]:
                    if self._normalize_for_match(inbound_message.content) not in normalized_expected:
                        errors.append("Resposta nao corresponde as opcoes esperadas")
                elif not self.lenient_validation:
                    # Strict validation for text responses
                    if self._normalize_for_match(inbound_message.content) not in normalized_expected:
                        errors.append("Resposta nao corresponde as opcoes esperadas")

            expected_type = rules.get("expected_response_type")
            if expected_type:
                expected_type_value = (
                    expected_type.value if hasattr(expected_type, "value") else str(expected_type)
                )
                if expected_type_value != response_type.value and not (
                    self.lenient_validation and response_type == ResponseType.TEXT
                ):
                    errors.append(
                        f"Tipo de resposta incorreto: esperado {expected_type_value}"
                    )

            # Content length validation
            if len(raw_content) > self.message_limit:
                errors.append("Mensagem longa demais")

            # Media validation
            if response_type == ResponseType.MEDIA:
                media_url = inbound_message.metadata.get("media_url") or inbound_message.metadata.get("url")
                if not media_url and "Mensagem de midia sem arquivo" not in errors:
                    errors.append("Mensagem de midia sem arquivo")

            # Format validation (yes/no, number, date, range)
            expected_format = rules.get("expected_format")
            if expected_format and normalized_content:
                format_key = str(expected_format).lower()
                if format_key in ["yes_no", "sim_nao", "boolean"]:
                    cleaned = re.sub(r"[^\w\s]", "", normalized_content).casefold()
                    if not re.search(YES_PATTERNS, cleaned) and not re.search(NO_PATTERNS, cleaned):
                        if not self.lenient_validation:
                            errors.append("Formato invalido: esperado sim/nao")
                elif format_key in ["number", "numeric", "float", "int", "integer"]:
                    parsed = self._parse_number(normalized_content)
                    if parsed is None:
                        if not self.lenient_validation:
                            errors.append("Formato invalido: esperado numero")
                    else:
                        min_value = rules.get("min_value")
                        max_value = rules.get("max_value")
                        if min_value is not None and parsed < float(min_value):
                            errors.append("Numero abaixo do minimo permitido")
                        if max_value is not None and parsed > float(max_value):
                            errors.append("Numero acima do maximo permitido")
                elif format_key in ["date", "data"]:
                    date_formats = [rules.get("date_format")] if rules.get("date_format") else None
                    parsed_date = self._parse_date(normalized_content, date_formats)
                    if parsed_date is None and not self.lenient_validation:
                        errors.append("Formato invalido: esperado data")
                elif format_key in ["range", "interval", "scale"]:
                    range_match = re.search(
                        r"\b(\d+(?:[.,]\d+)?)\s*(?:-|a|ate)\s*(\d+(?:[.,]\d+)?)\b",
                        normalized_content.casefold(),
                    )
                    if not range_match:
                        if not self.lenient_validation:
                            errors.append("Formato invalido: esperado intervalo")
                    else:
                        start_value = float(range_match.group(1).replace(",", "."))
                        end_value = float(range_match.group(2).replace(",", "."))
                        min_value = rules.get("min_value")
                        max_value = rules.get("max_value")
                        if min_value is not None and (start_value < float(min_value) or end_value < float(min_value)):
                            errors.append("Intervalo abaixo do minimo permitido")
                        if max_value is not None and (start_value > float(max_value) or end_value > float(max_value)):
                            errors.append("Intervalo acima do maximo permitido")

            response_regex = rules.get("response_regex")
            if response_regex and normalized_content:
                if not re.search(response_regex, normalized_content) and not self.lenient_validation:
                    errors.append("Formato invalido para a resposta")

            is_valid = len(errors) == 0
            extracted_value = inbound_message.content if is_valid else None

            return ResponseValidationResult(
                is_valid=is_valid,
                response_type=response_type,
                extracted_value=extracted_value,
                validation_errors=errors,
            )

        except Exception as e:
            logger.error(f"Response validation failed: {e}")
            return ResponseValidationResult(
                is_valid=False,
                response_type=response_type,
                validation_errors=[f"Validation error: {str(e)}"],
            )

    async def validate_interactive_response(
        self, interactive_response: InteractiveResponse, flow_state: PatientFlowState
    ) -> ResponseValidationResult:
        """
        Validate interactive response against flow context.

        Args:
            interactive_response: Interactive response data
            flow_state: Current flow state

        Returns:
            Validation result
        """
        try:
            errors = []
            rules = self._extract_expected_rules(flow_state)

            # Check if response value is provided
            if not interactive_response.response_value:
                errors.append("Mensagem vazia")

            # Validate against expected responses in flow state
            expected_responses = rules.get("expected_responses", [])
            if expected_responses:
                normalized_expected = self._normalize_expected_responses(expected_responses)
                if (
                    self._normalize_for_match(interactive_response.response_value)
                    not in normalized_expected
                ):
                    errors.append("Resposta nao corresponde as opcoes esperadas")

            # Validate response type consistency
            expected_type = rules.get("expected_response_type")
            expected_type_value = (
                expected_type.value if hasattr(expected_type, "value") else str(expected_type)
            ) if expected_type else None
            if expected_type_value and expected_type_value != interactive_response.response_type.value:
                errors.append(
                    f"Tipo de resposta incorreto: esperado {expected_type_value}"
                )

            is_valid = len(errors) == 0

            return ResponseValidationResult(
                is_valid=is_valid,
                response_type=interactive_response.response_type,
                extracted_value=interactive_response.response_value
                if is_valid
                else None,
                validation_errors=errors,
            )

        except Exception as e:
            logger.error(f"Interactive response validation failed: {e}")
            return ResponseValidationResult(
                is_valid=False,
                response_type=interactive_response.response_type,
                validation_errors=[f"Validation error: {str(e)}"],
            )
