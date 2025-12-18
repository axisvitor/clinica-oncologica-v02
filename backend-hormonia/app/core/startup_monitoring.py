"""
Script de Inicialização de Monitoramento - Sistema Hormonia

Este módulo inicializa monitoramento e observabilidade no startup da aplicação.

Sprint 0 - Configuração de Monitoramento
"""

import logging
from typing import Optional
from fastapi import FastAPI

from app.core.monitoring_config import (
    MonitoringConfig,
    init_sentry,
    get_monitoring_instance,
    set_tag,
)
from app.config import settings

logger = logging.getLogger(__name__)


def setup_monitoring(app: FastAPI, config: Optional[MonitoringConfig] = None) -> bool:
    """
    Configura monitoramento e observabilidade para a aplicação.

    Args:
        app: Instância do FastAPI
        config: Configuração de monitoramento (opcional)

    Returns:
        True se configurado com sucesso, False caso contrário
    """
    if config is None:
        config = get_monitoring_instance()

    # Log da configuração
    logger.info("=" * 70)
    logger.info("CONFIGURAÇÃO DE MONITORAMENTO")
    logger.info("=" * 70)
    logger.info(f"Ambiente: {config.environment}")
    logger.info(f"Release: {config.release}")
    logger.info(f"Sentry Habilitado: {config.is_enabled()}")
    logger.info(f"Sample Rate: {config.sample_rate * 100}%")
    logger.info(f"Traces Sample Rate: {config.traces_sample_rate * 100}%")
    logger.info(
        f"Profiling: {'Habilitado' if config.enable_profiling else 'Desabilitado'}"
    )
    logger.info("=" * 70)

    # Inicializar Sentry
    if config.is_enabled():
        success = init_sentry(config)

        if success:
            logger.info("✓ Sentry inicializado com sucesso")

            # Adicionar tags padrão
            set_tag("app", "hormonia-backend")
            set_tag("environment", config.environment)
            set_tag("version", config.release)

            # Adicionar informações ao app state
            app.state.monitoring_enabled = True
            app.state.monitoring_config = config

            return True
        else:
            logger.warning("⚠ Falha ao inicializar Sentry")
            app.state.monitoring_enabled = False
            return False
    else:
        logger.warning(
            "⚠ Monitoramento desabilitado - "
            "Configure SENTRY_DSN para habilitar error tracking"
        )
        app.state.monitoring_enabled = False
        return False


def setup_error_handlers(app: FastAPI):
    """
    Configura handlers de erro customizados com integração Sentry.

    Args:
        app: Instância do FastAPI
    """
    from fastapi import Request, status
    from fastapi.responses import JSONResponse
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app.core.monitoring_config import capture_exception, add_breadcrumb

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handle HTTP exceptions."""
        # Adicionar breadcrumb
        add_breadcrumb(
            message=f"HTTP {exc.status_code}: {exc.detail}",
            category="http",
            level="error" if exc.status_code >= 500 else "warning",
            data={
                "status_code": exc.status_code,
                "path": str(request.url.path),
                "method": request.method,
            },
        )

        # Capturar apenas erros 5xx no Sentry
        if exc.status_code >= 500 and hasattr(app.state, "monitoring_enabled"):
            if app.state.monitoring_enabled:
                capture_exception(
                    exc,
                    context={
                        "url": str(request.url),
                        "method": request.method,
                        "status_code": exc.status_code,
                    },
                )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Handle validation errors."""
        add_breadcrumb(
            message="Validation error",
            category="validation",
            level="warning",
            data={
                "path": str(request.url.path),
                "errors": str(exc.errors()),
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation error",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        # Sempre adicionar breadcrumb
        add_breadcrumb(
            message=f"Unexpected error: {type(exc).__name__}",
            category="error",
            level="error",
            data={
                "path": str(request.url.path),
                "method": request.method,
                "exception_type": type(exc).__name__,
            },
        )

        # Capturar no Sentry se habilitado
        if hasattr(app.state, "monitoring_enabled") and app.state.monitoring_enabled:
            event_id = capture_exception(
                exc,
                context={
                    "url": str(request.url),
                    "method": request.method,
                    "user_agent": request.headers.get("user-agent"),
                },
            )

            logger.error(
                f"Unexpected error captured in Sentry (event_id: {event_id}): {exc}"
            )
        else:
            logger.error(f"Unexpected error: {exc}", exc_info=True)

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            },
        )

    logger.info("✓ Error handlers configurados com integração Sentry")


