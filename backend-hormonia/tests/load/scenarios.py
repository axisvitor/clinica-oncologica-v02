"""
Cenários de Teste de Carga - Sistema Hormonia
=============================================

Cenários específicos para validar diferentes aspectos do sistema.

Cenários Disponíveis:
--------------------
1. Scenario 1: 100 pacientes cadastrados simultaneamente
2. Scenario 2: 1000 mensagens agendadas processadas
3. Scenario 3: 500 webhooks recebidos simultaneamente
4. Scenario 4: Dashboard sob carga pesada (múltiplos médicos)
5. Scenario 5: Stress test - Encontrar limites do sistema

Execução:
---------
# Cenário 1: Cadastro massivo
locust -f tests/load/scenarios.py Scenario1MassivePatientRegistration --host=http://localhost:8000 -u 100 -r 10 -t 3m --headless

# Cenário 2: Processamento de mensagens
locust -f tests/load/scenarios.py Scenario2MessageProcessing --host=http://localhost:8000 -u 50 -r 5 -t 5m --headless

# Cenário 3: Webhooks simultâneos
locust -f tests/load/scenarios.py Scenario3WebhookFlood --host=http://localhost:8000 -u 500 -r 50 -t 2m --headless

# Cenário 4: Dashboard carga pesada
locust -f tests/load/scenarios.py Scenario4DashboardLoad --host=http://localhost:8000 -u 200 -r 20 -t 5m --headless

# Cenário 5: Stress test
locust -f tests/load/scenarios.py Scenario5StressTest --host=http://localhost:8000 -u 1000 -r 100 --headless
"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from locust import HttpUser, task, between, events, constant, constant_throughput
from locust.exception import RescheduleTask


# ============================================================================
# Data Generators (reusado do locustfile.py)
# ============================================================================


def generate_cpf() -> str:
    """Gera CPF válido para testes."""
    cpf = [random.randint(0, 9) for _ in range(9)]
    sum_1 = sum((10 - i) * cpf[i] for i in range(9))
    digit_1 = 11 - (sum_1 % 11)
    if digit_1 >= 10:
        digit_1 = 0
    cpf.append(digit_1)
    sum_2 = sum((11 - i) * cpf[i] for i in range(10))
    digit_2 = 11 - (sum_2 % 11)
    if digit_2 >= 10:
        digit_2 = 0
    cpf.append(digit_2)
    return "".join(map(str, cpf))


def generate_phone() -> str:
    """Gera telefone celular válido."""
    ddd = random.choice([11, 21, 31, 41, 51, 61, 71, 81, 85, 91])
    number = random.randint(900000000, 999999999)
    return f"{ddd}{number}"


def generate_patient_data() -> Dict[str, Any]:
    """Gera dados de paciente para teste."""
    first_names = [
        "João",
        "Maria",
        "José",
        "Ana",
        "Pedro",
        "Mariana",
        "Carlos",
        "Julia",
        "Lucas",
        "Beatriz",
        "Rafael",
        "Camila",
    ]
    last_names = [
        "Silva",
        "Santos",
        "Oliveira",
        "Souza",
        "Pereira",
        "Costa",
        "Rodrigues",
        "Almeida",
        "Nascimento",
        "Lima",
    ]

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)

    return {
        "name": f"{first_name} {last_name}",
        "cpf": generate_cpf(),
        "phone": generate_phone(),
        "email": f"{first_name.lower()}.{last_name.lower()}.{random.randint(1000, 9999)}@test.com",
        "birth_date": f"19{random.randint(50, 90)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        "cancer_type": random.choice(
            ["mama", "prostata", "pulmao", "colorretal", "outro"]
        ),
        "diagnosis_date": datetime.now().strftime("%Y-%m-%d"),
        "treatment_status": "em_tratamento",
    }


# ============================================================================
# Scenario 1: Cadastro Massivo de Pacientes
# ============================================================================


class Scenario1MassivePatientRegistration(HttpUser):
    """
    Cenário 1: 100 pacientes cadastrados simultaneamente

    Objetivo: Validar capacidade do sistema de processar múltiplos cadastros
    simultâneos sem degradação de performance.

    Características:
    - 100 usuários concorrentes
    - Cada usuário cria 1 paciente
    - Taxa de chegada: 10 usuários/segundo
    - Duração: 3 minutos

    Critérios de Sucesso:
    - P95 < 500ms
    - Taxa de erro < 0.1%
    - Todos os pacientes criados com sucesso
    - Saga Pattern funciona corretamente
    """

    wait_time = constant(0)  # Sem espera - cadastro imediato
    admin_token = None

    def on_start(self):
        """Login e preparação."""
        self.login()

    def login(self):
        """Faz login como admin."""
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
            name="[S1] Login",
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        else:
            raise RescheduleTask()

    @task
    def create_patient_with_saga(self):
        """Cria paciente utilizando Saga Pattern."""
        patient_data = generate_patient_data()

        start_time = time.time()
        response = self.client.post(
            "/api/v2/patients",
            json=patient_data,
            name="[S1] Create Patient (Saga)",
        )

        if response.status_code == 201:
            patient = response.json()
            patient_id = patient.get("id")

            # Verificar se o paciente foi criado corretamente
            verification = self.client.get(
                f"/api/v2/patients/{patient_id}",
                name="[S1] Verify Patient Created",
            )

            if verification.status_code == 200:
                print(
                    f"✅ Paciente {patient_id} criado em {(time.time() - start_time) * 1000:.0f}ms"
                )
        else:
            print(f"❌ Falha ao criar paciente: {response.status_code}")

        # Parar após criar o paciente
        self.environment.runner.quit()


# ============================================================================
# Scenario 2: Processamento de Mensagens
# ============================================================================


class Scenario2MessageProcessing(HttpUser):
    """
    Cenário 2: 1000 mensagens agendadas processadas

    Objetivo: Validar capacidade do sistema de processar grande volume
    de mensagens agendadas.

    Características:
    - 50 usuários concorrentes
    - 1000 mensagens total (20 por usuário)
    - Taxa de chegada: 5 usuários/segundo
    - Duração: 5 minutos

    Critérios de Sucesso:
    - P95 < 500ms para agendamento
    - Taxa de erro < 0.1%
    - Idempotência funcionando (sem duplicatas)
    - Rate limiting respeitado
    """

    wait_time = between(0.5, 1.5)
    admin_token = None
    messages_created = 0
    max_messages = 20

    def on_start(self):
        """Login e preparação."""
        self.login()

    def login(self):
        """Faz login como admin."""
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
            name="[S2] Login",
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        else:
            raise RescheduleTask()

    @task(10)
    def schedule_message(self):
        """Agenda mensagem com idempotency key."""
        if self.messages_created >= self.max_messages:
            return

        idempotency_key = (
            f"test_msg_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        )

        message_data = {
            "patient_id": random.randint(1, 100),
            "content": f"Mensagem de teste {idempotency_key}",
            "scheduled_for": (datetime.now() + timedelta(hours=1)).isoformat(),
            "template_id": random.choice([1, 2, 3, 4]),
        }

        response = self.client.post(
            "/api/v2/messages/schedule",
            json=message_data,
            headers={"X-Idempotency-Key": idempotency_key},
            name="[S2] Schedule Message (Idempotent)",
        )

        if response.status_code in [200, 201]:
            self.messages_created += 1
            print(f"✅ Mensagem {self.messages_created}/{self.max_messages} agendada")

    @task(3)
    def list_scheduled_messages(self):
        """Lista mensagens agendadas."""
        self.client.get(
            "/api/v2/messages",
            params={"page": 1, "size": 50, "status": "scheduled"},
            name="[S2] List Scheduled Messages",
        )


# ============================================================================
# Scenario 3: Flood de Webhooks
# ============================================================================


class Scenario3WebhookFlood(HttpUser):
    """
    Cenário 3: 500 webhooks recebidos simultaneamente

    Objetivo: Validar capacidade do sistema de processar grande volume
    de webhooks simultâneos sem perda de dados.

    Características:
    - 500 usuários concorrentes (simulando eventos externos)
    - Taxa de chegada: 50 webhooks/segundo
    - Duração: 2 minutos

    Critérios de Sucesso:
    - P95 < 200ms (webhooks devem ser rápidos)
    - Taxa de erro < 0.1%
    - HMAC validation funcionando
    - Nenhum webhook perdido
    """

    wait_time = constant(0.1)  # Webhooks chegam rapidamente

    @task
    def send_webhook(self):
        """Envia webhook de evento."""
        event_types = [
            "message.received",
            "message.sent",
            "message.delivered",
            "message.read",
            "message.failed",
        ]

        payload = {
            "event": random.choice(event_types),
            "timestamp": datetime.now().isoformat(),
            "data": {
                "from": generate_phone(),
                "message": f"Webhook test {random.randint(10000, 99999)}",
                "message_id": f"msg_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
            },
        }

        # HMAC signature (simplificado)
        signature = f"test_sig_{random.randint(100000, 999999)}"

        self.client.post(
            "/webhooks/evolution",
            json=payload,
            headers={"X-Webhook-Signature": signature},
            name="[S3] Receive Webhook",
            catch_response=True,
        )


# ============================================================================
# Scenario 4: Dashboard sob Carga Pesada
# ============================================================================


class Scenario4DashboardLoad(HttpUser):
    """
    Cenário 4: Dashboard com múltiplos médicos acessando

    Objetivo: Validar performance do dashboard com múltiplos usuários
    consultando métricas e analytics simultaneamente.

    Características:
    - 200 usuários concorrentes (médicos)
    - Consultas a dashboards, analytics e relatórios
    - Taxa de chegada: 20 usuários/segundo
    - Duração: 5 minutos

    Critérios de Sucesso:
    - P95 < 500ms
    - Cache funcionando (redução de queries)
    - Queries N+1 eliminadas
    - Eager loading funcionando
    """

    wait_time = between(2, 5)
    admin_token = None

    def on_start(self):
        """Login e preparação."""
        self.login()

    def login(self):
        """Faz login como admin."""
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
            name="[S4] Login",
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        else:
            raise RescheduleTask()

    @task(10)
    def get_dashboard_metrics(self):
        """Obtém métricas principais do dashboard."""
        self.client.get(
            "/api/v2/dashboard/metrics",
            name="[S4] Dashboard Metrics",
        )

    @task(8)
    def get_patient_analytics(self):
        """Obtém analytics de pacientes."""
        periods = ["7d", "30d", "90d"]
        self.client.get(
            "/api/v2/analytics/patients",
            params={"period": random.choice(periods)},
            name="[S4] Patient Analytics",
        )

    @task(5)
    def get_message_analytics(self):
        """Obtém analytics de mensagens."""
        self.client.get(
            "/api/v2/analytics/messages",
            params={"period": "30d"},
            name="[S4] Message Analytics",
        )

    @task(3)
    def get_dlq_stats(self):
        """Obtém estatísticas da DLQ."""
        self.client.get(
            "/admin/dlq/stats",
            name="[S4] DLQ Stats",
        )

    @task(2)
    def list_patients_with_messages(self):
        """Lista pacientes com mensagens (eager loading test)."""
        self.client.get(
            "/api/v2/patients",
            params={"page": 1, "size": 20, "include": "messages,flows"},
            name="[S4] Patients with Relations",
        )


# ============================================================================
# Scenario 5: Stress Test - Encontrar Limites
# ============================================================================


class Scenario5StressTest(HttpUser):
    """
    Cenário 5: Stress Test - Encontrar limites do sistema

    Objetivo: Encontrar o ponto de quebra do sistema aumentando
    gradualmente a carga até falhar.

    Características:
    - Começa com 100 usuários
    - Aumenta 100 usuários a cada minuto
    - Continua até atingir taxa de erro > 5%
    - Mix de todas as operações

    Critérios de Sucesso:
    - Identificar limite máximo de usuários concorrentes
    - Identificar gargalos (DB, Redis, CPU, etc)
    - Sistema deve degradar graciosamente
    """

    wait_time = between(0.5, 2)
    admin_token = None

    def on_start(self):
        """Login e preparação."""
        self.login()

    def login(self):
        """Faz login como admin."""
        response = self.client.post(
            "/auth/login",
            json={"email": "admin@test.com", "password": "admin123"},
            name="[S5] Login",
        )
        if response.status_code == 200:
            self.admin_token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.admin_token}"})
        else:
            raise RescheduleTask()

    @task(3)
    def create_patient(self):
        """Cria paciente."""
        patient_data = generate_patient_data()
        self.client.post(
            "/api/v2/patients",
            json=patient_data,
            name="[S5] Create Patient",
        )

    @task(5)
    def list_patients(self):
        """Lista pacientes."""
        self.client.get(
            "/api/v2/patients",
            params={"page": random.randint(1, 10), "size": 20},
            name="[S5] List Patients",
        )

    @task(4)
    def schedule_message(self):
        """Agenda mensagem."""
        message_data = {
            "patient_id": random.randint(1, 1000),
            "content": f"Stress test message {random.randint(1000, 9999)}",
            "scheduled_for": (datetime.now() + timedelta(hours=1)).isoformat(),
        }
        self.client.post(
            "/api/v2/messages/schedule",
            json=message_data,
            name="[S5] Schedule Message",
        )

    @task(8)
    def get_dashboard(self):
        """Obtém métricas do dashboard."""
        self.client.get(
            "/api/v2/dashboard/metrics",
            name="[S5] Dashboard",
        )

    @task(2)
    def send_webhook(self):
        """Envia webhook."""
        payload = {
            "event": "message.received",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "from": generate_phone(),
                "message": f"Stress test webhook {random.randint(1000, 9999)}",
            },
        }
        self.client.post(
            "/webhooks/evolution",
            json=payload,
            name="[S5] Webhook",
        )


# ============================================================================
# Event Hooks
# ============================================================================


@events.test_start.add_listener
def on_scenario_start(environment, **kwargs):
    """Executado quando o cenário inicia."""
    print("\n" + "=" * 80)
    print("🎯 INICIANDO CENÁRIO DE TESTE ESPECÍFICO")
    print("=" * 80)
    print(f"Host: {environment.host}")
    print(
        f"Cenário: {environment.runner.user_classes[0].__name__ if environment.runner.user_classes else 'N/A'}"
    )
    print("=" * 80 + "\n")


@events.test_stop.add_listener
def on_scenario_stop(environment, **kwargs):
    """Executado quando o cenário termina."""
    print("\n" + "=" * 80)
    print("✅ CENÁRIO FINALIZADO")
    print("=" * 80)

    stats = environment.stats
    print(f"\nTotal de Requisições: {stats.total.num_requests}")
    print(f"Total de Falhas: {stats.total.num_failures}")
    print(f"Taxa de Erro: {stats.total.fail_ratio * 100:.2f}%")
    print(f"P50: {stats.total.get_response_time_percentile(0.50):.2f}ms")
    print(f"P95: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"P99: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print("=" * 80 + "\n")
