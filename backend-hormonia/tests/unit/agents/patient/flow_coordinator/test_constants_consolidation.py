"""Tests for canonical flow constants and cycle number consolidation."""

from app.agents.patient.flow_coordinator.constants import (
    compute_cycle_number,
    resolve_flow_type_and_day,
)
from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy
from app.utils.template_variables import TemplateVariableProcessor


def test_compute_cycle_number_pre_monthly_phase() -> None:
    for day in range(0, 45):
        assert compute_cycle_number(day) == (0, day)


def test_compute_cycle_number_first_cycle() -> None:
    assert compute_cycle_number(45) == (1, 1)
    assert compute_cycle_number(74) == (1, 30)

    for day in range(45, 75):
        _, day_in_cycle = compute_cycle_number(day)
        assert day_in_cycle == (day - 45) + 1


def test_compute_cycle_number_second_cycle() -> None:
    assert compute_cycle_number(75) == (2, 1)


def test_compute_cycle_number_boundary_day_45() -> None:
    assert compute_cycle_number(45) == (1, 1)


def test_compute_cycle_number_boundary_day_74() -> None:
    assert compute_cycle_number(74) == (1, 30)


def test_quiz_trigger_policy_delegates_to_canonical() -> None:
    assert QuizTriggerPolicy.calculate_monthly_cycle(50) == compute_cycle_number(50)


def test_template_variables_uses_canonical_constants() -> None:
    assert not hasattr(TemplateVariableProcessor, "MONTHLY_PHASE_START_DAY")


def test_resolve_flow_type_and_day_consistency() -> None:
    for day in range(46, 76):
        flow_type, cycle_day = resolve_flow_type_and_day(day)
        _, canonical_day = compute_cycle_number(day)
        assert flow_type == "quiz_mensal"
        assert cycle_day == canonical_day
