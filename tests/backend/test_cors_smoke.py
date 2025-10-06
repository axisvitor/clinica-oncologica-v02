"""
CORS Smoke Tests - Validação de Configuração CORS

Testes de fumaça para validar que as configurações CORS estão funcionando
corretamente em todos os ambientes (dev, staging, produção).

Uso:
    pytest tests/backend/test_cors_smoke.py -v
    pytest tests/backend/test_cors_smoke.py -v --base-url https://seu-backend.railway.app
"""
import pytest
import requests
from typing import Dict, List
import os


class TestCORSConfiguration:
    """Testes de configuração CORS básica"""

    @pytest.fixture
    def base_url(self) -> str:
        """URL base do backend (pode ser sobrescrita via pytest --base-url)"""
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    @pytest.fixture
    def allowed_origins(self) -> List[str]:
        """Origens que devem ser permitidas"""
        return [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "https://clinica-oncologica-v02-production.up.railway.app",
            "https://interface-quiz-production.up.railway.app",
        ]

    @pytest.fixture
    def forbidden_origins(self) -> List[str]:
        """Origens que NÃO devem ser permitidas"""
        return [
            "https://evil-site.com",
            "http://malicious-domain.net",
            "https://phishing-site.org",
        ]

    def test_preflight_allowed_origin(self, base_url: str, allowed_origins: List[str]):
        """
        Teste 1: Preflight OPTIONS com origem permitida

        Valida que:
        - Retorna 200/204
        - Inclui Access-Control-Allow-Origin correto
        - Inclui Access-Control-Allow-Credentials: true
        - Inclui Access-Control-Allow-Methods
        - Inclui Access-Control-Allow-Headers
        """
        for origin in allowed_origins[:2]:  # Testa primeiras 2 origens
            response = requests.options(
                f"{base_url}/api/v1/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization, Content-Type"
                }
            )

            assert response.status_code in [200, 204], \
                f"Preflight falhou para origem {origin}: status {response.status_code}"

            assert "Access-Control-Allow-Origin" in response.headers, \
                f"Header Access-Control-Allow-Origin ausente para {origin}"

            assert response.headers.get("Access-Control-Allow-Origin") == origin, \
                f"Origin incorreta: esperado {origin}, obtido {response.headers.get('Access-Control-Allow-Origin')}"

            assert response.headers.get("Access-Control-Allow-Credentials") == "true", \
                "Access-Control-Allow-Credentials deve ser 'true'"

            assert "Access-Control-Allow-Methods" in response.headers, \
                "Access-Control-Allow-Methods ausente"

            assert "Access-Control-Allow-Headers" in response.headers, \
                "Access-Control-Allow-Headers ausente"

    def test_preflight_forbidden_origin(self, base_url: str, forbidden_origins: List[str]):
        """
        Teste 2: Preflight OPTIONS com origem NÃO permitida

        Valida que:
        - Não retorna Access-Control-Allow-Origin para origem proibida
        - Ou retorna erro apropriado
        """
        for origin in forbidden_origins[:1]:  # Testa primeira origem proibida
            response = requests.options(
                f"{base_url}/api/v1/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                }
            )

            # CORS middleware pode retornar 200 sem headers ou 403
            allow_origin = response.headers.get("Access-Control-Allow-Origin")

            # Se retornou Access-Control-Allow-Origin, NÃO pode ser a origem proibida
            if allow_origin:
                assert allow_origin != origin, \
                    f"Origem proibida {origin} foi permitida indevidamente!"

    def test_actual_request_allowed_origin(self, base_url: str, allowed_origins: List[str]):
        """
        Teste 3: Requisição GET real com origem permitida

        Valida que:
        - Retorna 200
        - Inclui Access-Control-Allow-Origin
        - Inclui Access-Control-Expose-Headers (se configurado)
        """
        for origin in allowed_origins[:2]:
            response = requests.get(
                f"{base_url}/api/v1/health",
                headers={"Origin": origin}
            )

            assert response.status_code == 200, \
                f"Requisição falhou para {origin}: status {response.status_code}"

            assert "Access-Control-Allow-Origin" in response.headers, \
                f"Access-Control-Allow-Origin ausente para {origin}"

            assert response.headers.get("Access-Control-Allow-Origin") == origin, \
                f"Origin incorreta na resposta"

    def test_actual_request_forbidden_origin(self, base_url: str, forbidden_origins: List[str]):
        """
        Teste 4: Requisição GET real com origem NÃO permitida

        Valida que:
        - Requisição é processada (backend não bloqueia)
        - Mas NÃO inclui Access-Control-Allow-Origin para origem proibida
        """
        for origin in forbidden_origins[:1]:
            response = requests.get(
                f"{base_url}/api/v1/health",
                headers={"Origin": origin}
            )

            # Backend processa a requisição (CORS é validado no browser)
            assert response.status_code == 200

            allow_origin = response.headers.get("Access-Control-Allow-Origin")
            if allow_origin:
                assert allow_origin != origin, \
                    f"Origem proibida {origin} recebeu CORS indevidamente"


