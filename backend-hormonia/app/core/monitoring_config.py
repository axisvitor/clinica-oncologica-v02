"""
Configuração de Monitoramento - Sistema Hormonia

Este módulo configura monitoramento e observabilidade com Sentry e métricas customizadas.

Implementação do Sprint 0 - Configuração de Monitoramento
"""

import os
import logging
from typing import Optional, Dict, Any
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class MonitoringConfig:
    """
    Configuração de monitoramento e observabilidade.

    Features:
    - Sentry integration para error tracking
    - Métricas customizadas
    - Performance monitoring
    - Distributed tracing
    """

    def __init__(
        self,
        sentry_dsn: Optional[str] = None,
        environment: str = "development",
        release: Optional[str] = None,
        sample_rate: float = 1.0,
        traces_sample_rate: float = 0.1,
        enable_profiling: bool = False,
    ):
        """
        Inicializa configuração de monitoramento.

        Args:
            sentry_dsn: DSN do Sentry
            environment: Ambiente (development, staging, production)
            release: Versão da aplicação
            sample_rate: Taxa de amostragem de erros (0.0-1.0)
            traces_sample_rate: Taxa de amostragem de traces (0.0-1.0)
            enable_profiling: Habilitar profiling
        """
        self.sentry_dsn = sentry_dsn or os.getenv("SENTRY_DSN")
        self.environment = environment or os.getenv("ENVIRONMENT", "development")
        self.release = release or os.getenv("APP_VERSION", "2.0.0")
        self.sample_rate = sample_rate
        self.traces_sample_rate = traces_sample_rate
        self.enable_profiling = enable_profiling
        self.is_production = self.environment.lower() == "production"

    def is_enabled(self) -> bool:
        """Check if monitoring is enabled."""
        return self.sentry_dsn is not None and len(self.sentry_dsn) > 0

    def get_config(self) -> Dict[str, Any]:
        """Get monitoring configuration."""
        return {
            "enabled": self.is_enabled(),
            "environment": self.environment,
            "release": self.release,
            "sample_rate": self.sample_rate,
            "traces_sample_rate": self.traces_sample_rate,
            "enable_profiling": self.enable_profiling,
        }


def init_sentry(config: Optional[MonitoringConfig] = None) -> bool:
    """
    Inicializa Sentry para error tracking.

    Args:
        config: Configuração de monitoramento

    Returns:
        True se inicializado com sucesso, False caso contrário
    """
    if config is None:
        config = MonitoringConfig()

    if not config.is_enabled():
        logger.warning("Sentry não configurado - SENTRY_DSN não encontrado")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        # Configurar integração de logging
        logging_integration = LoggingIntegration(
            level=logging.INFO,  # Captura logs INFO e acima
            event_level=logging.ERROR,  # Envia eventos apenas para ERROR e acima
        )

        sentry_sdk.init(
            dsn=config.sentry_dsn,
            environment=config.environment,
            release=config.release,
            # Integrações
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                logging_integration,
            ],
            # Performance monitoring
            traces_sample_rate=config.traces_sample_rate,
            # Error sampling
            sample_rate=config.sample_rate,
            # Profiling
            profiles_sample_rate=0.1 if config.enable_profiling else 0.0,
            # Additional options
            send_default_pii=False,  # Não enviar PII por padrão (LGPD/GDPR)
            attach_stacktrace=True,
            max_breadcrumbs=50,
            # Before send hook para filtrar dados sensíveis
            before_send=_before_send_filter,
        )

        logger.info(
            f"✓ Sentry inicializado com sucesso "
            f"(env: {config.environment}, release: {config.release})"
        )
        return True

    except ImportError:
        logger.warning("Sentry SDK não instalado - pip install sentry-sdk")
        return False
    except Exception as e:
        logger.error(f"Erro ao inicializar Sentry: {e}")
        return False


