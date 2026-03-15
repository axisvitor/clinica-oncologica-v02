"""Regression tests for canonical physician search/detail/update surfaces."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


pytestmark = [pytest.mark.api]


def test_list_physicians_inactive_status_returns_only_inactive(
    client: TestClient,
    db_session: Session,
    admin_headers: dict,
):
    marker = f"inactive-regression-{uuid4().hex[:8]}"

    active_physician = User(
        email=f"{marker}-active@test.com",
        full_name="Dr. Active Regression",
        display_name=f"{marker}-active-display",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid=f"{marker}-active",
    )
    inactive_physician = User(
        email=f"{marker}-inactive@test.com",
        full_name="Dr. Inactive Regression",
        display_name=f"{marker}-inactive-display",
        role=UserRole.DOCTOR,
        is_active=False,
        firebase_uid=f"{marker}-inactive",
    )
    db_session.add(active_physician)
    db_session.add(inactive_physician)
    db_session.commit()
    db_session.refresh(active_physician)
    db_session.refresh(inactive_physician)

    response = client.get(
        f"/api/v2/physicians/?status=inactive&search={marker}",
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    returned_ids = {row["id"] for row in response.json()["data"]}
    assert str(inactive_physician.id) in returned_ids
    assert str(active_physician.id) not in returned_ids


def test_list_physicians_search_matches_canonical_display_name(
    client: TestClient,
    db_session: Session,
    admin_headers: dict,
    test_doctor_user: User,
):
    search_term = f"canonical-search-{uuid4().hex[:8]}"
    test_doctor_user.full_name = "Unrelated Physician Name"
    test_doctor_user.display_name = search_term
    db_session.commit()
    db_session.refresh(test_doctor_user)

    response = client.get(
        f"/api/v2/physicians/?search={search_term}",
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    rows = response.json()["data"]
    match = next((row for row in rows if row["id"] == str(test_doctor_user.id)), None)
    assert match is not None, (
        "canonical_profile surface=physician_search canonical_display_name_missing=true"
    )
    assert match["display_name"] == search_term, (
        "canonical_profile surface=physician_search canonical_display_name_mismatch=true"
    )


def test_update_physician_persists_canonical_fields(
    client: TestClient,
    db_session: Session,
    admin_headers: dict,
    test_doctor_user: User,
):
    response = client.patch(
        f"/api/v2/physicians/{test_doctor_user.id}",
        headers=admin_headers,
        json={
            "specialties": ["oncology", "hematology"],
            "status": "inactive",
            "license_number": "CRM/SP-123456",
            "phone": "+55 11 99999-1234",
            "bio": "Especialista em oncologia clínica.",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    db_session.refresh(test_doctor_user)

    assert payload["specialties"] == ["oncology", "hematology"], (
        "canonical_profile surface=physician_update canonical_specialties_missing=true"
    )
    assert payload["status"] == "inactive", (
        "canonical_profile surface=physician_update canonical_status_missing=true"
    )
    assert payload["license_number"] == "CRM/SP-123456", (
        "canonical_profile surface=physician_update canonical_license_missing=true"
    )
    assert test_doctor_user.specialties == ["oncology", "hematology"]
    assert test_doctor_user.specialty == "oncology"
    assert test_doctor_user.is_active is False
    assert test_doctor_user.license_number == "CRM/SP-123456"
    assert test_doctor_user.phone == "+55 11 99999-1234"
    assert test_doctor_user.bio == "Especialista em oncologia clínica."
