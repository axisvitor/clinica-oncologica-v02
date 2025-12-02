"""Bulk operations for creating multiple quiz links."""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.schemas.monthly_quiz import BulkQuizLinkCreate, BulkQuizLinkResponse, MonthlyQuizLinkCreate

import logging

logger = logging.getLogger(__name__)


class BulkManager:
    """Handles bulk creation of quiz links for multiple patients."""

    def __init__(self, db: Session):
        self.db = db

    async def create_bulk_links(
        self,
        bulk_data: BulkQuizLinkCreate,
        create_link_callback,
        actor_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> BulkQuizLinkResponse:
        """Create quiz links for multiple patients.

        Args:
            bulk_data: Bulk creation request data
            create_link_callback: Async callback to create individual link
            actor_id: User creating the links
            ip_address: IP address of request
            user_agent: User agent of request

        Returns:
            BulkQuizLinkResponse with results and failures
        """
        links = []
        failures = []

        for patient_id in bulk_data.patient_ids:
            try:
                link_data = MonthlyQuizLinkCreate(
                    patient_id=patient_id,
                    quiz_template_id=bulk_data.quiz_template_id,
                    delivery_method=bulk_data.delivery_method,
                    expiry_hours=bulk_data.expiry_hours,
                    custom_message=bulk_data.custom_message,
                    send_immediately=bulk_data.send_immediately
                )

                link = await create_link_callback(
                    link_data,
                    actor_id=actor_id,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                links.append(link)

            except Exception as e:
                logger.error(
                    f"Failed to create quiz link for patient {patient_id}",
                    extra={"patient_id": str(patient_id), "error": str(e)}
                )
                failures.append({
                    "patient_id": str(patient_id),
                    "error": str(e)
                })

        return BulkQuizLinkResponse(
            total_requested=len(bulk_data.patient_ids),
            total_created=len(links),
            total_failed=len(failures),
            links=links,
            failures=failures
        )