def _before_send_filter(
    event: Dict[str, Any], hint: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Filtro de eventos antes de enviar ao Sentry.

    Remove informações sensíveis como senhas, tokens, etc.
    """
    _ = hint
    # Lista de chaves sensíveis para remover
    sensitive_keys = [
        "password",
        "senha",
        "token",
        "api_key",
        "apikey",
        "secret",
        "authorization",
        "cookie",
        "session",
        "csrf",
        "credit_card",
        "cpf",
        "ssn",
        "taxpayer_id",
    ]

    # Filtrar request data
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict):
            for key in list(data.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    data[key] = "[FILTERED]"

    # Filtrar headers
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        if isinstance(headers, dict):
            for key in list(headers.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    headers[key] = "[FILTERED]"

    # Filtrar contexto extra
    if "extra" in event:
        extra = event["extra"]
        if isinstance(extra, dict):
            for key in list(extra.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    extra[key] = "[FILTERED]"

    return event


def capture_exception(
    error: Exception, context: Optional[Dict[str, Any]] = None, level: str = "error"
) -> Optional[str]:
    """
    Captura exceção e envia para Sentry.

    Args:
        error: Exceção a ser capturada
        context: Contexto adicional
        level: Nível de severidade (error, warning, info)

    Returns:
        Event ID do Sentry ou None
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            # Adicionar contexto
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)

            # Adicionar timestamp
            scope.set_extra("captured_at", now_sao_paulo().isoformat())

            # Definir nível
            scope.level = level

            # Capturar exceção
            event_id = sentry_sdk.capture_exception(error)

            logger.debug(f"Exception capturada no Sentry: {event_id}")
            return event_id

    except Exception as e:
        logger.error(f"Erro ao capturar exception no Sentry: {e}")
        return None


def capture_message(
    message: str, level: str = "info", context: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Captura mensagem e envia para Sentry.

    Args:
        message: Mensagem a ser enviada
        level: Nível de severidade
        context: Contexto adicional

    Returns:
        Event ID do Sentry ou None
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)

            scope.level = level
            event_id = sentry_sdk.capture_message(message)

            return event_id

    except Exception as e:
        logger.error(f"Erro ao capturar message no Sentry: {e}")
        return None


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None,
):
    """
    Adiciona breadcrumb para rastreamento de eventos.

    Args:
        message: Mensagem do breadcrumb
        category: Categoria (ex: 'http', 'db', 'auth')
        level: Nível de severidade
        data: Dados adicionais
    """
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {},
        )
    except Exception as e:
        logger.debug(f"Erro ao adicionar breadcrumb: {e}")


def set_user_context(
    user_id: str,
    email: Optional[str] = None,
    username: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Define contexto do usuário para eventos.

    Args:
        user_id: ID do usuário
        email: Email do usuário (opcional)
        username: Nome do usuário (opcional)
        extra: Dados extras do usuário
    """
    try:
        import sentry_sdk

        user_data = {
            "id": user_id,
        }

        if email:
            user_data["email"] = email
        if username:
            user_data["username"] = username
        if extra:
            user_data.update(extra)

        sentry_sdk.set_user(user_data)

    except Exception as e:
        logger.debug(f"Erro ao definir user context: {e}")


def set_tag(key: str, value: str):
    """
    Define tag para eventos do Sentry.

    Args:
        key: Chave da tag
        value: Valor da tag
    """
    try:
        import sentry_sdk

        sentry_sdk.set_tag(key, value)
    except Exception as e:
        logger.debug(f"Erro ao definir tag: {e}")


def get_monitoring_config() -> MonitoringConfig:
    """
    Obtém configuração de monitoramento do ambiente.

    Returns:
        Configuração de monitoramento
    """
    environment = os.getenv("ENVIRONMENT", "development")

    # Ajustar sample rates baseado no ambiente
    if environment == "production":
        sample_rate = 1.0  # Captura 100% dos erros em produção
        traces_sample_rate = 0.1  # Captura 10% das transações
    elif environment == "staging":
        sample_rate = 1.0
        traces_sample_rate = 0.5  # Captura 50% em staging
    else:
        sample_rate = 1.0
        traces_sample_rate = 1.0  # Captura 100% em desenvolvimento

    return MonitoringConfig(
        sentry_dsn=os.getenv("SENTRY_DSN"),
        environment=environment,
        release=os.getenv("APP_VERSION", "2.0.0"),
        sample_rate=sample_rate,
        traces_sample_rate=traces_sample_rate,
        enable_profiling=environment in ["staging", "production"],
    )


# Singleton instance
_monitoring_config: Optional[MonitoringConfig] = None


def get_monitoring_instance() -> MonitoringConfig:
    """Get singleton monitoring configuration instance."""
    global _monitoring_config

    if _monitoring_config is None:
        _monitoring_config = get_monitoring_config()

    return _monitoring_config


__all__ = [
    "MonitoringConfig",
    "init_sentry",
    "capture_exception",
    "capture_message",
    "add_breadcrumb",
    "set_user_context",
    "set_tag",
    "get_monitoring_config",
    "get_monitoring_instance",
]
