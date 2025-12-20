"""
Tests for Patient API v2 - Clinical Fields Evolution

Tests new optional clinical fields added in v2 evolution:
- allergies
- current_medications
- comorbidities
- blood_type
- emergency_contact_name
- emergency_contact_phone

Coverage Target: 90%+
Backward Compatibility: Required
"""
import pytest
from uuid import uuid4


@pytest.mark.asyncio
async def test_create_patient_with_all_clinical_fields(client, doctor_token):
    """Test creating patient with all new clinical fields populated"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Maria Silva Santos",
        "phone": "+5511999999999",
        "email": "maria.silva@example.com",
        "allergies": ["Penicilina", "Dipirona", "Amendoim"],
        "current_medications": ["Aspirina 100mg - 1x/dia", "Metformina 500mg - 2x/dia"],
        "comorbidities": ["Diabetes Tipo 2", "Hipertensão Arterial", "Hipotireoidismo"],
        "blood_type": "A+",
        "emergency_contact_name": "João Silva Santos",
        "emergency_contact_phone": "+5511888888888"
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["allergies"] == ["Penicilina", "Dipirona", "Amendoim"]
    assert data["current_medications"] == ["Aspirina 100mg - 1x/dia", "Metformina 500mg - 2x/dia"]
    assert data["comorbidities"] == ["Diabetes Tipo 2", "Hipertensão Arterial", "Hipotireoidismo"]
    assert data["blood_type"] == "A+"
    assert data["emergency_contact_name"] == "João Silva Santos"
    assert data["emergency_contact_phone"] == "+5511888888888"


@pytest.mark.asyncio
async def test_create_patient_partial_clinical_fields(client, doctor_token):
    """Test creating patient with only some clinical fields"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Ana Costa",
        "phone": "+5511777777777",
        "email": "ana.costa@example.com",
        "blood_type": "O-",
        "emergency_contact_name": "Pedro Costa",
        "emergency_contact_phone": "+5511666666666"
        # Deliberately omitting allergies, medications, comorbidities
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["blood_type"] == "O-"
    assert data["emergency_contact_name"] == "Pedro Costa"
    assert data.get("allergies") in (None, [])
    assert data.get("current_medications") in (None, [])
    assert data.get("comorbidities") in (None, [])


@pytest.mark.asyncio
async def test_backward_compatibility_no_clinical_fields(client, doctor_token):
    """CRITICAL: Test backward compatibility - create patient WITHOUT any new fields"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Cliente Antigo",
        "phone": "+5511555555555",
        "email": "cliente.antigo@example.com"
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201  # MUST still work!
    data = response.json()
    assert data["name"] == "Cliente Antigo"
    assert data["phone"] == "+5511555555555"
    assert data["email"] == "cliente.antigo@example.com"
    # New fields should be None or empty


@pytest.mark.asyncio
@pytest.mark.parametrize("blood_type", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"])
async def test_valid_blood_types(client, doctor_token, blood_type):
    """Test all valid blood type values"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": f"Patient {blood_type}",
        "phone": f"+551155555{blood_type[0]}",
        "blood_type": blood_type
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201
    assert response.json()["blood_type"] == blood_type


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_blood_type", [
    "INVALID",
    "A",
    "B",
    "AB",
    "O",
    "A++",
    "a+",  # lowercase
    "A positive",
    "Type A",
    "",
    "null"
])
async def test_invalid_blood_types(client, doctor_token, invalid_blood_type):
    """Test validation rejects invalid blood types"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511444444444",
        "blood_type": invalid_blood_type
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "blood_type" in response.json()["detail"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_phone", [
    "+5511999998888",
    "+5521987654321",
    "+5548988776655",
    "+551133334444"
])
async def test_valid_emergency_phones(client, doctor_token, valid_phone):
    """Test valid emergency phone formats"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511333333333",
        "emergency_contact_name": "Emergency Contact",
        "emergency_contact_phone": valid_phone
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201
    assert response.json()["emergency_contact_phone"] == valid_phone


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_phone", [
    "11999998888",  # Missing +55
    "+55119999",  # Too short
    "+551199999999999",  # Too long
    "5511999998888",  # Missing +
    "+55-11-99999-8888",  # Dashes not allowed
    "(11) 99999-8888",  # Invalid format
    ""
])
async def test_invalid_emergency_phones(client, doctor_token, invalid_phone):
    """Test validation rejects invalid emergency phone formats"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511222222222",
        "emergency_contact_name": "Emergency Contact",
        "emergency_contact_phone": invalid_phone
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    error_detail = response.json()["detail"].lower()
    assert "phone" in error_detail or "emergency" in error_detail


@pytest.mark.asyncio
async def test_emergency_contact_name_without_phone_fails(client, doctor_token):
    """Test that emergency_contact_name requires emergency_contact_phone"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511111111111",
        "emergency_contact_name": "Emergency Contact"
        # Missing emergency_contact_phone
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "emergency" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_emergency_contact_phone_without_name_fails(client, doctor_token):
    """Test that emergency_contact_phone requires emergency_contact_name"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511111111111",
        "emergency_contact_phone": "+5511999999999"
        # Missing emergency_contact_name
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400
    assert "emergency" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_empty_allergies_list(client, doctor_token):
    """Test empty allergies list is accepted"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "No Allergies Patient",
        "phone": "+5511000000000",
        "allergies": []
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201
    assert response.json()["allergies"] == []


