"""
API Endpoints para Dead Letter Queue (DLQ) Dashboard.

Este módulo fornece endpoints administrativos para gerenciar mensagens com falha.

Sprint 1 - DLQ Estruturada com Dashboard
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.user import User
from app.models.failed_message import DLQStatus
from app.services.dlq_service import DLQService, ErrorCategory
from app.schemas.dlq import (
    DLQMessageList,
    DLQMessageResponse,
    DLQRetryRequest,
    DLQDiscardRequest,
    DLQStats,
)
from app.core.monitoring_config import add_breadcrumb, capture_exception

router = APIRouter(prefix="/admin/dlq", tags=["Admin - DLQ"])


@router.get("", response_model=DLQMessageList)
async def list_dlq_messages(
    page: int = Query(1, ge=1, description="Página atual"),
    size: int = Query(20, ge=1, le=100, description="Tamanho da página"),
    status: Optional[DLQStatus] = Query(None, description="Filtrar por status"),
    category: Optional[str] = Query(
        None, description="Filtrar por categoria: transient, permanent, unknown"
    ),
    patient_id: Optional[UUID] = Query(None, description="Filtrar por paciente"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Lista mensagens da DLQ com paginação e filtros.

    **Requer**: Permissões de administrador

    **Filtros Disponíveis**:
    - status: pending, retry_scheduled, retrying, resolved, discarded, max_retries_exceeded
    - category: transient, permanent, unknown
    - patient_id: UUID do paciente

    **Retorna**: Lista paginada de mensagens na DLQ
    """
    add_breadcrumb(
        message="Listando mensagens da DLQ",
        category="dlq.list",
        data={
            "page": page,
            "size": size,
            "status": status.value if status else None,
            "category": category,
            "admin_user_id": str(current_user.id),
        },
    )

    try:
        dlq_service = DLQService(db)

        # Converter category string para enum se fornecido
        category_enum = None
        if category:
            try:
                category_enum = ErrorCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Categoria inválida: {category}. Use: transient, permanent, unknown",
                )

        result = dlq_service.list_messages(
            page=page,
            size=size,
            status=status,
            category=category_enum,
            patient_id=patient_id,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "list_dlq_messages",
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao listar mensagens da DLQ",
        )


@router.get("/stats", response_model=DLQStats)
async def get_dlq_stats(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Obtém estatísticas da DLQ.

    **Requer**: Permissões de administrador

    **Retorna**:
    - Total de mensagens
    - Contadores por status
    - Erros por categoria (últimas 24h)
    - Taxa de sucesso de retries
    """
    add_breadcrumb(
        message="Obtendo estatísticas da DLQ",
        category="dlq.stats",
        data={"admin_user_id": str(current_user.id)},
    )

    try:
        dlq_service = DLQService(db)
        stats = dlq_service.get_stats()

        return stats

    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "get_dlq_stats",
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter estatísticas da DLQ",
        )


@router.get("/{dlq_id}", response_model=DLQMessageResponse)
async def get_dlq_message(
    dlq_id: UUID,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Obtém detalhes de uma mensagem específica da DLQ.

    **Requer**: Permissões de administrador

    **Retorna**: Detalhes completos da mensagem incluindo:
    - Payload original
    - Histórico de retries
    - Metadata
    """
    add_breadcrumb(
        message="Obtendo detalhes de mensagem da DLQ",
        category="dlq.get",
        data={"dlq_id": str(dlq_id), "admin_user_id": str(current_user.id)},
    )

    try:
        from app.models.failed_message import FailedMessage

        message = db.query(FailedMessage).filter(FailedMessage.id == dlq_id).first()

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mensagem não encontrada na DLQ",
            )

        return DLQMessageResponse.from_orm(message)

    except HTTPException:
        raise
    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "get_dlq_message",
                "dlq_id": str(dlq_id),
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao obter mensagem da DLQ",
        )


