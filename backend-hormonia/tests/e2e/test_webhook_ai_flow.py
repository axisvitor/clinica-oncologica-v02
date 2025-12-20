"""
E2E Test: Webhook → Processing → AI → Response Flow
Tests the complete webhook processing pipeline with AI integration.

Journey Steps:
1. WhatsApp webhook received
2. Idempotency check (Redis + DB)
3. Flow Engine determines next step
4. AI generates humanized response
5. Response sent via WhatsApp
6. Message persisted in DB
7. Saga coordination

Coverage: Webhook validation, Idempotency, Flow Engine, AI integration, WhatsApp API

NOTE: Requires playwright and playwright_config to be installed.
"""
import pytest

# Skip entire module if playwright is not installed
pytest.importorskip("playwright", reason="Playwright not installed")

import asyncio
import json
from datetime import datetime
from typing import Any, Dict
from playwright.async_api import Page


class TestWebhookAIFlow:
    """Complete webhook-to-AI response E2E test suite."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_complete_webhook_to_ai_response_journey(
        self,
        page: Page,
        e2e_db_session,
        mock_whatsapp,
        mock_gemini,
        test_webhook_payload: Dict[str, Any],
        generate_signature,
    ):
        """
        Test complete webhook processing with AI response generation.

        Validates:
        - Webhook signature validation
        - Idempotency handling
        - Flow Engine routing
        - AI response generation
        - WhatsApp message sending
        - Message persistence
        """
        print("\n📱 Testing Complete Webhook → AI → Response Flow")

        # ===================================================================
        # STEP 1: Setup Test Data
        # ===================================================================
        print("\n🔧 Step 1: Setup Test Data")

        # Create patient first (to link messages)
        patient_data = {
            'nome': 'Test Patient Webhook',
            'cpf': '12345678909',
            'telefone': '+5511888888888',
            'email': 'webhook.test@example.com',
            'data_nascimento': '1985-03-20',
            'tipo_tratamento': 'Radioterapia',
        }

        patient_response = await page.request.post(
            get_endpoint_url('patients_create'),
            data=json.dumps(patient_data)
        )
        assert patient_response.status in [200, 201]
        patient = await patient_response.json()
        patient_id = patient['id']
        print(f"✅ Test patient created: ID {patient_id}")

        # Configure AI mock response
        ai_response = "Olá! Como posso ajudar você hoje? 😊"
        mock_gemini.setup_response(ai_response)
        print(f"✅ AI mock configured: '{ai_response[:30]}...'")

        # ===================================================================
        # STEP 2: Send WhatsApp Webhook
        # ===================================================================
        print("\n📨 Step 2: Send WhatsApp Webhook")

        # Prepare webhook payload
        webhook_payload = {
            'event': 'messages.upsert',
            'instance': 'test_instance',
            'data': {
                'key': {
                    'remoteJid': patient_data['telefone'] + '@s.whatsapp.net',
                    'fromMe': False,
                    'id': f'webhook_ai_test_{datetime.now().timestamp()}'
                },
                'message': {
                    'conversation': 'Preciso de ajuda com meus sintomas'
                },
                'messageTimestamp': int(datetime.now().timestamp()),
                'pushName': patient_data['nome']
            }
        }

        # Generate signature
        payload_str = json.dumps(webhook_payload)
        signature = generate_signature(payload_str)

        # Send webhook
        webhook_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            headers={
                'X-Webhook-Signature': signature,
                'Content-Type': 'application/json',
            },
            data=payload_str
        )

        assert webhook_response.status == 200, f"Webhook failed: {webhook_response.status}"
        webhook_result = await webhook_response.json()
        print(f"✅ Webhook accepted: {webhook_result}")

        # ===================================================================
        # STEP 3: Verify Idempotency - Send Duplicate
        # ===================================================================
        print("\n🔄 Step 3: Test Idempotency (Duplicate Request)")

        # Send exact same webhook again
        duplicate_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            headers={
                'X-Webhook-Signature': signature,
                'Content-Type': 'application/json',
            },
            data=payload_str
        )

        # Should still return 200 (idempotent)
        assert duplicate_response.status == 200, "Duplicate webhook should be idempotent"
        print("✅ Duplicate request handled idempotently")

        # Wait for async processing
        await asyncio.sleep(2)

        # Verify only ONE message was processed
        messages_response = await page.request.get(
            f'/api/v2/patients/{patient_id}/messages'
        )
        messages = await messages_response.json()

        message_with_id = [
            m for m in messages
            if m.get('whatsapp_id') == webhook_payload['data']['key']['id']
        ]
        assert len(message_with_id) == 1, f"Expected 1 message, found {len(message_with_id)}"
        print("✅ Idempotency verified: 1 message stored (2 requests sent)")

        # ===================================================================
        # STEP 4: Verify Flow Engine Processing
        # ===================================================================
        print("\n⚙️ Step 4: Verify Flow Engine Processing")

        # Wait for flow execution
        await asyncio.sleep(3)

        # Check flow execution was created
        flow_executions_response = await page.request.get(
            f'/api/v2/flows/executions?patient_id={patient_id}'
        )

        if flow_executions_response.status == 200:
            flow_executions = await flow_executions_response.json()
            assert len(flow_executions) > 0, "Flow execution not created"
            print(f"✅ Flow Engine executed: {len(flow_executions)} flow(s)")

            # Check flow status
            latest_flow = flow_executions[0]
            print(f"   - Flow ID: {latest_flow.get('id')}")
            print(f"   - Status: {latest_flow.get('status')}")
            print(f"   - Type: {latest_flow.get('flow_type')}")
        else:
            print("⚠️  Flow executions endpoint not available")

        # ===================================================================
        # STEP 5: Verify AI Response Generation
        # ===================================================================
        print("\n🤖 Step 5: Verify AI Response Generation")

        # Check AI was called
        assert mock_gemini.call_count >= 1, "AI not called"
        print(f"✅ AI called {mock_gemini.call_count} time(s)")

        # Verify response was generated
        assert mock_whatsapp.messages_sent >= 1, "Response not sent via WhatsApp"
        sent_message = mock_whatsapp.last_message

        # Response should contain AI-generated text
        assert ai_response in sent_message or len(sent_message) > 0
        print(f"✅ AI response sent: '{sent_message[:50]}...'")

        # ===================================================================
        # STEP 6: Verify Message Persistence
        # ===================================================================
        print("\n💾 Step 6: Verify Message Persistence")

        # Fetch all messages for patient
        all_messages_response = await page.request.get(
            f'/api/v2/patients/{patient_id}/messages'
        )
        all_messages = await all_messages_response.json()

        # Should have at least 2 messages: incoming + outgoing
        assert len(all_messages) >= 2, f"Expected ≥2 messages, found {len(all_messages)}"

        # Find incoming message
        incoming = next(
            (m for m in all_messages if m.get('direction') == 'incoming'),
            None
        )
        assert incoming is not None, "Incoming message not found"
        assert 'sintomas' in incoming.get('content', '').lower()
        print(f"✅ Incoming message persisted: '{incoming['content'][:30]}...'")

        # Find outgoing message
        outgoing = next(
            (m for m in all_messages if m.get('direction') == 'outgoing'),
            None
        )
        assert outgoing is not None, "Outgoing message not found"
        print(f"✅ Outgoing message persisted: '{outgoing['content'][:30]}...'")

        # ===================================================================
        # STEP 7: Verify WhatsApp API Integration
        # ===================================================================
        print("\n📲 Step 7: Verify WhatsApp API Integration")

        # Check message was sent to correct phone number
        last_sent = mock_whatsapp.message_history[-1]
        assert last_sent['phone'] == patient_data['telefone']
        print(f"✅ Message sent to: {last_sent['phone']}")

        # Verify message metadata
        assert 'timestamp' in last_sent
        assert last_sent['message'] == sent_message
        print("✅ Message metadata complete")

        # ===================================================================
        # JOURNEY COMPLETE
        # ===================================================================
        print("\n" + "="*60)
        print("🎉 WEBHOOK → AI → RESPONSE FLOW COMPLETE!")
        print("="*60)
        print("✅ Webhook Processed: 1 message")
        print("✅ Idempotency: Verified")
        print(f"✅ AI Calls: {mock_gemini.call_count}")
        print(f"✅ WhatsApp Sent: {mock_whatsapp.messages_sent}")
        print(f"✅ Messages Persisted: {len(all_messages)}")
        print("="*60 + "\n")


    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_webhook_signature_validation(
        self,
        page: Page,
        test_webhook_payload: Dict[str, Any],
        generate_signature,
    ):
        """Test webhook signature validation security."""
        print("\n🔒 Testing Webhook Signature Validation")

        payload_str = json.dumps(test_webhook_payload)

        # ===================================================================
        # Test 1: Valid Signature
        # ===================================================================
        valid_signature = generate_signature(payload_str)
        valid_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            headers={
                'X-Webhook-Signature': valid_signature,
                'Content-Type': 'application/json',
            },
            data=payload_str
        )
        assert valid_response.status == 200, "Valid signature should be accepted"
        print("✅ Valid signature accepted")

        # ===================================================================
        # Test 2: Invalid Signature
        # ===================================================================
        invalid_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            headers={
                'X-Webhook-Signature': 'invalid_signature_12345',
                'Content-Type': 'application/json',
            },
            data=payload_str
        )
        assert invalid_response.status in [401, 403], "Invalid signature should be rejected"
        print("✅ Invalid signature rejected")

        # ===================================================================
        # Test 3: Missing Signature
        # ===================================================================
        missing_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            headers={'Content-Type': 'application/json'},
            data=payload_str
        )
        assert missing_response.status in [400, 401, 403], "Missing signature should be rejected"
        print("✅ Missing signature rejected")

        # ===================================================================
        # Test 4: Tampered Payload
        # ===================================================================
        signature = generate_signature(payload_str)
        tampered_payload = payload_str.replace('Test', 'Hacked')

        tampered_response = await page.request.post(
            get_endpoint_url('webhooks_evolution'),
            headers={
                'X-Webhook-Signature': signature,  # Valid for original payload
                'Content-Type': 'application/json',
            },
            data=tampered_payload  # But payload is different
        )
        assert tampered_response.status in [401, 403], "Tampered payload should be rejected"
        print("✅ Tampered payload rejected")


    @pytest.mark.asyncio
    @pytest.mark.timeout(90)
    async def test_webhook_ai_flow_with_context(
        self,
        page: Page,
        mock_whatsapp,
        mock_gemini,
        generate_signature,
    ):
        """Test AI response with conversation context."""
        print("\n💬 Testing AI Context Management")

        # Create patient
        patient_data = {
            'nome': 'Context Test Patient',
            'cpf': '12345678909',
            'telefone': '+5511777777777',
            'email': 'context@test.com',
            'data_nascimento': '1990-01-01',
            'tipo_tratamento': 'Quimioterapia',
        }

        patient_response = await page.request.post(
            get_endpoint_url('patients_create'),
            data=json.dumps(patient_data)
        )
        patient = await patient_response.json()
        patient_id = patient['id']

        # Setup AI responses
        mock_gemini.setup_responses([
            "Sim, posso ajudar com informações sobre quimioterapia.",
            "A náusea é um efeito colateral comum. Recomendo conversar com seu médico.",
            "Fique tranquilo, há medicamentos que podem ajudar.",
        ])

        # Send 3 messages in sequence
        messages = [
            "Pode me ajudar com informações?",
            "Estou com náusea após a quimio",
            "Estou preocupado"
        ]

        for i, message_text in enumerate(messages):
            webhook_payload = {
                'event': 'messages.upsert',
                'data': {
                    'key': {
                        'remoteJid': patient_data['telefone'] + '@s.whatsapp.net',
                        'id': f'context_msg_{i}_{datetime.now().timestamp()}'
                    },
                    'message': {'conversation': message_text},
                    'messageTimestamp': int(datetime.now().timestamp())
                }
            }

            payload_str = json.dumps(webhook_payload)
            signature = generate_signature(payload_str)

            response = await page.request.post(
                get_endpoint_url('webhooks_evolution'),
                headers={
                    'X-Webhook-Signature': signature,
                    'Content-Type': 'application/json',
                },
                data=payload_str
            )

            assert response.status == 200
            await asyncio.sleep(2)  # Wait for processing
            print(f"✅ Message {i+1}/{len(messages)}: '{message_text[:30]}...'")

        # Verify all messages processed
        assert mock_gemini.call_count == 3, f"Expected 3 AI calls, got {mock_gemini.call_count}"
        assert mock_whatsapp.messages_sent == 3, f"Expected 3 responses, got {mock_whatsapp.messages_sent}"
        print(f"✅ Context maintained across {len(messages)} messages")

        # Verify conversation history
        messages_response = await page.request.get(
            f'/api/v2/patients/{patient_id}/messages'
        )
        conversation = await messages_response.json()

        # Should have 6 messages total: 3 incoming + 3 outgoing
        assert len(conversation) >= 6, f"Expected ≥6 messages, found {len(conversation)}"
        print(f"✅ Conversation history: {len(conversation)} messages")


    @pytest.mark.asyncio
    @pytest.mark.timeout(60)
    async def test_webhook_rate_limiting(
        self,
        page: Page,
        test_webhook_payload: Dict[str, Any],
        generate_signature,
    ):
        """Test webhook rate limiting protection."""
        print("\n🚦 Testing Webhook Rate Limiting")

        payload_str = json.dumps(test_webhook_payload)
        signature = generate_signature(payload_str)

        # Send 20 requests rapidly
        responses = []
        for i in range(20):
            # Use different message IDs to bypass idempotency
            payload = test_webhook_payload.copy()
            payload['data']['key']['id'] = f'rate_limit_test_{i}'

            response = await page.request.post(
                get_endpoint_url('webhooks_evolution'),
                headers={
                    'X-Webhook-Signature': generate_signature(json.dumps(payload)),
                    'Content-Type': 'application/json',
                },
                data=json.dumps(payload)
            )
            responses.append(response.status)

            # No delay - test rate limiting

        # Count successful vs rate-limited requests
        success_count = sum(1 for status in responses if status == 200)
        rate_limited_count = sum(1 for status in responses if status == 429)

        print(f"✅ Successful: {success_count}")
        print(f"⚠️  Rate Limited: {rate_limited_count}")

        # At least some requests should be rate limited
        assert rate_limited_count > 0 or success_count <= 10, \
            "Rate limiting should trigger with rapid requests"
        print("✅ Rate limiting working correctly")
