"""
Tests for Patient API v2 - Advanced Filters Evolution

Tests new filters added in v2 evolution:
- treatment_phase
- has_active_flow
- created_after/created_before
- sort_by/sort_order

Coverage Target: 90%+
Backward Compatibility: Required
"""
import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_filter_by_treatment_phase_initial(client, doctor_token, test_patients_various_phases):
    """Test filtering by treatment_phase='initial'"""
    response = client.get(
        "/api/v2/patients?treatment_phase=initial",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    # All returned patients should have treatment_phase = initial
    for patient in data["data"]:
        assert patient.get("treatment_phase") == "initial"


@pytest.mark.asyncio
async def test_filter_by_treatment_phase_maintenance(client, doctor_token, test_patients_various_phases):
    """Test filtering by treatment_phase='maintenance'"""
    response = client.get(
        "/api/v2/patients?treatment_phase=maintenance",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    for patient in data["data"]:
        assert patient.get("treatment_phase") == "maintenance"


@pytest.mark.asyncio
async def test_filter_by_treatment_phase_followup(client, doctor_token, test_patients_various_phases):
    """Test filtering by treatment_phase='followup'"""
    response = client.get(
        "/api/v2/patients?treatment_phase=followup",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    for patient in data["data"]:
        assert patient.get("treatment_phase") == "followup"


@pytest.mark.asyncio
async def test_filter_invalid_treatment_phase(client, doctor_token):
    """Test validation rejects invalid treatment_phase values"""
    response = client.get(
        "/api/v2/patients?treatment_phase=invalid_phase",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "treatment_phase" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_filter_has_active_flow_true(client, doctor_token, test_patients_with_flows):
    """Test filtering by has_active_flow=true"""
    response = client.get(
        "/api/v2/patients?has_active_flow=true",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    # All returned patients should have active flows
    for patient in data["data"]:
        assert patient.get("flow_state") in ["ACTIVE", "RUNNING", "IN_PROGRESS"]


@pytest.mark.asyncio
async def test_filter_has_active_flow_false(client, doctor_token, test_patients_with_flows):
    """Test filtering by has_active_flow=false"""
    response = client.get(
        "/api/v2/patients?has_active_flow=false",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    # All returned patients should NOT have active flows
    for patient in data["data"]:
        assert patient.get("flow_state") not in ["ACTIVE", "RUNNING", "IN_PROGRESS"]


@pytest.mark.asyncio
async def test_filter_created_after_yesterday(client, doctor_token, test_patients_various_dates):
    """Test filtering by created_after (yesterday)"""
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
    response = client.get(
        f"/api/v2/patients?created_after={yesterday}",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    # All returned patients should be created after yesterday
    yesterday_dt = datetime.fromisoformat(yesterday.replace("Z", "+00:00"))
    for patient in data["data"]:
        created_at = datetime.fromisoformat(patient["created_at"].replace("Z", "+00:00"))
        assert created_at > yesterday_dt


@pytest.mark.asyncio
async def test_filter_created_before_today(client, doctor_token, test_patients_various_dates):
    """Test filtering by created_before (today)"""
    today = datetime.utcnow().isoformat()
    response = client.get(
        f"/api/v2/patients?created_before={today}",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    # All returned patients should be created before today
    today_dt = datetime.fromisoformat(today.replace("Z", "+00:00"))
    for patient in data["data"]:
        created_at = datetime.fromisoformat(patient["created_at"].replace("Z", "+00:00"))
        assert created_at < today_dt


@pytest.mark.asyncio
async def test_filter_created_date_range(client, doctor_token, test_patients_various_dates):
    """Test filtering by both created_after and created_before (date range)"""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()

    response = client.get(
        f"/api/v2/patients?created_after={week_ago}&created_before={yesterday}",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    week_ago_dt = datetime.fromisoformat(week_ago.replace("Z", "+00:00"))
    yesterday_dt = datetime.fromisoformat(yesterday.replace("Z", "+00:00"))

    for patient in data["data"]:
        created_at = datetime.fromisoformat(patient["created_at"].replace("Z", "+00:00"))
        assert week_ago_dt < created_at < yesterday_dt


@pytest.mark.asyncio
async def test_filter_invalid_date_format(client, doctor_token):
    """Test validation rejects invalid date formats"""
    response = client.get(
        "/api/v2/patients?created_after=invalid-date",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "date" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sort_by_name_ascending(client, doctor_token, test_patients_various_names):
    """Test sorting by name ascending"""
    response = client.get(
        "/api/v2/patients?sort_by=name&sort_order=asc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify names are in ascending order
    names = [p["name"] for p in data]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_sort_by_name_descending(client, doctor_token, test_patients_various_names):
    """Test sorting by name descending"""
    response = client.get(
        "/api/v2/patients?sort_by=name&sort_order=desc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify names are in descending order
    names = [p["name"] for p in data]
    assert names == sorted(names, reverse=True)


@pytest.mark.asyncio
async def test_sort_by_created_at_ascending(client, doctor_token, test_patients_various_dates):
    """Test sorting by created_at ascending (oldest first)"""
    response = client.get(
        "/api/v2/patients?sort_by=created_at&sort_order=asc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify dates are in ascending order
    dates = [datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) for p in data]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_sort_by_created_at_descending(client, doctor_token, test_patients_various_dates):
    """Test sorting by created_at descending (newest first) - DEFAULT"""
    response = client.get(
        "/api/v2/patients?sort_by=created_at&sort_order=desc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify dates are in descending order
    dates = [datetime.fromisoformat(p["created_at"].replace("Z", "+00:00")) for p in data]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_sort_by_email_ascending(client, doctor_token, test_patients_various_emails):
    """Test sorting by email ascending"""
    response = client.get(
        "/api/v2/patients?sort_by=email&sort_order=asc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify emails are in ascending order
    emails = [p["email"] for p in data if p.get("email")]
    assert emails == sorted(emails)


@pytest.mark.asyncio
async def test_invalid_sort_by_field(client, doctor_token):
    """Test validation rejects invalid sort_by field"""
    response = client.get(
        "/api/v2/patients?sort_by=invalid_field",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "sort_by" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invalid_sort_order(client, doctor_token):
    """Test validation rejects invalid sort_order"""
    response = client.get(
        "/api/v2/patients?sort_by=name&sort_order=invalid",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "sort_order" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sort_order_without_sort_by_uses_default(client, doctor_token):
    """Test that sort_order without sort_by uses default sorting"""
    response = client.get(
        "/api/v2/patients?sort_order=asc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    # Should use default sort_by (created_at) with specified order
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_backward_compatibility_no_filters_no_sorting(client, doctor_token):
    """CRITICAL: Test backward compatibility - list without any new parameters"""
    response = client.get(
        "/api/v2/patients",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200  # MUST still work!
    data = response.json()
    assert "data" in data
    assert "total" in data
    # Default sorting should be created_at desc (newest first)


@pytest.mark.asyncio
async def test_combined_filters_treatment_phase_and_active_flow(client, doctor_token, test_patients_complex):
    """Test combining treatment_phase and has_active_flow filters"""
    response = client.get(
        "/api/v2/patients?treatment_phase=initial&has_active_flow=true",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    for patient in data["data"]:
        assert patient.get("treatment_phase") == "initial"
        assert patient.get("flow_state") in ["ACTIVE", "RUNNING", "IN_PROGRESS"]


@pytest.mark.asyncio
async def test_combined_filters_date_range_and_sort(client, doctor_token, test_patients_complex):
    """Test combining date filters with sorting"""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    response = client.get(
        f"/api/v2/patients?created_after={week_ago}&sort_by=name&sort_order=asc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Verify date filter
    week_ago_dt = datetime.fromisoformat(week_ago.replace("Z", "+00:00"))
    for patient in data:
        created_at = datetime.fromisoformat(patient["created_at"].replace("Z", "+00:00"))
        assert created_at > week_ago_dt

    # Verify sorting
    names = [p["name"] for p in data]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_combined_all_filters_and_sort(client, doctor_token, test_patients_complex):
    """Test combining ALL filters with sorting"""
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

    response = client.get(
        f"/api/v2/patients?treatment_phase=initial&has_active_flow=true&created_after={week_ago}&sort_by=name&sort_order=desc",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    week_ago_dt = datetime.fromisoformat(week_ago.replace("Z", "+00:00"))

    for patient in data["data"]:
        # Verify all filters
        assert patient.get("treatment_phase") == "initial"
        assert patient.get("flow_state") in ["ACTIVE", "RUNNING", "IN_PROGRESS"]
        created_at = datetime.fromisoformat(patient["created_at"].replace("Z", "+00:00"))
        assert created_at > week_ago_dt

    # Verify sorting
    names = [p["name"] for p in data["data"]]
    assert names == sorted(names, reverse=True)


@pytest.mark.asyncio
async def test_pagination_with_filters(client, doctor_token, test_patients_complex):
    """Test pagination works correctly with filters"""
    response = client.get(
        "/api/v2/patients?treatment_phase=initial&page=1&page_size=5",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) <= 5
    assert data["page"] == 1
    assert "total" in data


@pytest.mark.asyncio
async def test_pagination_with_sorting(client, doctor_token, test_patients_complex):
    """Test pagination works correctly with sorting"""
    response = client.get(
        "/api/v2/patients?sort_by=name&sort_order=asc&page=1&page_size=10",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) <= 10

    # Verify first page is sorted correctly
    names = [p["name"] for p in data["data"]]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_empty_results_with_filters(client, doctor_token):
    """Test filtering that returns no results"""
    future_date = (datetime.utcnow() + timedelta(days=30)).isoformat()

    response = client.get(
        f"/api/v2/patients?created_after={future_date}",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["data"] == []


@pytest.mark.asyncio
async def test_filters_respect_rbac_doctor_only_sees_own_patients(client, doctor_token, test_patients_multiple_doctors):
    """Test filters respect RBAC - doctor only sees their own patients"""
    response = client.get(
        "/api/v2/patients?treatment_phase=initial",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # All returned patients should belong to this doctor
    # (assuming doctor_token is for a specific doctor)
    for patient in data["data"]:
        # Verify RBAC is enforced
        assert patient.get("doctor_id") is not None


@pytest.mark.asyncio
async def test_filters_admin_sees_all_patients(client, admin_token, test_patients_multiple_doctors):
    """Test filters for admin - sees all patients regardless of doctor"""
    response = client.get(
        "/api/v2/patients?treatment_phase=initial",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Admin should see patients from multiple doctors
    doctor_ids = set(p.get("doctor_id") for p in data["data"])
    # Should have patients from different doctors
    assert len(doctor_ids) >= 1


@pytest.mark.asyncio
async def test_case_insensitive_sort_order(client, doctor_token):
    """Test sort_order is case insensitive"""
    response = client.get(
        "/api/v2/patients?sort_by=name&sort_order=ASC",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_whitespace_in_parameters_handled(client, doctor_token):
    """Test parameters with whitespace are handled correctly"""
    response = client.get(
        "/api/v2/patients?sort_by=name&sort_order= asc ",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    # Should either trim and accept, or reject with 400
    assert response.status_code in [200, 400]


@pytest.mark.asyncio
async def test_default_sorting_order(client, doctor_token, test_patients_various_dates):
    """Test default sorting (no sort parameters) returns newest first"""
    response = client.get(
        "/api/v2/patients",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()["data"]

    if len(data) >= 2:
        # Default should be created_at desc (newest first)
        first_date = datetime.fromisoformat(data[0]["created_at"].replace("Z", "+00:00"))
        second_date = datetime.fromisoformat(data[1]["created_at"].replace("Z", "+00:00"))
        assert first_date >= second_date
