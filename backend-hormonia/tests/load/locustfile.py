"""
Locust Load Testing - Sistema Hormonia
======================================

Testes de carga para validar performance e escalabilidade do sistema.

Cenários de Teste:
- Cadastro massivo de pacientes
- Processamento de mensagens agendadas
- Webhooks simultâneos
- Consultas de dashboard

Execução:
---------
# Teste básico (10 usuários)
locust -f tests/load/locustfile.py --host=http://localhost:8000

# Teste de carga pesada (100 usuários)
locust -f tests/load/locustfile.py --host=http://localhost:8000 -u 100 -r 10

# Headless com duração
locust -f tests/load/locustfile.py --host=http://localhost:8000 -u 100 -r 10 -t 5m --headless

# Com CSV de resultados
locust -f tests/load/locustfile.py --host=http://localhost:8000 -u 100 -r 10 -t 5m --headless --csv=results

Métricas Alvo:
--------------
- P95 response time < 500ms
- Taxa de erro < 0.1%
- Pool de conexões < 80% utilization
- Redis memory < 70% utilization
- CPU < 70% utilization
"""

import json
import random
import time
from datetime import datetime
from typing import Dict, Any

from locust import HttpUser, TaskSet, task, between, events
from locust.exception import RescheduleTask


# ============================================================================
# Configuration
# ============================================================================

# Admin credentials (use test environment)
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# Test data generation
FIRST_NAMES = [
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
    "Gabriel",
    "Larissa",
    "Fernando",
]

LAST_NAMES = [
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
    "Araújo",
    "Fernandes",
    "Carvalho",
    "Gomes",
]

# ============================================================================
# Utilities
# ============================================================================


def generate_cpf() -> str:
    """Gera CPF válido para testes."""
    # Simplificado - em produção usar biblioteca appropriada
    cpf = [random.randint(0, 9) for _ in range(9)]

    # Dígito 1
    sum_1 = sum((10 - i) * cpf[i] for i in range(9))
    digit_1 = 11 - (sum_1 % 11)
    if digit_1 >= 10:
        digit_1 = 0
    cpf.append(digit_1)

    # Dígito 2
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
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)

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


def generate_webhook_payload() -> Dict[str, Any]:
    """Gera payload de webhook para teste."""
    return {
        "event": "message.received",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "from": generate_phone(),
            "message": "Teste de mensagem recebida",
            "message_id": f"msg_{random.randint(100000, 999999)}",
        },
    }


# ============================================================================
# Task Sets
# ============================================================================


class PatientTasks(TaskSet):
    """Tarefas relacionadas a pacientes."""

    def on_start(self):
        """Executado quando o usuário inicia."""
        self.login()

    def login(self):
        """Faz login e armazena token."""
        response = self.client.post(
            "/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            },
        )

        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            raise RescheduleTask()

    @task(3)
    def list_patients(self):
        """Lista pacientes (operação comum)."""
        self.client.get(
            "/api/v2/patients",
            params={"page": 1, "size": 20},
            name="/api/v2/patients [LIST]",
        )

    @task(2)
    def get_patient_detail(self):
        """Obtém detalhes de um paciente específico."""
        # Assumindo que temos alguns pacientes no sistema
        patient_id = random.randint(1, 100)
        self.client.get(
            f"/api/v2/patients/{patient_id}",
            name="/api/v2/patients/:id [GET]",
        )

    @task(1)
    def create_patient(self):
        """Cria novo paciente."""
        patient_data = generate_patient_data()

        response = self.client.post(
            "/api/v2/patients",
            json=patient_data,
            name="/api/v2/patients [CREATE]",
        )

        if response.status_code == 201:
            patient = response.json()
            # Armazenar ID para uso posterior
            if not hasattr(self, "created_patients"):
                self.created_patients = []
            self.created_patients.append(patient.get("id"))


class MessageTasks(TaskSet):
    """Tarefas relacionadas a mensagens."""

    def on_start(self):
        """Executado quando o usuário inicia."""
        self.login()

    def login(self):
        """Faz login e armazena token."""
        response = self.client.post(
            "/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            },
        )

        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            raise RescheduleTask()

    @task(5)
    def list_messages(self):
        """Lista mensagens agendadas."""
        self.client.get(
            "/api/v2/messages",
            params={"page": 1, "size": 20},
            name="/api/v2/messages [LIST]",
        )

    @task(2)
    def schedule_message(self):
        """Agenda nova mensagem."""
        message_data = {
            "patient_id": random.randint(1, 100),
            "content": f"Mensagem de teste {random.randint(1000, 9999)}",
            "scheduled_for": datetime.now().isoformat(),
            "template_id": random.choice([1, 2, 3, 4]),
        }

        self.client.post(
            "/api/v2/messages/schedule",
            json=message_data,
            name="/api/v2/messages/schedule [POST]",
        )


class WebhookTasks(TaskSet):
    """Tarefas relacionadas a webhooks."""

    @task(10)
    def receive_webhook(self):
        """Simula recebimento de webhook."""
        payload = generate_webhook_payload()

        # HMAC signature (simplificado - em produção calcular corretamente)
        signature = "test_signature_" + str(random.randint(100000, 999999))

        self.client.post(
            "/webhooks/evolution",
            json=payload,
            headers={"X-Webhook-Signature": signature},
            name="/webhooks/evolution [POST]",
        )


