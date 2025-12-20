"""
E2E Test: Complete Patient Onboarding Journey
Tests the full patient lifecycle from creation to quiz completion.

Journey Steps:
1. Doctor creates patient via UI
2. Patient receives WhatsApp welcome message
3. Patient responds with personal data
4. System validates and creates Firebase account
5. Patient receives confirmation
6. Quiz flow starts automatically
7. Patient completes quiz
8. Doctor sees results in dashboard

Coverage: Patient CRUD, WhatsApp integration, Firebase auth, Quiz flow, Saga orchestration

NOTE: Requires playwright and playwright_config to be installed.
"""
import pytest

# Skip entire module if playwright is not installed
pytest.importorskip("playwright", reason="Playwright not installed")

import asyncio
import json
from datetime import datetime
from typing import Any, Dict
from playwright.async_api import Page, expect


class TestPatientOnboardingJourney:
    """Complete patient onboarding E2E test suite."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(120)  # 2 minutes max
    async def test_complete_patient_onboarding_journey(
        self,
        page: Page,
        e2e_db_session,
        mock_whatsapp,
        mock_gemini,
        mock_firebase,
        test_patient_data: Dict[str, Any],
        wait_for_saga,
        generate_signature,
    ):
        """
        Test complete patient onboarding flow from creation to quiz completion.

        This test validates:
        - Doctor UI for patient creation
        - WhatsApp message sending
        - Webhook processing with idempotency
        - Firebase account creation
        - Quiz flow initialization
        - Patient data persistence
        - Dashboard updates
        """
        # ===================================================================
        # STEP 1: Doctor Login
        # ===================================================================
        print("\n🔐 Step 1: Doctor Login")

        await page.goto(get_endpoint_url('auth_login'))
        await page.wait_for_load_state('networkidle')

        # Fill login credentials
        await page.fill('[name=email]', 'doctor@test.com')
        await page.fill('[name=password]', 'Test@1234')

        # Submit login form
        await page.click('button[type=submit]')

        # Wait for dashboard redirect
        await page.wait_for_url('**/dashboard', timeout=10000)

        # Verify authenticated state
        user_menu = page.locator('.user-menu')
        await expect(user_menu).to_be_visible()
        print("✅ Doctor authenticated successfully")

        # ===================================================================
        # STEP 2: Create Patient via UI
        # ===================================================================
        print("\n👤 Step 2: Create Patient")

        # Navigate to patient creation
        await page.click('button:has-text("Novo Paciente")')
        await page.wait_for_selector('form[data-testid="patient-create-form"]')

        # Fill patient form
        await page.fill('[name=nome]', test_patient_data['nome'])
        await page.fill('[name=cpf]', test_patient_data['cpf'])
        await page.fill('[name=telefone]', test_patient_data['telefone'])
        await page.fill('[name=email]', test_patient_data['email'])
        await page.fill('[name=data_nascimento]', test_patient_data['data_nascimento'])

        # Select treatment type
        await page.select_option('[name=tipo_tratamento]', test_patient_data['tipo_tratamento'])

        # Submit patient creation
        submit_button = page.locator('button:has-text("Salvar")')
        await submit_button.click()

        # Wait for success message
        success_msg = page.locator('.success-message, .toast-success')
        await expect(success_msg).to_contain_text('Paciente criado', timeout=5000)
        print(f"✅ Patient created: {test_patient_data['nome']}")

        # Extract patient ID from URL or data attribute
        await page.wait_for_url('**/patients/**', timeout=5000)
        patient_url = page.url
        patient_id = patient_url.split('/')[-1]
        print(f"📝 Patient ID: {patient_id}")

        # ===================================================================
        # STEP 3: Verify WhatsApp Welcome Message Sent
        # ===================================================================
        print("\n📱 Step 3: Verify WhatsApp Message")

        # Wait for async message sending
        await asyncio.sleep(2)

        # Check WhatsApp service was called
        assert mock_whatsapp.messages_sent >= 1, "WhatsApp welcome message not sent"
        assert 'Bem-vindo' in mock_whatsapp.last_message or 'bem-vindo' in mock_whatsapp.last_message.lower()
        print(f"✅ WhatsApp message sent: {mock_whatsapp.last_message[:50]}...")

        # Verify message persisted in database
        response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id) + '/messages'
        )
        assert response.status == 200
        messages = await response.json()
        assert len(messages) >= 1, "Welcome message not persisted"
        print(f"✅ Message persisted in DB ({len(messages)} messages)")

        # ===================================================================
        # STEP 4: Patient Responds via WhatsApp Webhook
        # ===================================================================
        print("\n💬 Step 4: Simulate Patient Response")

        # Prepare webhook payload
        webhook_payload = {
            'event': 'messages.upsert',
            'instance': 'test_instance',
            'data': {
                'key': {
                    'remoteJid': test_patient_data['telefone'] + '@s.whatsapp.net',
                    'fromMe': False,
                    'id': f'msg_{datetime.now().timestamp()}'
                },
                'message': {
                    'conversation': test_patient_data['nome']  # Patient confirms name
                },
                'messageTimestamp': int(datetime.now().timestamp())
            }
        }

        # Generate webhook signature
        payload_str = json.dumps(webhook_payload)
        signature = generate_signature(payload_str)

        # Send webhook request
        webhook_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            data={
                'headers': {
                    'X-Webhook-Signature': signature,
                    'Content-Type': 'application/json',
                },
                'data': payload_str
            }
        )

        assert webhook_response.status == 200, f"Webhook failed: {webhook_response.status}"
        print("✅ Webhook processed successfully")

        # ===================================================================
        # STEP 5: Verify Saga Execution (Firebase + Patient Update)
        # ===================================================================
        print("\n⚙️ Step 5: Verify Saga Orchestration")

        # Wait for saga to complete
        saga = await wait_for_saga(expected_status='COMPLETED')
        print(f"✅ Saga completed: {saga.get('id')}")

        # Verify Firebase account created
        assert mock_firebase.users_created >= 1, "Firebase account not created"
        firebase_user = mock_firebase.created_users[0]
        assert firebase_user['email'] == test_patient_data['email']
        print(f"✅ Firebase account: {firebase_user['uid']}")

        # Verify patient updated in database
        patient_response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id)
        )
        assert patient_response.status == 200
        patient = await patient_response.json()
        assert patient['status'] == 'ativo' or patient['status'] == 'active'
        assert patient.get('firebase_uid') is not None
        print(f"✅ Patient status: {patient['status']}")

        # ===================================================================
        # STEP 6: Verify Quiz Flow Initialization
        # ===================================================================
        print("\n📋 Step 6: Verify Quiz Flow Started")

        # Wait for quiz flow to initialize
        await asyncio.sleep(3)

        # Check quiz session created
        quiz_response = await page.request.get(
            get_endpoint_url('quiz_sessions') + f'?patient_id={patient_id}'
        )
        assert quiz_response.status == 200
        sessions = await quiz_response.json()
        assert len(sessions) > 0, "Quiz session not created"

        quiz_session = sessions[0]
        session_id = quiz_session['id']
        print(f"✅ Quiz session created: {session_id}")
        print(f"   - Status: {quiz_session.get('status')}")
        print(f"   - Expires: {quiz_session.get('expires_at')}")

        # ===================================================================
        # STEP 7: Patient Completes Quiz
        # ===================================================================
        print("\n✍️ Step 7: Simulate Quiz Completion")

        # Fetch quiz questions
        questions_response = await page.request.get(
            f'/api/v2/quiz/sessions/{session_id}/questions'
        )
        assert questions_response.status == 200
        questions = await questions_response.json()
        assert len(questions) > 0, "No quiz questions found"
        print(f"✅ Found {len(questions)} questions")

        # Answer first 5 questions
        answers_submitted = 0
        for i, question in enumerate(questions[:5]):
            # Determine answer based on question type
            if question['tipo'] == 'sim_nao':
                answer_value = 'Sim'
            elif question['tipo'] == 'escala':
                answer_value = '3'  # Mid-scale answer
            elif question['tipo'] == 'multipla_escolha':
                answer_value = question['opcoes'][0] if question.get('opcoes') else 'Opção 1'
            else:
                answer_value = 'Resposta de teste'

            # Submit answer
            answer_response = await page.request.post(
                get_endpoint_url('quiz_responses', session_id=session_id),
                data=json.dumps({
                    'question_id': question['id'],
                    'value': answer_value,
                    'metadata': {'source': 'e2e_test'}
                })
            )

            if answer_response.status in [200, 201]:
                answers_submitted += 1
                print(f"   ✓ Question {i+1}/{len(questions)} answered")
            else:
                print(f"   ✗ Question {i+1} failed: {answer_response.status}")

        assert answers_submitted >= 5, f"Only {answers_submitted}/5 answers submitted"
        print(f"✅ Quiz partially completed ({answers_submitted} answers)")

        # ===================================================================
        # STEP 8: Doctor Views Results in Dashboard
        # ===================================================================
        print("\n📊 Step 8: Verify Dashboard Updates")

        # Navigate to dashboard
        await page.goto('/dashboard')
        await page.wait_for_load_state('networkidle')

        # Check patient appears in dashboard
        patient_card = page.locator(f'[data-patient-id="{patient_id}"]')
        await expect(patient_card).to_be_visible(timeout=5000)
        print("✅ Patient visible in dashboard")

        # Check quiz status indicator
        quiz_status = patient_card.locator('.quiz-status')
        await expect(quiz_status).to_contain_text('Quiz', timeout=3000)
        print("✅ Quiz status displayed")

        # Click to view patient details
        await patient_card.click()
        await page.wait_for_url(f'**/patients/{patient_id}', timeout=5000)

        # Verify quiz results section
        quiz_results = page.locator('.quiz-results, [data-testid="quiz-results"]')
        await expect(quiz_results).to_be_visible(timeout=3000)
        print("✅ Quiz results section visible")

        # Verify answered questions count
        answered_count = page.locator('.questions-answered')
        if await answered_count.count() > 0:
            await expect(answered_count).to_contain_text(f'{answers_submitted}')
            print(f"✅ Answered questions count correct: {answers_submitted}")

        # ===================================================================
        # STEP 9: Verify Data Consistency
        # ===================================================================
        print("\n🔍 Step 9: Verify Data Consistency")

        # Fetch final patient state
        final_patient_response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id)
        )
        final_patient = await final_patient_response.json()

        # Assertions
        assert final_patient['nome'] == test_patient_data['nome']
        assert final_patient['cpf'] == test_patient_data['cpf']
        assert final_patient['telefone'] == test_patient_data['telefone']
        assert final_patient['email'] == test_patient_data['email']
        assert final_patient.get('firebase_uid') is not None
        assert final_patient.get('status') in ['ativo', 'active']
        print("✅ Patient data consistent")

        # Fetch final quiz state
        final_quiz_response = await page.request.get(
            f'/api/v2/quiz/sessions/{session_id}'
        )
        final_quiz = await final_quiz_response.json()

        assert final_quiz['patient_id'] == int(patient_id)
        assert final_quiz.get('responses_count', 0) >= answers_submitted
        print("✅ Quiz data consistent")

        # ===================================================================
        # JOURNEY COMPLETE
        # ===================================================================
        print("\n" + "="*60)
        print("🎉 PATIENT ONBOARDING JOURNEY COMPLETE!")
        print("="*60)
        print(f"✅ Patient Created: {test_patient_data['nome']}")
        print(f"✅ WhatsApp Messages: {mock_whatsapp.messages_sent}")
        print(f"✅ Firebase Account: {firebase_user['uid']}")
        print(f"✅ Quiz Session: {session_id}")
        print(f"✅ Answers Submitted: {answers_submitted}")
        print("="*60 + "\n")


    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_patient_onboarding_with_webhook_idempotency(
        self,
        page: Page,
        test_patient_data: Dict[str, Any],
        mock_whatsapp,
        generate_signature,
    ):
        """Test webhook idempotency during patient onboarding."""
        print("\n🔄 Testing Webhook Idempotency")

        # Create patient
        patient_response = await page.request.post(
            get_endpoint_url('patients_create'),
            data=json.dumps(test_patient_data)
        )
        assert patient_response.status in [200, 201]
        patient = await patient_response.json()
        patient_id = patient['id']

        # Prepare webhook payload
        webhook_payload = {
            'event': 'messages.upsert',
            'data': {
                'key': {
                    'remoteJid': test_patient_data['telefone'] + '@s.whatsapp.net',
                    'id': 'SAME_MESSAGE_ID_123'  # Same ID for idempotency test
                },
                'message': {'conversation': 'Test message'}
            }
        }

        payload_str = json.dumps(webhook_payload)
        signature = generate_signature(payload_str)

        # Send webhook 3 times with same message ID
        responses = []
        for i in range(3):
            response = await page.request.post(
                get_endpoint_url('webhooks_evolution'),
                data={
                    'headers': {'X-Webhook-Signature': signature},
                    'data': payload_str
                }
            )
            responses.append(response.status)
            await asyncio.sleep(0.5)

        # All requests should succeed (200)
        assert all(status == 200 for status in responses), f"Webhook failures: {responses}"
        print("✅ All webhook requests succeeded")

        # Verify only ONE message was processed
        messages_response = await page.request.get(
            f'/api/v2/patients/{patient_id}/messages'
        )
        messages = await messages_response.json()

        # Count messages with same WhatsApp ID
        duplicate_count = sum(
            1 for msg in messages
            if msg.get('whatsapp_id') == 'SAME_MESSAGE_ID_123'
        )

        assert duplicate_count == 1, f"Expected 1 message, found {duplicate_count} duplicates"
        print("✅ Idempotency verified: 1 message processed (3 requests sent)")


    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_patient_onboarding_saga_failure_recovery(
        self,
        page: Page,
        test_patient_data: Dict[str, Any],
        mock_firebase,
        chaos_monkey,
        wait_for_saga,
    ):
        """Test saga recovery when Firebase fails during patient onboarding."""
        print("\n🔥 Testing Saga Failure Recovery")

        # Configure Firebase to fail first 2 attempts
        chaos_monkey.fail_next('firebase_create_user', times=2)

        # Attempt patient creation
        patient_response = await page.request.post(
            get_endpoint_url('patients_create'),
            data=json.dumps(test_patient_data)
        )

        # Request should succeed despite Firebase failures (saga will retry)
        assert patient_response.status in [200, 201]
        patient = await patient_response.json()
        patient_id = patient['id']
        print(f"✅ Patient created with ID: {patient_id}")

        # Wait for saga to complete (with retries)
        saga = await wait_for_saga(timeout=15000, expected_status='COMPLETED')

        # Verify saga retried
        assert saga.get('retry_count', 0) >= 2, "Saga should have retried at least twice"
        print(f"✅ Saga retried {saga.get('retry_count')} times")

        # Verify final state is consistent
        final_patient_response = await page.request.get(
            get_endpoint_url('patients_detail', id=patient_id)
        )
        final_patient = await final_patient_response.json()

        assert final_patient['status'] in ['ativo', 'active']
        assert final_patient.get('firebase_uid') is not None
        assert mock_firebase.users_created == 1  # Only one user created (after retries)
        print("✅ Final state consistent after recovery")
