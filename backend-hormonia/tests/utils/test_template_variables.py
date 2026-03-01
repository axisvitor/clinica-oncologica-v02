from datetime import datetime, timedelta

from app.utils.template_variables import TemplateVariableProcessor


def _expected_quiz_date(days_until_quiz: int) -> str:
    return (datetime.now() + timedelta(days=days_until_quiz)).strftime("%d/%m/%Y")


def test_next_quiz_date_uses_monthly_cycle_day_30_after_day_45():
    content = "Proximo quiz: {next_quiz_date}"
    context = {"current_day": 46}  # monthly phase day 1

    result = TemplateVariableProcessor.substitute_variables(content, context)

    assert _expected_quiz_date(29) in result


def test_next_quiz_date_today_when_already_on_monthly_quiz_day():
    content = "Proximo quiz: {next_quiz_date}"
    context = {"current_day": 75}  # monthly cycle day 30

    result = TemplateVariableProcessor.substitute_variables(content, context)

    assert _expected_quiz_date(0) in result


def test_next_quiz_date_not_replaced_before_monthly_phase():
    content = "Proximo quiz: {next_quiz_date}"
    context = {"current_day": 45}

    result = TemplateVariableProcessor.substitute_variables(content, context)

    assert result == content
