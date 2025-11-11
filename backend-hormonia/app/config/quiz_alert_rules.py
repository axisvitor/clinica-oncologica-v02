"""
Quiz Alert Rules Configuration for Hormonia Backend System.

This module defines the alert rules that automatically evaluate quiz responses
and generate alerts when risk thresholds are exceeded.

Sprint 2 - Week 1, Task 3: Automatic Alert Evaluation
"""
from enum import Enum
from typing import Dict, Any, List, Callable, Optional
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels for quiz response evaluation."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class QuizAlertRule:
    """
    Represents a single alert rule for quiz response evaluation.

    Each rule consists of:
    - rule_id: Unique identifier for the rule
    - name: Human-readable name
    - description: Detailed description of what triggers the rule
    - severity: AlertSeverity level
    - condition: Callable that evaluates responses
    - message_template: Template for generating alert messages
    """

    def __init__(
        self,
        rule_id: str,
        name: str,
        description: str,
        severity: AlertSeverity,
        condition: Callable[[Dict[str, Any]], bool],
        message_template: str,
        recommendation: str = ""
    ):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.severity = severity
        self.condition = condition
        self.message_template = message_template
        self.recommendation = recommendation

    def evaluate(self, responses: Dict[str, Any]) -> bool:
        """
        Evaluate if rule is triggered by the given responses.

        Args:
            responses: Dictionary of question_id -> response_value mappings

        Returns:
            True if the rule condition is met, False otherwise
        """
        try:
            return self.condition(responses)
        except Exception as e:
            logger.error(f"Error evaluating rule {self.rule_id}: {e}", exc_info=True)
            return False

    def generate_message(self, responses: Dict[str, Any]) -> str:
        """
        Generate alert message from template and responses.

        Args:
            responses: Dictionary of question_id -> response_value mappings

        Returns:
            Formatted alert message
        """
        try:
            return self.message_template.format(**responses)
        except KeyError as e:
            logger.warning(f"Missing key in message template for rule {self.rule_id}: {e}")
            return self.message_template
        except Exception as e:
            logger.error(f"Error generating message for rule {self.rule_id}: {e}", exc_info=True)
            return self.description


# Helper functions for complex rule conditions
def _get_numeric_value(responses: Dict[str, Any], key: str, default: float = 0.0) -> float:
    """Safely extract numeric value from responses."""
    try:
        value = responses.get(key, default)
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _get_bool_value(responses: Dict[str, Any], key: str, default: bool = False) -> bool:
    """Safely extract boolean value from responses."""
    value = responses.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('yes', 'sim', 'true', '1', 'y', 's')
    return bool(value)


def _count_high_severity_symptoms(responses: Dict[str, Any], threshold: float = 7.0) -> int:
    """Count number of symptoms rated above threshold."""
    count = 0
    # Look for scale-type responses (typically pain_scale, nausea_scale, fatigue_scale, etc.)
    for key, value in responses.items():
        if key.endswith('_scale') or key.endswith('_level') or key.endswith('_intensity'):
            try:
                if float(value) >= threshold:
                    count += 1
            except (ValueError, TypeError):
                continue
    return count


