"""
Unit tests for schema conversion helpers.
"""

import logging

import pytest

LOGGER_NAME = "app.api.v2.routers.patients.crud"


@pytest.fixture
def split_list_func():
    from app.api.v2.routers.patients.crud import _split_list

    return _split_list


@pytest.fixture
def parse_emergency_contact_func():
    from app.api.v2.routers.patients.crud import _parse_emergency_contact

    return _parse_emergency_contact


@pytest.mark.parametrize(
    "value, expected",
    [
        ("A, B, C", ["A", "B", "C"]),
        ("A; B; C", ["A", "B", "C"]),
        ("A\nB\nC", ["A", "B", "C"]),
        ("A, B; C\nD", ["A", "B", "C", "D"]),
        ("  A  ,  B  ", ["A", "B"]),
        ("A/B", ["A", "B"]),
        ("Medicacao 500mg/dia", ["Medicacao 500mg/dia"]),
        ("A/B, C 100mg/dia", ["A", "B", "C 100mg/dia"]),
        ("A,,B", ["A", "B"]),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_split_list_cases(split_list_func, value, expected):
    assert split_list_func(value, field="allergies") == expected


def test_split_list_logs_warning_on_empty_result(split_list_func, caplog):
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    result = split_list_func(",;,;", field="allergies")

    assert result is None

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "Split list produced no items"
    ]
    assert records

    record = records[0]
    assert record.field == "allergies"
    assert record.original_value == ",;,;"
    assert record.parsed_value == []


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Maria - (11) 99999-9999", ("Maria", "+5511999999999")),
        ("Maria: 11999999999", ("Maria", "+5511999999999")),
        ("Maria | (11) 99999-9999", ("Maria", "+5511999999999")),
        ("+5511999999999", (None, "+5511999999999")),
        ("11999999999", (None, "+5511999999999")),
        (" - 11999999999", (None, "+5511999999999")),
        ("", (None, None)),
        ("   ", (None, None)),
        (None, (None, None)),
    ],
)
def test_parse_emergency_contact_valid(parse_emergency_contact_func, value, expected):
    assert parse_emergency_contact_func(value) == expected


def test_parse_emergency_contact_logs_warning_on_invalid_phone(
    parse_emergency_contact_func, caplog
):
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    value = "Maria - telefone-invalido"
    result = parse_emergency_contact_func(value)

    assert result == ("Maria", None)

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "Emergency contact parsing failed"
    ]
    assert records

    record = records[0]
    assert record.field == "emergency_contact"
    assert record.original_value == value
    assert record.parsed_value == {"name": "Maria", "phone": None}


def test_parse_emergency_contact_logs_warning_on_missing_separator(
    parse_emergency_contact_func, caplog
):
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    value = "Maria (11) 99999-9999"
    result = parse_emergency_contact_func(value)

    assert result == (value, None)

    records = [
        record
        for record in caplog.records
        if record.getMessage() == "Emergency contact parsing failed"
    ]
    assert records

    record = records[0]
    assert record.field == "emergency_contact"
    assert record.original_value == value
    assert record.parsed_value == {"name": value, "phone": None}
