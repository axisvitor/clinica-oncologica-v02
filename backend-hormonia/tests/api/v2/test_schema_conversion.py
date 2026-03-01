"""Tests for v2 -> v1 schema conversion helpers."""

from app.api.v2.routers.patients.crud import _parse_emergency_contact, _split_list


def test_split_list_multiple_separators():
    assert _split_list("A, B; C/D", field="allergies") == ["A", "B", "C", "D"]


def test_split_list_dosage_kept_intact():
    assert _split_list("Medicacao 500mg/dia", field="medications") == [
        "Medicacao 500mg/dia"
    ]


def test_split_list_empty_string():
    assert _split_list("", field="allergies") is None


def test_split_list_none_value():
    assert _split_list(None, field="allergies") is None


def test_split_list_extra_spaces():
    assert _split_list("  A  ,  B  ", field="allergies") == ["A", "B"]


def test_split_list_newlines():
    assert _split_list("A\nB", field="allergies") == ["A", "B"]


def test_parse_emergency_contact_dash_format():
    assert _parse_emergency_contact("Maria - (11) 99999-9999") == (
        "Maria",
        "+5511999999999",
    )


def test_parse_emergency_contact_colon_format():
    assert _parse_emergency_contact("Maria: 11999999999") == (
        "Maria",
        "+5511999999999",
    )


def test_parse_emergency_contact_phone_only():
    assert _parse_emergency_contact("11999999999") == (None, "+5511999999999")


def test_parse_emergency_contact_name_only():
    assert _parse_emergency_contact("Maria") == ("Maria", None)


def test_parse_emergency_contact_invalid_phone():
    assert _parse_emergency_contact("Maria - 123") == ("Maria", None)