class DashboardTasks(TaskSet):
    """Tarefas relacionadas ao dashboard."""

    def on_start(self):
        """Executado quando o usuário inicia."""
        self.login()

    def login(self):
        """Faz login e armazena token."""
        response = self.client.post(
            "/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            },
        )

        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            raise RescheduleTask()

    @task(10)
    def get_metrics(self):
        """Obtém métricas do dashboard."""
        self.client.get(
            "/api/v2/dashboard/metrics",
            name="/api/v2/dashboard/metrics [GET]",
        )

    @task(5)
    def get_patient_stats(self):
        """Obtém estatísticas de pacientes."""
        self.client.get(
            "/api/v2/analytics/patients",
            params={"period": "7d"},
            name="/api/v2/analytics/patients [GET]",
        )

    @task(3)
    def get_message_stats(self):
        """Obtém estatísticas de mensagens."""
        self.client.get(
            "/api/v2/analytics/messages",
            params={"period": "7d"},
            name="/api/v2/analytics/messages [GET]",
        )

    @task(2)
    def get_dlq_stats(self):
        """Obtém estatísticas da DLQ."""
        self.client.get(
            "/admin/dlq/stats",
            name="/admin/dlq/stats [GET]",
        )


# ============================================================================
# User Classes
# ============================================================================


class AdminUser(HttpUser):
    """Usuário administrador do sistema."""

    tasks = {
        PatientTasks: 3,
        MessageTasks: 2,
        DashboardTasks: 5,
    }

    wait_time = between(1, 3)  # Espera entre 1-3 segundos entre tarefas

    def on_start(self):
        """Executado quando o usuário inicia."""
        print(f"[AdminUser] Iniciando usuário em {self.host}")


class WebhookSimulator(HttpUser):
    """Simulador de webhooks externos."""

    tasks = [WebhookTasks]

    wait_time = between(0.1, 0.5)  # Webhooks chegam rapidamente

    def on_start(self):
        """Executado quando o usuário inicia."""
        print(f"[WebhookSimulator] Iniciando simulador em {self.host}")


class ReadOnlyUser(HttpUser):
    """Usuário que apenas consulta dados (médicos)."""

    tasks = [DashboardTasks]

    wait_time = between(2, 5)  # Consultas mais espaçadas

    def on_start(self):
        """Executado quando o usuário inicia."""
        print(f"[ReadOnlyUser] Iniciando usuário de leitura em {self.host}")


# ============================================================================
# Event Hooks
# ============================================================================


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Executado quando o teste inicia."""
    print("\n" + "=" * 80)
    print("🚀 INICIANDO TESTES DE CARGA - SISTEMA HORMONIA")
    print("=" * 80)
    print(f"Host: {environment.host}")
    print(
        f"Usuários: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}"
    )
    print("=" * 80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Executado quando o teste termina."""
    print("\n" + "=" * 80)
    print("✅ TESTES DE CARGA FINALIZADOS")
    print("=" * 80)

    # Estatísticas
    stats = environment.stats
    print(f"\nTotal de Requisições: {stats.total.num_requests}")
    print(f"Total de Falhas: {stats.total.num_failures}")
    print(f"Taxa de Erro: {stats.total.fail_ratio * 100:.2f}%")
    print(f"RPS Médio: {stats.total.total_rps:.2f}")
    print(f"Tempo de Resposta Médio: {stats.total.avg_response_time:.2f}ms")
    print(f"P95: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"P99: {stats.total.get_response_time_percentile(0.99):.2f}ms")

    # Validação de critérios
    print("\n" + "-" * 80)
    print("📊 VALIDAÇÃO DE CRITÉRIOS")
    print("-" * 80)

    p95 = stats.total.get_response_time_percentile(0.95)
    fail_ratio = stats.total.fail_ratio

    criteria_met = True

    # P95 < 500ms
    if p95 < 500:
        print("✅ P95 < 500ms: PASS ({:.2f}ms)".format(p95))
    else:
        print("❌ P95 < 500ms: FAIL ({:.2f}ms)".format(p95))
        criteria_met = False

    # Taxa de erro < 0.1%
    if fail_ratio < 0.001:
        print("✅ Taxa de Erro < 0.1%: PASS ({:.2f}%)".format(fail_ratio * 100))
    else:
        print("❌ Taxa de Erro < 0.1%: FAIL ({:.2f}%)".format(fail_ratio * 100))
        criteria_met = False

    print("-" * 80)

    if criteria_met:
        print("\n🎉 TODOS OS CRITÉRIOS FORAM ATENDIDOS!")
    else:
        print("\n⚠️  ALGUNS CRITÉRIOS NÃO FORAM ATENDIDOS")

    print("=" * 80 + "\n")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Executado para cada requisição."""
    # Log apenas de falhas ou requisições muito lentas
    if exception:
        print(f"❌ [{request_type}] {name} - FALHOU: {exception}")
    elif response_time > 1000:
        print(f"⚠️  [{request_type}] {name} - LENTO: {response_time:.0f}ms")


# ============================================================================
# Main (para execução direta)
# ============================================================================

if __name__ == "__main__":
    import os
    import sys

    # Para execução direta (útil para testes rápidos)
    print("Para executar os testes de carga, use:")
    print("\n  locust -f tests/load/locustfile.py --host=http://localhost:8000\n")
    print("Ou com parâmetros:")
    print(
        "\n  locust -f tests/load/locustfile.py --host=http://localhost:8000 -u 100 -r 10 -t 5m --headless\n"
    )
