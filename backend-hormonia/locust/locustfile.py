"""Load testing scenarios for Backend Hormonia.

This module defines load testing scenarios using Locust to validate
system performance under various load conditions.

Test Scenarios:
1. PatientOnboardingUser - Simulates patient management workflow
2. QuizEngineUser - Tests quiz flow engine
3. WebhookUser - Simulates WhatsApp webhook traffic
4. APIHealthUser - Basic health check monitoring

Usage:
    # Run with web UI
    locust -f locustfile.py --host=http://localhost:8000

    # Headless mode
    locust -f locustfile.py --headless -u 100 -r 10 --run-time 5m

    # Specific user class
    locust -f locustfile.py PatientOnboardingUser --headless -u 50 -r 5
"""

from locust import HttpUser, task, between, events
import random
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatientOnboardingUser(HttpUser):
    """Simulate patient onboarding and management workflow.

    This user class simulates the typical workflow of a healthcare
    professional managing patients in the system.

    Workflow:
    1. Login to get JWT token
    2. Create new patients (most common)
    3. List patients with pagination
    4. View patient details
    5. Send messages to patients
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    weight = 3  # This user type is 3x more likely than others

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.headers = {}
        self.patient_ids = []

    def on_start(self):
        """Login and get JWT token before starting tasks."""
        logger.info("PatientOnboardingUser: Starting session")

        response = self.client.post(
            "/api/v2/auth/login",
            json={
                "email": "doctor@example.com",
                "password": "test123"
            },
            name="/api/v2/auth/login [POST]"
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
            logger.info("PatientOnboardingUser: Login successful")
        else:
            logger.error(f"PatientOnboardingUser: Login failed - {response.status_code}")

    @task(5)  # Weight 5 - most common operation
    def create_patient(self):
        """Test patient creation endpoint.

        Simulates creating a new patient with realistic data.
        """
        if not self.token:
            return

        cpf = f"{random.randint(10000000000, 99999999999)}"
        patient_data = {
            "name": f"Test Patient {random.randint(1000, 9999)}",
            "cpf": cpf,
            "birth_date": self._random_birth_date(),
            "phone": f"+5511{random.randint(900000000, 999999999)}",
            "email": f"patient{cpf}@example.com",
            "metadata": {
                "source": "load_test",
                "test_run": datetime.now().isoformat()
            }
        }

        with self.client.post(
            "/api/v2/patients",
            headers=self.headers,
            json=patient_data,
            name="/api/v2/patients [POST]",
            catch_response=True
        ) as response:
            if response.status_code == 201:
                data = response.json()
                patient_id = data.get("id")
                if patient_id:
                    self.patient_ids.append(patient_id)
                response.success()
            elif response.status_code == 409:
                # CPF conflict is expected in load tests
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

    @task(3)  # Weight 3
    def list_patients(self):
        """Test patient listing with pagination.

        Simulates browsing through patient lists.
        """
        if not self.token:
            return

        limit = random.choice([10, 25, 50, 100])
        offset = random.randint(0, 200)

        self.client.get(
            f"/api/v2/patients?limit={limit}&offset={offset}",
            headers=self.headers,
            name="/api/v2/patients [GET]"
        )

    @task(2)  # Weight 2
    def search_patients(self):
        """Test patient search functionality."""
        if not self.token:
            return

        search_terms = ["Silva", "Santos", "Test", "Patient"]
        search = random.choice(search_terms)

        self.client.get(
            f"/api/v2/patients?search={search}&limit=20",
            headers=self.headers,
            name="/api/v2/patients?search [GET]"
        )

    @task(2)  # Weight 2
    def get_patient_details(self):
        """Test patient details endpoint.

        Retrieves full patient information including metadata.
        """
        if not self.token:
            return

        # Use created patient or fallback to mock UUID
        patient_id = (
            random.choice(self.patient_ids)
            if self.patient_ids
            else "123e4567-e89b-12d3-a456-426614174000"
        )

        self.client.get(
            f"/api/v2/patients/{patient_id}",
            headers=self.headers,
            name="/api/v2/patients/{id} [GET]"
        )

    @task(1)  # Weight 1
    def send_message(self):
        """Test message sending endpoint.

        Simulates sending WhatsApp messages to patients.
        """
        if not self.token:
            return

        patient_id = (
            random.choice(self.patient_ids)
            if self.patient_ids
            else "123e4567-e89b-12d3-a456-426614174000"
        )

        messages = [
            "Olá! Lembre-se de tomar seus medicamentos.",
            "Seu próximo questionário está disponível.",
            "Como você está se sentindo hoje?",
            "Importante: consulta agendada para amanhã."
        ]

        self.client.post(
            f"/api/v2/patients/{patient_id}/messages",
            headers=self.headers,
            json={
                "content": random.choice(messages),
                "message_type": "manual"
            },
            name="/api/v2/patients/{id}/messages [POST]"
        )

    def _random_birth_date(self) -> str:
        """Generate random birth date between 1950 and 2005."""
        start_date = datetime(1950, 1, 1)
        end_date = datetime(2005, 12, 31)

        time_between = end_date - start_date
        days_between = time_between.days
        random_days = random.randrange(days_between)

        birth_date = start_date + timedelta(days=random_days)
        return birth_date.strftime("%Y-%m-%d")


class QuizEngineUser(HttpUser):
    """Simulate quiz flow engine interactions.

    Tests the quiz response submission and flow progression.
    """

    wait_time = between(2, 5)
    weight = 2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.headers = {}
        self.session_id = None

    def on_start(self):
        """Login and initialize quiz session."""
        response = self.client.post(
            "/api/v2/auth/login",
            json={
                "email": "patient@example.com",
                "password": "test123"
            }
        )

        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def submit_quiz_response(self):
        """Test quiz response submission."""
        if not self.token:
            return

        response_data = {
            "question_id": f"q_{random.randint(1, 50)}",
            "answer": random.choice(["sim", "não", "às vezes"]),
            "metadata": {
                "response_time_ms": random.randint(2000, 30000)
            }
        }

        self.client.post(
            "/api/v2/quiz/responses",
            headers=self.headers,
            json=response_data,
            name="/api/v2/quiz/responses [POST]"
        )

    @task(1)
    def get_quiz_status(self):
        """Check quiz session status."""
        if not self.token:
            return

        self.client.get(
            "/api/v2/quiz/status",
            headers=self.headers,
            name="/api/v2/quiz/status [GET]"
        )


class WebhookUser(HttpUser):
    """Simulate webhook traffic from WhatsApp Evolution API.

    This user class simulates incoming webhooks from the WhatsApp
    Evolution API, testing the webhook processing pipeline.
    """

    wait_time = between(0.5, 2)  # Webhooks come in bursts
    weight = 1

    @task
    def process_message_webhook(self):
        """Test message received webhook processing."""
        phone_numbers = [
            "5511987654321",
            "5511912345678",
            "5521987654321",
            "5531987654321"
        ]

        messages = [
            "Olá, preciso de ajuda",
            "Sim",
            "Não",
            "Obrigado",
            "Como faço para marcar consulta?"
        ]

        webhook_data = {
            "event": "message.received",
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": f"{random.choice(phone_numbers)}@s.whatsapp.net",
                    "fromMe": False,
                    "id": f"msg_{random.randint(100000, 999999)}"
                },
                "message": {
                    "conversation": random.choice(messages)
                },
                "messageTimestamp": int(datetime.now().timestamp())
            }
        }

        self.client.post(
            "/api/webhooks/evolution",
            json=webhook_data,
            headers={
                "X-Webhook-Signature": "test-signature",
                "Content-Type": "application/json"
            },
            name="/api/webhooks/evolution [POST]"
        )

    @task
    def process_status_webhook(self):
        """Test message status webhook (delivery, read, etc.)."""
        webhook_data = {
            "event": "message.status",
            "instance": "clinica-hormonia",
            "data": {
                "status": random.choice(["sent", "delivered", "read"]),
                "messageId": f"msg_{random.randint(100000, 999999)}"
            }
        }

        self.client.post(
            "/api/webhooks/evolution",
            json=webhook_data,
            headers={
                "X-Webhook-Signature": "test-signature",
                "Content-Type": "application/json"
            },
            name="/api/webhooks/evolution/status [POST]"
        )


class APIHealthUser(HttpUser):
    """Monitor API health and basic endpoints.

    Lightweight user for continuous health monitoring.
    """

    wait_time = between(5, 10)
    weight = 1

    @task(5)
    def health_check(self):
        """Test health check endpoint."""
        self.client.get("/api/v2/health", name="/api/v2/health [GET]")

    @task(2)
    def health_detailed(self):
        """Test detailed health check."""
        self.client.get(
            "/api/v2/health/detailed",
            name="/api/v2/health/detailed [GET]"
        )

    @task(1)
    def openapi_spec(self):
        """Test OpenAPI spec endpoint."""
        self.client.get("/openapi.json", name="/openapi.json [GET]")


# Event listeners for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Log when load test starts."""
    logger.info("="*80)
    logger.info("🚀 LOAD TEST STARTING")
    logger.info(f"Host: {environment.host}")
    logger.info(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    logger.info("="*80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Log when load test stops."""
    logger.info("="*80)
    logger.info("🏁 LOAD TEST COMPLETED")
    logger.info("="*80)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log slow requests (>1000ms)."""
    if response_time > 1000:
        logger.warning(
            f"⚠️  SLOW REQUEST: {request_type} {name} - {response_time:.0f}ms"
        )
