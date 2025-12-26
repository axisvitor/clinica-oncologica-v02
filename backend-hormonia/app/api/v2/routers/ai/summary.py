"""
AI Patient Summary API - Generate AI-powered patient summaries for doctor consultations.

Endpoints:
- POST /summary - Generate new patient summary
- GET /summary/{patient_id} - Get saved summaries for patient
- GET /summary/{summary_id}/pdf - Export summary as PDF

Features:
- AI-powered summary generation with Gemini 2.5 Flash
- Automatic caching (1 hour)
- PDF export capability
- Historical summary tracking
- Token usage monitoring

Author: AI Architect
Date: January 2025
"""

# Standard library imports
import logging
from uuid import UUID

# Third-party imports
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.dependencies import get_db, get_patient_service, validate_patient_access
from app.models.user import User
from app.schemas.v2.patient_summary import (
    GenerateSummaryRequest,
    PatientSummaryListResponse,
    PatientSummaryResponse,
)
from app.services.ai.patient_summary_service import get_patient_summary_service

from .dependencies import verify_physician_or_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=PatientSummaryResponse,
    summary="Generate Patient Summary",
    description="""
    Generate an AI-powered patient summary for doctor consultation.

    The summary includes:
    - Overview (2-3 paragraphs)
    - Quiz findings and symptom trends
    - Health concerns prioritized by severity
    - Engagement metrics
    - Treatment compliance score
    - Actionable recommendations (3-5 items)

    **Caching**: Summaries are cached for 1 hour. Use `force_refresh=true` to regenerate.
    **Cost**: ~$0.001-0.002 per summary (Gemini 2.5 Flash)
    """,
)
async def generate_patient_summary(
    request: GenerateSummaryRequest,
    current_user: User = Depends(verify_physician_or_admin),
    db: AsyncSession = Depends(get_db),
) -> PatientSummaryResponse:
    """
    Generate AI-powered patient summary.

    Requires physician or admin role.
    Validates patient access before generating summary (HIPAA compliance).
    """
    try:
        # FIX: Validate patient access before generating summary (HIPAA compliance)
        patient = await validate_patient_access(
            request.patient_id, current_user, get_patient_service(db)
        )

        service = get_patient_summary_service(db)

        response = await service.generate_summary(
            request=request,
            generated_by=current_user.id,
        )

        logger.info(
            f"Summary generated for patient {request.patient_id} "
            f"by user {current_user.id} - "
            f"{response.token_usage} tokens, {response.generation_time_ms}ms"
        )

        return response

    except ValueError as e:
        logger.warning(f"Summary generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found or insufficient data for summary",
        )
    except Exception as e:
        logger.error(f"Summary generation error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate patient summary",
        )


@router.get(
    "/patient/{patient_id}",
    response_model=PatientSummaryListResponse,
    summary="Get Saved Summaries",
    description="Get list of saved summaries for a patient.",
)
async def get_patient_summaries(
    patient_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(verify_physician_or_admin),
    db: AsyncSession = Depends(get_db),
) -> PatientSummaryListResponse:
    """
    Get saved summaries for a patient.

    Returns paginated list of previously generated summaries.
    """
    try:
        service = get_patient_summary_service(db)

        summaries, total = await service.get_saved_summaries(
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )

        return PatientSummaryListResponse(
            summaries=summaries,
            total=total,
            has_more=(offset + len(summaries)) < total,
        )

    except Exception as e:
        logger.error(f"Error fetching summaries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch patient summaries",
        )


@router.get(
    "/{summary_id}/pdf",
    response_class=Response,
    summary="Export Summary as PDF",
    description="Export a saved summary as PDF document.",
)
async def export_summary_pdf(
    summary_id: UUID,
    current_user: User = Depends(verify_physician_or_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Export summary as PDF.

    Returns PDF file bytes with appropriate headers for download.
    """
    try:
        service = get_patient_summary_service(db)

        pdf_bytes = await service.export_to_pdf(summary_id)

        # Create filename
        filename = f"patient_summary_{summary_id}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except ValueError as e:
        logger.warning(f"PDF export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Summary not found or cannot be exported",
        )
    except Exception as e:
        logger.error(f"PDF export error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export summary as PDF",
        )


@router.get(
    "/{summary_id}",
    response_model=PatientSummaryResponse,
    summary="Get Summary by ID",
    description="Get a specific summary by its ID.",
)
async def get_summary_by_id(
    summary_id: UUID,
    current_user: User = Depends(verify_physician_or_admin),
    db: AsyncSession = Depends(get_db),
) -> PatientSummaryResponse:
    """
    Get a specific summary by ID.
    """
    from sqlalchemy import select
    from app.models.patient_summary import PatientSummary
    from app.schemas.v2.patient_summary import SummaryContent

    try:
        result = await db.execute(
            select(PatientSummary).where(PatientSummary.id == summary_id)
        )
        summary = result.scalar_one_or_none()

        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Summary {summary_id} not found",
            )

        # Get patient name
        patient_name = ""
        if summary.patient:
            patient_name = summary.patient.name

        return PatientSummaryResponse(
            summary_id=summary.id,
            patient_id=summary.patient_id,
            patient_name=patient_name,
            start_date=summary.start_date,
            end_date=summary.end_date,
            content=SummaryContent(**summary.content)
            if summary.content
            else SummaryContent(overview=""),
            generated_at=summary.created_at,
            generated_by=summary.generated_by,
            token_usage=summary.token_usage,
            model_used=summary.model_used,
            generation_time_ms=summary.generation_time_ms,
            from_cache=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch summary",
        )