@router.post("/{dlq_id}/retry")
async def retry_dlq_message(
    dlq_id: UUID,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Tenta reprocessar mensagem da DLQ manualmente.

    **Requer**: Permissões de administrador

    **Ação**: Tenta reenviar a mensagem com falha.
    Se bem-sucedido, marca como resolvida.
    Se falhar, mantém na DLQ com contador de retry incrementado.

    **Retorna**: Status da operação
    """
    add_breadcrumb(
        message="Retry manual de mensagem da DLQ",
        category="dlq.retry",
        data={"dlq_id": str(dlq_id), "admin_user_id": str(current_user.id)},
    )

    try:
        dlq_service = DLQService(db)

        success, error_message = dlq_service.retry_message(dlq_id, manual=True)

        if success:
            return {
                "success": True,
                "message": "Mensagem reprocessada com sucesso",
                "dlq_id": str(dlq_id),
            }
        else:
            return {
                "success": False,
                "message": "Falha ao reprocessar mensagem",
                "error": error_message,
                "dlq_id": str(dlq_id),
            }

    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "retry_dlq_message",
                "dlq_id": str(dlq_id),
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao tentar retry da mensagem",
        )


@router.post("/{dlq_id}/discard")
async def discard_dlq_message(
    dlq_id: UUID,
    request: DLQDiscardRequest,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Descarta mensagem da DLQ (não será mais processada).

    **Requer**: Permissões de administrador

    **Ação**: Marca mensagem como descartada permanentemente.
    Use quando a mensagem não é mais relevante ou não pode ser corrigida.

    **Parâmetros**:
    - reason: Razão do descarte (obrigatório)

    **Retorna**: Confirmação da operação
    """
    add_breadcrumb(
        message="Descartando mensagem da DLQ",
        category="dlq.discard",
        data={
            "dlq_id": str(dlq_id),
            "reason": request.reason,
            "admin_user_id": str(current_user.id),
        },
    )

    try:
        dlq_service = DLQService(db)

        success = dlq_service.discard_message(dlq_id, request.reason)

        if success:
            return {
                "success": True,
                "message": "Mensagem descartada com sucesso",
                "dlq_id": str(dlq_id),
                "reason": request.reason,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mensagem não encontrada na DLQ",
            )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "discard_dlq_message",
                "dlq_id": str(dlq_id),
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao descartar mensagem",
        )


@router.post("/process-scheduled")
async def process_scheduled_retries(
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Processa retries agendados manualmente (normalmente executado por worker).

    **Requer**: Permissões de administrador

    **Ação**: Processa todas as mensagens com retry agendado cuja hora já passou.

    **Retorna**: Número de mensagens processadas
    """
    add_breadcrumb(
        message="Processando retries agendados manualmente",
        category="dlq.process_scheduled",
        data={"admin_user_id": str(current_user.id)},
    )

    try:
        dlq_service = DLQService(db)

        processed = dlq_service.process_scheduled_retries()

        return {
            "success": True,
            "message": f"Processados {processed} retries agendados",
            "processed": processed,
        }

    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "process_scheduled_retries",
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao processar retries agendados",
        )


@router.delete("/bulk-discard")
async def bulk_discard(
    status_filter: DLQStatus = Query(
        ..., description="Status das mensagens a descartar"
    ),
    reason: str = Query(..., description="Razão do descarte em massa"),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """
    Descarta múltiplas mensagens por status (operação em massa).

    **Requer**: Permissões de administrador

    **⚠️ ATENÇÃO**: Operação irreversível!

    **Parâmetros**:
    - status_filter: Status das mensagens (ex: max_retries_exceeded)
    - reason: Razão do descarte em massa

    **Retorna**: Número de mensagens descartadas
    """
    add_breadcrumb(
        message="Descarte em massa de mensagens da DLQ",
        category="dlq.bulk_discard",
        level="warning",
        data={
            "status": status_filter.value,
            "reason": reason,
            "admin_user_id": str(current_user.id),
        },
    )

    try:
        from app.models.failed_message import FailedMessage

        # Buscar mensagens com o status
        messages = (
            db.query(FailedMessage).filter(FailedMessage.status == status_filter).all()
        )

        count = len(messages)

        if count == 0:
            return {
                "success": True,
                "message": f"Nenhuma mensagem encontrada com status {status_filter.value}",
                "discarded": 0,
            }

        # Descartar todas
        dlq_service = DLQService(db)
        discarded = 0

        for message in messages:
            if dlq_service.discard_message(message.id, reason):
                discarded += 1

        return {
            "success": True,
            "message": f"Descartadas {discarded} mensagens com status {status_filter.value}",
            "discarded": discarded,
            "reason": reason,
        }

    except Exception as e:
        capture_exception(
            e,
            context={
                "endpoint": "bulk_discard",
                "status": status_filter.value,
                "admin_user_id": str(current_user.id),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao descartar mensagens em massa",
        )
