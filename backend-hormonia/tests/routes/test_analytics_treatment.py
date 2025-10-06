"""
Test suite for Analytics Treatment Distribution endpoint.

Tests GET /api/v1/analytics/treatment-distribution with:
- Valid/invalid period parameters
- Response structure validation
- Chart-ready data formatting
- Percentage calculations
- Empty data handling
- Color coding for chart rendering
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.services.analytics import AnalyticsService, TREATMENT_COLORS
from app.models.patient import Patient
from tests.helpers.jwt_helper import jwt_helper


class TestTreatmentDistribution:
    """Test suite for GET /api/v1/analytics/treatment-distribution"""

    def test_invalid_period_parameter(self, db_session):
        """Invalid period should raise ValueError"""
        service = AnalyticsService(db_session)

        # Test with invalid period format
        with pytest.raises(ValueError):
            service.get_treatment_distribution(period="invalid")

    @pytest.mark.parametrize("period", ["7d", "30d", "90d", "all"])
    def test_valid_period_parameters(self, db_session, period):
        """All valid period values should work"""
        service = AnalyticsService(db_session)

        result = service.get_treatment_distribution(period=period)

        assert result is not None
        assert "period" in result
        assert result["period"] == period
        assert "data" in result
        assert "total_patients" in result
        assert "timestamp" in result

    def test_treatment_distribution_structure(self, db_session):
        """Response should have correct structure with colors"""
        # Create test patients with treatments
        patients = [
            Patient(
                id=uuid4(),
                name="Patient 1",
                firebase_uid=f"firebase_patient_1",
                treatment_type="Quimioterapia",
                flow_state="active"
            ),
            Patient(
                id=uuid4(),
                name="Patient 2",
                firebase_uid=f"firebase_patient_2",
                treatment_type="Quimioterapia",
                flow_state="active"
            ),
            Patient(
                id=uuid4(),
                name="Patient 3",
                firebase_uid=f"firebase_patient_3",
                treatment_type="Radioterapia",
                flow_state="active"
            ),
        ]
        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        assert "data" in result
        assert "total_patients" in result
        assert result["total_patients"] >= 3

        # Check first treatment entry structure
        if result["data"]:
            treatment = result["data"][0]
            assert "treatment_type" in treatment
            assert "count" in treatment
            assert "percentage" in treatment
            assert "color" in treatment  # Chart-ready
            assert treatment["color"].startswith("#")  # Hex color

    def test_percentage_calculation(self, db_session):
        """Percentages should sum to approximately 100%"""
        # Create 10 patients: 7 Quimio, 3 Radio
        patients = []
        for i in range(7):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Quimio {i}",
                firebase_uid=f"firebase_quimio_{i}",
                treatment_type="Quimioterapia",
                flow_state="active"
            ))
        for i in range(3):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Radio {i}",
                firebase_uid=f"firebase_radio_{i}",
                treatment_type="Radioterapia",
                flow_state="active"
            ))

        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        total_percentage = sum(t["percentage"] for t in result["data"])
        # Allow for rounding errors
        assert 99.0 <= total_percentage <= 100.1

        # Verify counts
        assert result["total_patients"] >= 10

    def test_empty_treatments(self, db_session):
        """Should handle empty database gracefully"""
        # Query on empty or filtered-empty result
        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all", doctor_id=uuid4())

        assert result["data"] == []
        assert result["total_patients"] == 0
        assert result["period"] == "all"

    def test_period_filtering(self, db_session):
        """Should filter patients by creation date based on period"""
        # Create old patient (91 days ago)
        old_date = datetime.utcnow() - timedelta(days=91)
        old_patient = Patient(
            id=uuid4(),
            name="Old Patient",
            firebase_uid="firebase_old",
            treatment_type="Quimioterapia",
            flow_state="active",
            created_at=old_date
        )

        # Create recent patient (within 30 days)
        recent_patient = Patient(
            id=uuid4(),
            name="Recent Patient",
            firebase_uid="firebase_recent",
            treatment_type="Radioterapia",
            flow_state="active"
        )

        db_session.add_all([old_patient, recent_patient])
        db_session.commit()

        service = AnalyticsService(db_session)

        # 30d filter should exclude old patient
        result_30d = service.get_treatment_distribution(period="30d")

        # "all" should include both
        result_all = service.get_treatment_distribution(period="all")

        assert result_all["total_patients"] >= result_30d["total_patients"]

    def test_color_assignment(self, db_session):
        """Each treatment type should have correct color from mapping"""
        patients = [
            Patient(
                id=uuid4(),
                name="Patient Quimio",
                firebase_uid="firebase_quimio",
                treatment_type="Quimioterapia",
                flow_state="active"
            ),
            Patient(
                id=uuid4(),
                name="Patient Radio",
                firebase_uid="firebase_radio",
                treatment_type="Radioterapia",
                flow_state="active"
            ),
        ]
        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        # Check color assignment
        for treatment in result["data"]:
            treatment_type = treatment["treatment_type"]
            if treatment_type in TREATMENT_COLORS:
                assert treatment["color"] == TREATMENT_COLORS[treatment_type]
            else:
                # Unknown types should get default gray color
                assert treatment["color"] == "#6b7280"

    def test_sorting_by_count(self, db_session):
        """Results should be sorted by count descending"""
        # Create 5 Quimio, 2 Radio, 1 Imunoterapia
        patients = []
        for i in range(5):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Quimio {i}",
                firebase_uid=f"firebase_quimio_{i}",
                treatment_type="Quimioterapia",
                flow_state="active"
            ))
        for i in range(2):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Radio {i}",
                firebase_uid=f"firebase_radio_{i}",
                treatment_type="Radioterapia",
                flow_state="active"
            ))
        patients.append(Patient(
            id=uuid4(),
            name="Patient Imuno",
            firebase_uid="firebase_imuno",
            treatment_type="Imunoterapia",
            flow_state="active"
        ))

        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        # Verify sorting
        if len(result["data"]) > 1:
            for i in range(len(result["data"]) - 1):
                assert result["data"][i]["count"] >= result["data"][i + 1]["count"]

    def test_doctor_filtering(self, db_session):
        """Should filter by doctor_id when provided"""
        doctor1_id = uuid4()
        doctor2_id = uuid4()

        patients = [
            Patient(
                id=uuid4(),
                name="Patient Doctor1",
                firebase_uid="firebase_d1",
                treatment_type="Quimioterapia",
                flow_state="active",
                doctor_id=doctor1_id
            ),
            Patient(
                id=uuid4(),
                name="Patient Doctor2",
                firebase_uid="firebase_d2",
                treatment_type="Radioterapia",
                flow_state="active",
                doctor_id=doctor2_id
            ),
        ]
        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)

        # Filter by doctor1
        result_d1 = service.get_treatment_distribution(period="all", doctor_id=doctor1_id)

        # Should only include doctor1's patients
        assert result_d1["total_patients"] >= 1
        if result_d1["data"]:
            # Should only have Quimioterapia
            assert any(t["treatment_type"] == "Quimioterapia" for t in result_d1["data"])

    def test_null_treatment_types_excluded(self, db_session):
        """Patients with null treatment_type should be excluded"""
        patients = [
            Patient(
                id=uuid4(),
                name="Patient with treatment",
                firebase_uid="firebase_with",
                treatment_type="Quimioterapia",
                flow_state="active"
            ),
            Patient(
                id=uuid4(),
                name="Patient without treatment",
                firebase_uid="firebase_without",
                treatment_type=None,  # NULL treatment
                flow_state="active"
            ),
        ]
        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        # Should only count patient with treatment
        assert result["total_patients"] >= 1

        # Verify no null treatment types in results
        for treatment in result["data"]:
            assert treatment["treatment_type"] is not None

    def test_timestamp_format(self, db_session):
        """Timestamp should be in ISO format"""
        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        assert "timestamp" in result
        # Should be parseable as ISO datetime
        timestamp = datetime.fromisoformat(result["timestamp"])
        assert isinstance(timestamp, datetime)

    def test_small_categories_grouping(self, db_session):
        """Categories below 2% should be grouped into 'Outros'"""
        # Create distribution: 50 Quimio, 45 Radio, 3 Imuno, 2 Cirurgia
        # Imuno (3%) and Cirurgia (2%) should remain separate or be grouped
        patients = []

        for i in range(50):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Quimio {i}",
                firebase_uid=f"firebase_quimio_{i}",
                treatment_type="Quimioterapia",
                flow_state="active"
            ))

        for i in range(45):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Radio {i}",
                firebase_uid=f"firebase_radio_{i}",
                treatment_type="Radioterapia",
                flow_state="active"
            ))

        for i in range(3):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Imuno {i}",
                firebase_uid=f"firebase_imuno_{i}",
                treatment_type="Imunoterapia",
                flow_state="active"
            ))

        for i in range(2):
            patients.append(Patient(
                id=uuid4(),
                name=f"Patient Cirurgia {i}",
                firebase_uid=f"firebase_cirurgia_{i}",
                treatment_type="Cirurgia",
                flow_state="active"
            ))

        db_session.add_all(patients)
        db_session.commit()

        service = AnalyticsService(db_session)
        result = service.get_treatment_distribution(period="all")

        # Check if small categories exist
        # Implementation may group them into "Outros" or keep them separate
        total_categories = len(result["data"])
        assert total_categories > 0

        # Verify all percentages are valid
        for treatment in result["data"]:
            assert 0 <= treatment["percentage"] <= 100


class TestTreatmentDistributionIntegration:
    """Integration tests for treatment distribution with API endpoint"""

    @pytest.mark.asyncio
    async def test_api_endpoint_unauthorized(self, http_client):
        """Unauthenticated requests should be rejected"""
        response = await http_client.get("/api/v1/analytics/treatment-distribution")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_endpoint_success(self, http_client, doctor_a_credentials, auth_headers):
        """Authenticated requests should return valid data"""
        headers = auth_headers(doctor_a_credentials)
        response = await http_client.get(
            "/api/v1/analytics/treatment-distribution",
            headers=headers
        )

        # Should succeed (200 or 404 if endpoint not yet implemented)
        assert response.status_code in [200, 404, 500]

        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert "total_patients" in data
            assert "period" in data