# Define alert rules for quiz response evaluation
QUIZ_ALERT_RULES: List[QuizAlertRule] = [
    # CRITICAL ALERTS
    QuizAlertRule(
        rule_id="pain_score_critical",
        name="Dor Crítica",
        description="Paciente relata dor intensa com escala ≥7",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: _get_numeric_value(r, "pain_scale") >= 7 or _get_numeric_value(r, "pain_level") >= 7,
        message_template="Paciente relatou dor intensa (nível {pain_scale}/10). Intervenção médica urgente recomendada.",
        recommendation="Avaliar necessidade de analgesia imediata e consulta médica urgente"
    ),

    QuizAlertRule(
        rule_id="fever_with_chills",
        name="Febre com Calafrios",
        description="Paciente apresenta febre e calafrios simultaneamente",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: _get_bool_value(r, "has_fever") and _get_bool_value(r, "has_chills"),
        message_template="Febre com calafrios relatados. Possível infecção ou neutropenia febril.",
        recommendation="Avaliação médica urgente para investigar possível neutropenia febril"
    ),

    QuizAlertRule(
        rule_id="severe_bleeding",
        name="Sangramento Severo",
        description="Paciente relata sangramento severo ou hemorragia",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: _get_bool_value(r, "severe_bleeding") or _get_bool_value(r, "hemorrhage"),
        message_template="Sangramento severo relatado. Requer avaliação médica imediata.",
        recommendation="Encaminhar para emergência imediatamente"
    ),

    QuizAlertRule(
        rule_id="multiple_severe_symptoms",
        name="Múltiplos Sintomas Severos",
        description="Paciente apresenta ≥3 sintomas com severidade ≥7",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: _count_high_severity_symptoms(r, threshold=7.0) >= 3,
        message_template="Múltiplos sintomas severos detectados (≥3 sintomas com nível ≥7). Quadro clínico preocupante.",
        recommendation="Avaliação médica completa e possível internação"
    ),

    QuizAlertRule(
        rule_id="respiratory_distress",
        name="Desconforto Respiratório Severo",
        description="Paciente relata dificuldade respiratória severa",
        severity=AlertSeverity.CRITICAL,
        condition=lambda r: _get_numeric_value(r, "breathing_difficulty") >= 8 or _get_bool_value(r, "severe_dyspnea"),
        message_template="Desconforto respiratório severo relatado (nível {breathing_difficulty}/10).",
        recommendation="Avaliação médica urgente e possível oxigenoterapia"
    ),

    # WARNING ALERTS
    QuizAlertRule(
        rule_id="prolonged_nausea",
        name="Náusea Prolongada",
        description="Náusea ou vômitos persistindo por ≥4 dias",
        severity=AlertSeverity.WARNING,
        condition=lambda r: _get_numeric_value(r, "nausea_days") >= 4 or _get_numeric_value(r, "vomiting_days") >= 4,
        message_template="Náusea/vômitos prolongados por {nausea_days} dias. Risco de desidratação.",
        recommendation="Avaliar hidratação e considerar antieméticos"
    ),

    QuizAlertRule(
        rule_id="significant_weight_loss",
        name="Perda Ponderal Significativa",
        description="Perda de peso ≥5% no último mês",
        severity=AlertSeverity.WARNING,
        condition=lambda r: _get_numeric_value(r, "weight_loss_percent") >= 5,
        message_template="Perda de peso significativa: {weight_loss_percent}% no último mês.",
        recommendation="Avaliação nutricional e suporte nutricional"
    ),

    QuizAlertRule(
        rule_id="severe_fatigue",
        name="Fadiga Severa",
        description="Fadiga impedindo atividades diárias normais",
        severity=AlertSeverity.WARNING,
        condition=lambda r: _get_numeric_value(r, "fatigue_level") >= 8 or _get_numeric_value(r, "fatigue_scale") >= 8,
        message_template="Fadiga severa (nível {fatigue_level}/10) impedindo atividades diárias.",
        recommendation="Avaliar causas reversíveis e considerar suporte"
    ),

    QuizAlertRule(
        rule_id="persistent_diarrhea",
        name="Diarreia Persistente",
        description="Diarreia por ≥3 dias ou >5 episódios/dia",
        severity=AlertSeverity.WARNING,
        condition=lambda r: _get_numeric_value(r, "diarrhea_days") >= 3 or _get_numeric_value(r, "diarrhea_episodes_per_day") > 5,
        message_template="Diarreia persistente: {diarrhea_days} dias ou {diarrhea_episodes_per_day} episódios/dia.",
        recommendation="Avaliar hidratação e considerar antidiarreicos"
    ),

    QuizAlertRule(
        rule_id="moderate_pain",
        name="Dor Moderada Persistente",
        description="Dor com escala 5-6 necessitando atenção",
        severity=AlertSeverity.WARNING,
        condition=lambda r: 5 <= _get_numeric_value(r, "pain_scale") < 7 or 5 <= _get_numeric_value(r, "pain_level") < 7,
        message_template="Dor moderada persistente (nível {pain_scale}/10). Pode requerer ajuste de analgesia.",
        recommendation="Avaliar eficácia do esquema analgésico atual"
    ),

    QuizAlertRule(
        rule_id="oral_mucositis",
        name="Mucosite Oral Significativa",
        description="Mucosite oral interferindo na alimentação",
        severity=AlertSeverity.WARNING,
        condition=lambda r: _get_numeric_value(r, "mucositis_grade") >= 2 or _get_bool_value(r, "difficulty_eating"),
        message_template="Mucosite oral grau {mucositis_grade} ou dificuldade de alimentação relatada.",
        recommendation="Cuidados orais intensivos e avaliação nutricional"
    ),

    QuizAlertRule(
        rule_id="peripheral_neuropathy",
        name="Neuropatia Periférica",
        description="Formigamento ou dormência significativos",
        severity=AlertSeverity.WARNING,
        condition=lambda r: _get_numeric_value(r, "neuropathy_scale") >= 6 or _get_bool_value(r, "severe_tingling"),
        message_template="Neuropatia periférica significativa (nível {neuropathy_scale}/10).",
        recommendation="Avaliar dose de quimioterapia e considerar neuropatia"
    ),

    # INFO ALERTS
    QuizAlertRule(
        rule_id="mild_symptoms",
        name="Sintomas Leves",
        description="Sintomas leves que requerem monitoramento",
        severity=AlertSeverity.INFO,
        condition=lambda r: _count_high_severity_symptoms(r, threshold=3.0) >= 2,
        message_template="Múltiplos sintomas leves detectados. Monitoramento recomendado.",
        recommendation="Acompanhamento de rotina e orientações ao paciente"
    ),

    QuizAlertRule(
        rule_id="appetite_changes",
        name="Alteração de Apetite",
        description="Mudanças significativas no apetite",
        severity=AlertSeverity.INFO,
        condition=lambda r: _get_bool_value(r, "decreased_appetite") or _get_numeric_value(r, "appetite_change") >= 3,
        message_template="Alteração de apetite relatada. Monitorar estado nutricional.",
        recommendation="Orientações nutricionais e acompanhamento"
    ),

    QuizAlertRule(
        rule_id="sleep_disturbance",
        name="Distúrbio do Sono",
        description="Dificuldades para dormir ou insônia",
        severity=AlertSeverity.INFO,
        condition=lambda r: _get_bool_value(r, "sleep_problems") or _get_numeric_value(r, "sleep_quality") <= 3,
        message_template="Distúrbio do sono relatado. Qualidade do sono: {sleep_quality}/10.",
        recommendation="Avaliar higiene do sono e considerar suporte"
    ),

    QuizAlertRule(
        rule_id="anxiety_or_depression",
        name="Ansiedade/Depressão",
        description="Sinais de ansiedade ou depressão",
        severity=AlertSeverity.INFO,
        condition=lambda r: _get_numeric_value(r, "anxiety_level") >= 6 or _get_numeric_value(r, "depression_score") >= 6,
        message_template="Sinais de ansiedade (nível {anxiety_level}/10) ou depressão detectados.",
        recommendation="Considerar suporte psicológico e avaliação mental"
    ),
]