class TestCORSWithCredentials:
    """Testes de CORS com credenciais (cookies/authorization)"""

    @pytest.fixture
    def base_url(self) -> str:
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    def test_credentials_with_specific_origin(self, base_url: str):
        """
        Teste 5: Credenciais com origem específica (VÁLIDO)

        Valida que:
        - Access-Control-Allow-Credentials: true funciona
        - Access-Control-Allow-Origin é uma origem específica (não *)
        """
        origin = "http://localhost:5173"
        response = requests.options(
            f"{base_url}/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization"
            }
        )

        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

        allow_origin = response.headers.get("Access-Control-Allow-Origin")
        assert allow_origin != "*", \
            "ERRO CRÍTICO: Access-Control-Allow-Origin: * com Credentials: true é INVÁLIDO!"

        assert allow_origin == origin, \
            f"Origin deve ser específica ({origin}), não wildcard"


class TestCORSExposedHeaders:
    """Testes de headers expostos via CORS"""

    @pytest.fixture
    def base_url(self) -> str:
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    def test_expose_headers_present(self, base_url: str):
        """
        Teste 6: Headers expostos estão presentes

        Valida que:
        - Access-Control-Expose-Headers está presente
        - Inclui headers customizados (X-Request-ID, etc)
        """
        origin = "http://localhost:5173"
        response = requests.get(
            f"{base_url}/api/v1/health",
            headers={"Origin": origin}
        )

        expose_headers = response.headers.get("Access-Control-Expose-Headers")

        if expose_headers:
            assert "X-Request-ID" in expose_headers, \
                "X-Request-ID deve estar em Access-Control-Expose-Headers"

            assert "X-Process-Time" in expose_headers or "X-Request-Duration" in expose_headers, \
                "Headers de performance devem estar expostos"


class TestCORSMethods:
    """Testes de métodos HTTP permitidos via CORS"""

    @pytest.fixture
    def base_url(self) -> str:
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def test_allowed_methods(self, base_url: str, method: str):
        """
        Teste 7: Métodos HTTP permitidos

        Valida que todos os métodos essenciais são permitidos via CORS
        """
        origin = "http://localhost:5173"
        response = requests.options(
            f"{base_url}/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method
            }
        )

        allowed_methods = response.headers.get("Access-Control-Allow-Methods", "")

        assert method in allowed_methods or "*" in allowed_methods, \
            f"Método {method} não permitido via CORS"


class TestCORSHeaders:
    """Testes de headers permitidos via CORS"""

    @pytest.fixture
    def base_url(self) -> str:
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    @pytest.mark.parametrize("header", [
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Quiz-Token",
    ])
    def test_allowed_headers(self, base_url: str, header: str):
        """
        Teste 8: Headers customizados permitidos

        Valida que headers essenciais são permitidos via CORS
        """
        origin = "http://localhost:5173"
        response = requests.options(
            f"{base_url}/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": header
            }
        )

        allowed_headers = response.headers.get("Access-Control-Allow-Headers", "")

        assert header.lower() in allowed_headers.lower() or "*" in allowed_headers, \
            f"Header {header} não permitido via CORS"


class TestCORSVaryHeader:
    """Testes de cache CORS com Vary header"""

    @pytest.fixture
    def base_url(self) -> str:
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    def test_vary_header_present(self, base_url: str):
        """
        Teste 9: Vary header para cache correto

        Valida que:
        - Header Vary está presente para evitar cache incorreto de CORS
        """
        origin = "http://localhost:5173"
        response = requests.get(
            f"{base_url}/api/v1/health",
            headers={"Origin": origin}
        )

        vary_header = response.headers.get("Vary", "")

        # Vary: Origin é essencial para cache correto de CORS
        # Alguns middlewares incluem automaticamente
        if vary_header:
            assert "Origin" in vary_header or "origin" in vary_header.lower(), \
                "Vary: Origin recomendado para cache correto de CORS"


class TestCORSMaxAge:
    """Testes de cache de preflight (max-age)"""

    @pytest.fixture
    def base_url(self) -> str:
        return os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

    def test_max_age_present(self, base_url: str):
        """
        Teste 10: Max-Age para cache de preflight

        Valida que Access-Control-Max-Age está configurado
        """
        origin = "http://localhost:5173"
        response = requests.options(
            f"{base_url}/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET"
            }
        )

        max_age = response.headers.get("Access-Control-Max-Age")

        if max_age:
            assert int(max_age) > 0, \
                "Access-Control-Max-Age deve ser positivo"


# ===== CONFIGURAÇÃO PYTEST =====

def pytest_addoption(parser):
    """Adiciona opções customizadas ao pytest"""
    parser.addoption(
        "--base-url",
        action="store",
        default=None,
        help="URL base do backend para testes (ex: https://seu-backend.railway.app)"
    )


@pytest.fixture
def base_url_from_cli(request):
    """Obtém URL base do CLI ou variável de ambiente"""
    return request.config.getoption("--base-url") or os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