@pytest.mark.asyncio
async def test_update_patient_add_clinical_fields(client, doctor_token, test_patient):
    """Test updating existing patient to add clinical fields"""
    update_data = {
        "allergies": ["Látex"],
        "blood_type": "B+",
        "emergency_contact_name": "Updated Contact",
        "emergency_contact_phone": "+5511777777777"
    }

    response = client.patch(
        f"/api/v2/patients/{test_patient['id']}",
        json=update_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allergies"] == ["Látex"]
    assert data["blood_type"] == "B+"
    assert data["emergency_contact_name"] == "Updated Contact"


@pytest.mark.asyncio
async def test_update_patient_remove_clinical_fields(client, doctor_token, test_patient_with_clinical_data):
    """Test updating patient to remove/clear clinical fields"""
    update_data = {
        "allergies": None,
        "current_medications": None,
        "comorbidities": None,
        "blood_type": None,
        "emergency_contact_name": None,
        "emergency_contact_phone": None
    }

    response = client.patch(
        f"/api/v2/patients/{test_patient_with_clinical_data['id']}",
        json=update_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data.get("allergies") in (None, [])
    assert data.get("blood_type") is None


@pytest.mark.asyncio
async def test_get_patient_includes_clinical_fields(client, doctor_token, test_patient_with_clinical_data):
    """Test GET patient includes all clinical fields"""
    response = client.get(
        f"/api/v2/patients/{test_patient_with_clinical_data['id']}",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "allergies" in data
    assert "current_medications" in data
    assert "comorbidities" in data
    assert "blood_type" in data
    assert "emergency_contact_name" in data
    assert "emergency_contact_phone" in data


@pytest.mark.asyncio
async def test_list_patients_includes_clinical_fields(client, doctor_token):
    """Test listing patients includes clinical fields in response"""
    response = client.get(
        "/api/v2/patients",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    if data["data"]:
        first_patient = data["data"][0]
        # Clinical fields should be present (even if None/empty)
        assert "blood_type" in first_patient
        assert "emergency_contact_name" in first_patient


@pytest.mark.asyncio
async def test_clinical_fields_max_length_validation(client, doctor_token):
    """Test validation of max lengths for text fields"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511999999999",
        "emergency_contact_name": "A" * 256,  # Too long
        "allergies": ["A" * 501]  # Individual allergy too long
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_clinical_fields_array_max_items(client, doctor_token):
    """Test validation of max items in arrays"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511999999999",
        "allergies": [f"Allergy {i}" for i in range(101)]  # Too many
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_clinical_fields_rbac_admin_can_update(client, admin_token, test_patient):
    """Test RBAC: Admin can update clinical fields"""
    update_data = {
        "blood_type": "AB+",
        "allergies": ["Iodo"]
    }

    response = client.patch(
        f"/api/v2/patients/{test_patient['id']}",
        json=update_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_clinical_fields_rbac_doctor_can_update_own_patient(client, doctor_token, test_patient_owned_by_doctor):
    """Test RBAC: Doctor can update clinical fields for their patients"""
    update_data = {
        "comorbidities": ["Asma"],
        "current_medications": ["Salbutamol"]
    }

    response = client.patch(
        f"/api/v2/patients/{test_patient_owned_by_doctor['id']}",
        json=update_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_clinical_fields_rbac_doctor_cannot_update_other_doctor_patient(client, doctor_token, test_patient_owned_by_other_doctor):
    """Test RBAC: Doctor cannot update other doctor's patient clinical fields"""
    update_data = {
        "blood_type": "A-"
    }

    response = client.patch(
        f"/api/v2/patients/{test_patient_owned_by_other_doctor['id']}",
        json=update_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_special_characters_in_clinical_fields(client, doctor_token):
    """Test handling of special characters in clinical fields"""
    patient_data = {
        "doctor_id": str(uuid4()),
        "name": "Test Patient",
        "phone": "+5511999999999",
        "allergies": ["Dipirona®", "Anti-inflamatórios (AINEs)", "Ácido acetilsalicílico"],
        "current_medications": ["Losartana 50mg - 1x/dia (manhã)", "Sinvastatina 20mg à noite"],
        "emergency_contact_name": "José da Silva Jr."
    }

    response = client.post(
        "/api/v2/patients",
        json=patient_data,
        headers={"Authorization": f"Bearer {doctor_token}"}
    )

    assert response.status_code == 201
    data = response.json()
    assert "Dipirona®" in data["allergies"]
    assert "José da Silva Jr." == data["emergency_contact_name"]