def get_rules_by_severity(severity: AlertSeverity) -> List[QuizAlertRule]:
    """
    Get all rules for a specific severity level.

    Args:
        severity: AlertSeverity to filter by

    Returns:
        List of rules matching the severity
    """
    return [rule for rule in QUIZ_ALERT_RULES if rule.severity == severity]


def get_rule_by_id(rule_id: str) -> Optional[QuizAlertRule]:
    """
    Get a specific rule by its ID.

    Args:
        rule_id: Unique identifier of the rule

    Returns:
        QuizAlertRule if found, None otherwise
    """
    for rule in QUIZ_ALERT_RULES:
        if rule.rule_id == rule_id:
            return rule
    return None


def get_all_rule_ids() -> List[str]:
    """Get all rule IDs."""
    return [rule.rule_id for rule in QUIZ_ALERT_RULES]


def get_rules_summary() -> Dict[str, Any]:
    """
    Get summary of all configured alert rules.

    Returns:
        Dictionary with rule statistics and details
    """
    return {
        "total_rules": len(QUIZ_ALERT_RULES),
        "by_severity": {
            "critical": len(get_rules_by_severity(AlertSeverity.CRITICAL)),
            "warning": len(get_rules_by_severity(AlertSeverity.WARNING)),
            "info": len(get_rules_by_severity(AlertSeverity.INFO))
        },
        "rule_ids": get_all_rule_ids()
    }