def setup_request_tracking(app: FastAPI):
    """
    Configura tracking de requisições com breadcrumbs.

    Args:
        app: Instância do FastAPI
    """
    from fastapi import Request
    from app.core.monitoring_config import add_breadcrumb

    @app.middleware("http")
    async def track_requests(request: Request, call_next):
        """Track requests with breadcrumbs."""
        # Adicionar breadcrumb para cada requisição
        if hasattr(app.state, "monitoring_enabled") and app.state.monitoring_enabled:
            add_breadcrumb(
                message=f"{request.method} {request.url.path}",
                category="http.request",
                level="info",
                data={
                    "url": str(request.url),
                    "method": request.method,
                    "client": request.client.host if request.client else None,
                },
            )

        response = await call_next(request)

        return response

    logger.info("✓ Request tracking configurado")


def log_startup_info():
    """Log informações de startup."""
    import sys
    import platform

    logger.info("\n" + "=" * 70)
    logger.info("SISTEMA HORMONIA - BACKEND")
    logger.info("=" * 70)
    logger.info(f"Python: {sys.version.split()[0]}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Environment: {settings.APP_ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.APP_ENABLE_DEBUG}")
    logger.info("API Version: 2.0.0")
    logger.info("=" * 70)


def setup_health_check(app: FastAPI):
    """
    Configura endpoint de health check com status de monitoramento.

    Args:
        app: Instância do FastAPI
    """

    @app.get("/health/monitoring", tags=["Health"])
    async def monitoring_health():
        """
        Health check do sistema de monitoramento.

        Returns:
            Status do monitoramento
        """
        monitoring_enabled = getattr(app.state, "monitoring_enabled", False)
        monitoring_config = getattr(app.state, "monitoring_config", None)

        if not monitoring_enabled:
            return {
                "monitoring": "disabled",
                "sentry": "not_configured",
                "message": "Configure SENTRY_DSN para habilitar monitoramento",
            }

        config_dict = monitoring_config.get_config() if monitoring_config else {}

        return {
            "monitoring": "enabled",
            "sentry": "operational",
            "config": config_dict,
        }

    logger.info("✓ Health check de monitoramento configurado")


def initialize_monitoring(app: FastAPI) -> bool:
    """
    Inicializa completamente o sistema de monitoramento.

    Esta é a função principal que deve ser chamada no startup da aplicação.

    Args:
        app: Instância do FastAPI

    Returns:
        True se inicializado com sucesso
    """
    try:
        # Log de startup
        log_startup_info()

        # Setup de monitoramento
        monitoring_enabled = setup_monitoring(app)

        # Setup de error handlers
        setup_error_handlers(app)

        # Setup de request tracking
        if monitoring_enabled:
            setup_request_tracking(app)

        # Setup de health check
        setup_health_check(app)

        logger.info("\n" + "=" * 70)
        if monitoring_enabled:
            logger.info("✓ MONITORAMENTO INICIALIZADO COM SUCESSO")
        else:
            logger.info("⚠ MONITORAMENTO DESABILITADO")
        logger.info("=" * 70 + "\n")

        return monitoring_enabled

    except Exception as e:
        logger.error(f"Erro ao inicializar monitoramento: {e}", exc_info=True)
        return False


__all__ = [
    "setup_monitoring",
    "setup_error_handlers",
    "setup_request_tracking",
    "setup_health_check",
    "initialize_monitoring",
]
