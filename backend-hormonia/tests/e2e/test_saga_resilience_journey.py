"""
E2E Test: Saga Resilience and Recovery Journey
Tests Saga orchestration failure handling, compensation, and retry logic.

Journey Steps:
1. Start patient creation saga
2. Firebase fails on first attempt
3. Saga compensates (rollback partial changes)
4. Saga retries with exponential backoff
5. Firebase succeeds on retry
6. Saga completes successfully
7. All state consistent

Coverage: Saga orchestration, Error handling, Compensation, Retries, State consistency
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest
from playwright.async_api import Page, expect

from playwright_config import get_endpoint_url


class TestSagaResilienceJourney:
    """Complete Saga resilience and recovery E2E test suite."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)
    async def test_saga_failure_compensation_and_recovery(
        self,
        page: Page,
        e2e_db_session,
        mock_firebase,
        mock_whatsapp,
        chaos_monkey,
        wait_for_saga,
    ):
        """
        Test complete Saga failure and recovery cycle.

        Validates:
        - Saga initiation
        - Service failure detection
        - Compensation execution
        - Retry with backoff
        - Successful recovery
        - Final state consistency
        """
        print("\n🔥 Testing Saga Failure, Compensation, and Recovery")

        # ===================================================================
        # STEP 1: Configure Failure Scenario
        # ===================================================================
        print("\n⚙️ Step 1: Configure Chaos Engineering")

        # Configure Firebase to fail first 2 attempts
        firebase_error = Exception("Firebase temporarily unavailable (simulated)")
        chaos_monkey.fail_next('firebase_create_user', times=2, exception=firebase_error)
        print("✅ Configured Firebase to fail 2 times")

        # Track initial state
        initial_patients_response = await page.request.get(get_endpoint_url('patients_list'))
        initial_patients = await initial_patients_response.json()
        initial_patient_count = len(initial_patients) if isinstance(initial_patients, list) else 0
        print(f"   - Initial patient count: {initial_patient_count}")

        # ===================================================================
        # STEP 2: Attempt Patient Creation (Will Trigger Saga)
        # ===================================================================
        print("\n👤 Step 2: Create Patient (Saga Will Fail Initially)")

        patient_data = {
            'nome': 'Saga Test Patient',
            'cpf': '55544433322',
            'telefone': '+5511555555555',
            'email': 'saga.test@example.com',
            'data_nascimento': '1988-06-15',
            'tipo_tratamento': 'Quimioterapia',
            'metadata': {
                'test_scenario': 'saga_resilience'
            }
        }

        # Start patient creation
        creation_start_time = datetime.now()
        patient_response = await page.request.post(
            get_endpoint_url('patients_create'),
            headers={'Content-Type': 'application/json'},
            data=json.dumps(patient_data)
        )

        # Request should succeed (Saga handles retries internally)
        assert patient_response.status in [200, 201, 202], \
            f"Patient creation failed: {patient_response.status}"

        patient = await patient_response.json()
        patient_id = patient.get('id') or patient.get('patient_id')
        print(f"✅ Patient creation initiated: ID {patient_id}")
        print(f"   - Response status: {patient_response.status}")

        # ===================================================================
        # STEP 3: Monitor Saga Execution (First Failure)
        # ===================================================================
        print("\n📊 Step 3: Monitor Saga Execution")

        # Wait a bit for first attempt
        await asyncio.sleep(2)

        # Query saga status
        saga_response = await page.request.get(f'/api/v2/sagas?patient_id={patient_id}')
        if saga_response.status == 200:
            sagas = await saga_response.json()
            if sagas and len(sagas) > 0:
                saga = sagas[0]
                saga_id = saga.get('id')
                saga_status = saga.get('status')
                print(f"   - Saga ID: {saga_id}")
                print(f"   - Current Status: {saga_status}")
                print(f"   - Retry Count: {saga.get('retry_count', 0)}")
            else:
                print("⚠️  Saga not found yet (async processing)")
                saga_id = None
        else:
            print("⚠️  Saga endpoint not available")
            saga_id = None

        # ===================================================================
        # STEP 4: Wait for Compensation
        # ===================================================================
        print("\n⚙️ Step 4: Verify Compensation Logic")

        # Wait for compensation to execute (after first failure)
        await asyncio.sleep(3)

        # Check if patient was marked for compensation
        patient_check_response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id)
        )

        if patient_check_response.status == 200:
            patient_state = await patient_check_response.json()
            print(f"   - Patient Status: {patient_state.get('status')}")

            # During compensation, patient might be in 'pending' or similar state
            if patient_state.get('status') in ['pending', 'processing', 'compensating']:
                print("✅ Compensation detected (patient in transitional state)")
            else:
                print(f"   - Patient state: {patient_state.get('status')}")

        # ===================================================================
        # STEP 5: Wait for Saga Retry with Backoff
        # ===================================================================
        print("\n🔄 Step 5: Wait for Saga Retry")

        # Saga should retry with exponential backoff
        # First retry: ~2s, Second retry: ~4s
        print("   - Waiting for retries with exponential backoff...")

        retry_wait_time = 10  # seconds
        for i in range(retry_wait_time):
            await asyncio.sleep(1)
            if (i + 1) % 3 == 0:
                print(f"   - Waiting... {i + 1}/{retry_wait_time}s")

        # ===================================================================
        # STEP 6: Verify Successful Recovery
        # ===================================================================
        print("\n✅ Step 6: Verify Successful Recovery")

        # Check if saga eventually completed
        if saga_id:
            final_saga_response = await page.request.get(f'/api/v2/sagas/{saga_id}')
            if final_saga_response.status == 200:
                final_saga = await final_saga_response.json()
                saga_status = final_saga.get('status')
                retry_count = final_saga.get('retry_count', 0)

                print(f"   - Final Saga Status: {saga_status}")
                print(f"   - Total Retries: {retry_count}")

                # Saga should have retried at least twice
                assert retry_count >= 2, f"Expected ≥2 retries, got {retry_count}"
                print("✅ Saga retried with exponential backoff")

                # Saga should eventually complete
                assert saga_status in ['COMPLETED', 'SUCCESS'], \
                    f"Saga failed to recover: {saga_status}"
                print("✅ Saga completed successfully after retries")

        # ===================================================================
        # STEP 7: Verify Firebase Account Created
        # ===================================================================
        print("\n🔐 Step 7: Verify Firebase Account")

        # Check mock Firebase was eventually called
        assert mock_firebase.users_created >= 1, \
            f"Firebase account not created (attempts: {mock_firebase.users_created})"

        firebase_user = mock_firebase.created_users[0]
        assert firebase_user['email'] == patient_data['email']
        print(f"✅ Firebase account created: {firebase_user['uid']}")

        # ===================================================================
        # STEP 8: Verify Final Patient State
        # ===================================================================
        print("\n🔍 Step 8: Verify Final State Consistency")

        # Fetch final patient state
        final_patient_response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id)
        )
        assert final_patient_response.status == 200

        final_patient = await final_patient_response.json()

        # Verify all data is correct
        assert final_patient['nome'] == patient_data['nome']
        assert final_patient['cpf'] == patient_data['cpf']
        assert final_patient['telefone'] == patient_data['telefone']
        assert final_patient['email'] == patient_data['email']
        print("✅ Patient data consistent")

        # Verify patient is active
        assert final_patient.get('status') in ['ativo', 'active'], \
            f"Patient status not active: {final_patient.get('status')}"
        print(f"✅ Patient status: {final_patient['status']}")

        # Verify Firebase UID is set
        assert final_patient.get('firebase_uid') is not None, \
            "Firebase UID not set after recovery"
        assert final_patient['firebase_uid'] == firebase_user['uid']
        print(f"✅ Firebase UID: {final_patient['firebase_uid']}")

        # ===================================================================
        # STEP 9: Verify No Duplicate Records
        # ===================================================================
        print("\n🔍 Step 9: Verify No Duplicate Records")

        # Count patients after saga
        final_patients_response = await page.request.get(get_endpoint_url('patients_list'))
        final_patients = await final_patients_response.json()
        final_patient_count = len(final_patients) if isinstance(final_patients, list) else 0

        # Should have exactly 1 new patient
        assert final_patient_count == initial_patient_count + 1, \
            f"Duplicate records detected: expected {initial_patient_count + 1}, got {final_patient_count}"
        print(f"✅ No duplicates: {initial_patient_count} → {final_patient_count}")

        # Verify only one Firebase account created
        assert mock_firebase.users_created == 1, \
            f"Multiple Firebase accounts created: {mock_firebase.users_created}"
        print("✅ Exactly 1 Firebase account created")

        # ===================================================================
        # STEP 10: Verify Saga Metrics
        # ===================================================================
        print("\n📊 Step 10: Verify Saga Metrics")

        total_duration = (datetime.now() - creation_start_time).total_seconds()
        print(f"   - Total Saga Duration: {total_duration:.2f}s")

        # Saga should have taken time due to retries (backoff)
        # First attempt: immediate, Retry 1: ~2s, Retry 2: ~4s = ~6s minimum
        assert total_duration >= 4, \
            f"Saga completed too quickly for retries: {total_duration}s"
        print("✅ Saga duration consistent with retry backoff")

        # ===================================================================
        # JOURNEY COMPLETE
        # ===================================================================
        print("\n" + "="*60)
        print("🎉 SAGA RESILIENCE JOURNEY COMPLETE!")
        print("="*60)
        print(f"✅ Saga ID: {saga_id}")
        print(f"✅ Retries: {retry_count}")
        print(f"✅ Final Status: COMPLETED")
        print(f"✅ Firebase Account: {firebase_user['uid']}")
        print(f"✅ Patient Status: {final_patient['status']}")
        print(f"✅ Duration: {total_duration:.2f}s")
        print(f"✅ State Consistency: Verified")
        print("="*60 + "\n")


    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_saga_compensation_rollback(
        self,
        page: Page,
        mock_firebase,
        chaos_monkey,
    ):
        """Test Saga compensation when all retries are exhausted."""
        print("\n↩️ Testing Saga Compensation Rollback")

        # Configure Firebase to always fail
        chaos_monkey.fail_next('firebase_create_user', times=10)  # More than max retries

        # Attempt patient creation
        patient_data = {
            'nome': 'Compensation Test',
            'cpf': '11111111111',
            'telefone': '+5511111111111',
            'email': 'compensation@test.com',
            'data_nascimento': '1990-01-01',
            'tipo_tratamento': 'Quimioterapia',
        }

        patient_response = await page.request.post(
            get_endpoint_url('patients_create'),
            data=json.dumps(patient_data)
        )

        # Request might fail or return accepted status
        patient = await patient_response.json()
        patient_id = patient.get('id')

        # Wait for saga to exhaust retries
        await asyncio.sleep(15)

        # Check saga status
        saga_response = await page.request.get(f'/api/v2/sagas?patient_id={patient_id}')
        if saga_response.status == 200:
            sagas = await saga_response.json()
            if sagas:
                saga = sagas[0]
                saga_status = saga.get('status')

                # Saga should be in FAILED or COMPENSATED state
                assert saga_status in ['FAILED', 'COMPENSATED', 'ROLLED_BACK'], \
                    f"Expected failure, got {saga_status}"
                print(f"✅ Saga compensated: Status = {saga_status}")

        # Verify patient was rolled back or marked as failed
        patient_check_response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id)
        )

        if patient_check_response.status == 404:
            print("✅ Patient record rolled back (deleted)")
        elif patient_check_response.status == 200:
            patient_state = await patient_check_response.json()
            assert patient_state.get('status') in ['failed', 'error', 'inactive'], \
                f"Patient should be marked as failed: {patient_state.get('status')}"
            print(f"✅ Patient marked as: {patient_state['status']}")


    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_concurrent_saga_executions(
        self,
        page: Page,
        mock_firebase,
        chaos_monkey,
    ):
        """Test multiple concurrent saga executions."""
        print("\n🔀 Testing Concurrent Saga Executions")

        # Create 5 patients concurrently
        patient_count = 5
        patient_responses = []

        print(f"Creating {patient_count} patients concurrently...")

        # Send all requests in parallel
        for i in range(patient_count):
            patient_data = {
                'nome': f'Concurrent Patient {i+1}',
                'cpf': f'{10000000000 + i}',
                'telefone': f'+551199999{1000 + i}',
                'email': f'concurrent{i+1}@test.com',
                'data_nascimento': '1990-01-01',
                'tipo_tratamento': 'Quimioterapia',
            }

            # Send request (don't await yet)
            response_promise = page.request.post(
                get_endpoint_url('patients_create'),
                data=json.dumps(patient_data)
            )
            patient_responses.append(response_promise)

        # Wait for all responses
        results = await asyncio.gather(*patient_responses, return_exceptions=True)

        successful = sum(1 for r in results if not isinstance(r, Exception) and hasattr(r, 'status') and r.status in [200, 201, 202])
        print(f"✅ Concurrent requests: {successful}/{patient_count} successful")

        # Wait for all sagas to complete
        await asyncio.sleep(10)

        # Verify all Firebase accounts created
        assert mock_firebase.users_created >= successful, \
            f"Not all Firebase accounts created: {mock_firebase.users_created}/{successful}"
        print(f"✅ Firebase accounts: {mock_firebase.users_created}/{successful}")

        # Verify no race conditions (each patient has unique Firebase UID)
        firebase_uids = [user['uid'] for user in mock_firebase.created_users]
        unique_uids = set(firebase_uids)
        assert len(unique_uids) == len(firebase_uids), \
            "Duplicate Firebase UIDs detected (race condition)"
        print("✅ No race conditions detected")


    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_saga_idempotency(
        self,
        page: Page,
        mock_firebase,
    ):
        """Test Saga idempotency (same operation not executed twice)."""
        print("\n🔄 Testing Saga Idempotency")

        patient_data = {
            'nome': 'Idempotency Test',
            'cpf': '22222222222',
            'telefone': '+5511222222222',
            'email': 'idempotency@test.com',
            'data_nascimento': '1990-01-01',
            'tipo_tratamento': 'Quimioterapia',
            'idempotency_key': 'test_saga_idempotency_123',  # Same key
        }

        # Send same request twice
        response1 = await page.request.post(
            get_endpoint_url('patients_create'),
            headers={'X-Idempotency-Key': 'test_saga_idempotency_123'},
            data=json.dumps(patient_data)
        )

        response2 = await page.request.post(
            get_endpoint_url('patients_create'),
            headers={'X-Idempotency-Key': 'test_saga_idempotency_123'},  # Same key
            data=json.dumps(patient_data)
        )

        # Both should succeed
        assert response1.status in [200, 201, 202]
        assert response2.status in [200, 201, 202]

        patient1 = await response1.json()
        patient2 = await response2.json()

        # Should return same patient ID
        assert patient1.get('id') == patient2.get('id'), \
            "Idempotency failed: different patient IDs"
        print(f"✅ Idempotency verified: Same ID = {patient1['id']}")

        # Wait for processing
        await asyncio.sleep(5)

        # Verify only ONE Firebase account created
        assert mock_firebase.users_created == 1, \
            f"Duplicate Firebase accounts: {mock_firebase.users_created}"
        print("✅ Only 1 Firebase account created (idempotency working)")
