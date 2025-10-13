"""
Medical reports API endpoints.
Handles report generation, preview, and download functionality.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.services.report import ReportService, ReportGenerationError
from app.schemas.report import (
    ReportGenerationRequest,
    ReportPreviewResponse,
    MedicalReportResponse,
    ReportListResponse
)
from app.schemas.common import ErrorResponse, PaginationParams
from app.utils.api_decorators import handle_service_exceptions


logger = logging.getLogger(__name__)

def _convert_pagination(pagination: PaginationParams) -> dict:
    """Convert PaginationParams to page/size format for compatibility."""
    skip = max(pagination.skip, 0)
    limit = pagination.limit if pagination.limit > 0 else 1
    page = (skip // limit) + 1
    return {
        "page": page,
        "size": limit,
        "skip": skip,
        "limit": limit
    }

router = APIRouter(tags=["reports"])


@router.post(
    "/generate",
    response_model=MedicalReportResponse,
    summary="Generate medical report",
    description="Generate a comprehensive medical report for a patient"
)
@handle_service_exceptions
async def generate_report(
    request: ReportGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a comprehensive medical report for a patient."""
    try:
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            from app.repositories.patient import PatientRepository
            patient_repo = PatientRepository(db)
            patient = patient_repo.get(request.patient_id)

            if not patient or patient.doctor_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Cannot generate report for this patient"
                )
        
        report_service = ReportService(db)
        report = await report_service.generate_report(request, current_user.id)
        
        logger.info(f"Report generated successfully: {report.id}")
        return report
        
    except ReportGenerationError as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in report generation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/preview",
    response_model=ReportPreviewResponse,
    summary="Preview report",
    description="Generate a report preview without saving to database"
)
@handle_service_exceptions
async def preview_report(
    request: ReportGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate a report preview without saving to database."""
    try:
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            from app.repositories.patient import PatientRepository
            patient_repo = PatientRepository(db)
            patient = patient_repo.get(request.patient_id)

            if not patient or patient.doctor_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Cannot preview report for this patient"
                )
        
        report_service = ReportService(db)
        preview = report_service.generate_report_preview(request)
        
        logger.info(f"Report preview generated for patient {request.patient_id}")
        return preview
        
    except ReportGenerationError as e:
        logger.error(f"Report preview failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in report preview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{report_id}",
    response_model=MedicalReportResponse,
    summary="Get report",
    description="Get a specific medical report by ID"
)
@handle_service_exceptions
async def get_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific medical report by ID."""
    try:
        report_service = ReportService(db)
        report = report_service.get_report(report_id)
        
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            from app.repositories.patient import PatientRepository
            patient_repo = PatientRepository(db)
            patient = patient_repo.get(report.patient_id)

            if not patient or patient.doctor_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Cannot access this report"
                )
        
        logger.info(f"Report retrieved: {report_id}")
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/{report_id}/download",
    response_model=None,
    summary="Download report PDF",
    description="Download a medical report as PDF"
)
@handle_service_exceptions
async def download_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """Download a medical report as PDF."""
    try:
        report_service = ReportService(db)
        
        # Check if report exists and user has permission
        report = report_service.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            from app.repositories.patient import PatientRepository
            patient_repo = PatientRepository(db)
            patient = patient_repo.get(report.patient_id)

            if not patient or patient.doctor_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Cannot download this report"
                )
        
        # Generate PDF
        pdf_content = report_service.generate_pdf_report(report_id)
        
        # Create filename
        filename = f"medical_report_{report.patient_id}_{report.period_start}_{report.period_end}.pdf"
        
        logger.info(f"Report PDF downloaded: {report_id}")
        
        return StreamingResponse(
            iter([pdf_content]),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except ReportGenerationError as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in download report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/patient/{patient_id}",
    response_model=ReportListResponse,
    summary="Get patient reports",
    description="Get all reports for a specific patient with pagination"
)
@handle_service_exceptions
async def get_patient_reports(
    patient_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all reports for a specific patient with pagination."""
    try:
        # Check permissions
        if current_user.role != UserRole.ADMIN:
            from app.repositories.patient import PatientRepository
            patient_repo = PatientRepository(db)
            patient = patient_repo.get(patient_id)

            if not patient or patient.doctor_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Cannot access this patient's reports"
                )
        
        report_service = ReportService(db)
        reports = report_service.get_reports_by_patient(
            patient_id,
            skip=_convert_pagination(pagination)["skip"],
            limit=_convert_pagination(pagination)["limit"]
        )
        
        # Get total count for pagination
        from app.repositories.report import MedicalReportRepository
        report_repo = MedicalReportRepository(db)
        total = report_repo.count_by_patient(patient_id)
        
        response = ReportListResponse(
            reports=reports,
            total=total,
            page=pagination.page,
            size=_convert_pagination(pagination)["limit"],
            pages=(total + _convert_pagination(pagination)["limit"] - 1) // _convert_pagination(pagination)["limit"]
        )
        
        logger.info(f"Patient reports retrieved: {patient_id}, count: {len(reports)}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get patient reports: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete(
    "/{report_id}",
    response_model=None,
    summary="Delete report",
    description="Delete a medical report"
)
@handle_service_exceptions
async def delete_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> dict[str, str]:
    """Delete a medical report."""
    try:
        # Only admins can delete reports
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Admin privileges required to delete reports"
            )
        
        report_service = ReportService(db)
        
        # Check if report exists
        report = report_service.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        
        # Delete report
        success = report_service.delete_report(report_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to delete report")
        
        logger.info(f"Report deleted: {report_id}")
        return {"message": "Report deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/",
    response_model=ReportListResponse,
    summary="List all reports",
    description="Get all reports with pagination and filtering"
)
@router.get(
    "",
    response_model=ReportListResponse,
    summary="List all reports",
    description="Get all reports with pagination and filtering"
)
@handle_service_exceptions
async def list_reports(
    pagination: PaginationParams = Depends(),
    patient_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all reports with pagination and filtering."""
    try:
        from app.repositories.report import MedicalReportRepository
        report_repo = MedicalReportRepository(db)
        
        # Filter by doctor if not admin
        doctor_id = None if current_user.role == UserRole.ADMIN else current_user.id
        
        # Get reports
        reports_data = report_repo.get_all_with_filters(
            skip=_convert_pagination(pagination)["skip"],
            limit=_convert_pagination(pagination)["limit"],
            patient_id=patient_id,
            doctor_id=doctor_id
        )
        
        reports = [MedicalReportResponse.model_validate(report) for report in reports_data]
        
        # Get total count
        total = report_repo.count_with_filters(
            patient_id=patient_id,
            doctor_id=doctor_id
        )
        
        response = ReportListResponse(
            reports=reports,
            total=total,
            page=_convert_pagination(pagination)["page"],
            size=_convert_pagination(pagination)["limit"],
            pages=(total + _convert_pagination(pagination)["limit"] - 1) // _convert_pagination(pagination)["limit"]
        )
        
        logger.info(f"Reports listed: count={len(reports)}, total={total}")
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error in list reports: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
