from datetime import datetime

from sqlalchemy import select

from app.models.patient import Patient


class QuizMixin:
    async def _inject_quiz_link_if_needed(self, content: str, patient: Patient) -> str:
        """Replace quiz link placeholder with a generated monthly quiz link."""
        placeholder = "[LINK DO QUIZ]"
        if placeholder not in content:
            return content

        from app.core.monthly_quiz_config import get_monthly_quiz_config
        from app.domain.quizzes.manager import QuizSessionManager
        from app.domain.quizzes.quiz_trigger_policy import QuizTriggerPolicy
        from app.models.quiz import QuizSession, QuizTemplate
        from app.schemas.monthly_quiz import DeliveryMethod, MonthlyQuizLinkCreate
        from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo

        tmpl_result = await self.db.execute(
            select(QuizTemplate).filter(QuizTemplate.is_active.is_(True))
        )
        templates = tmpl_result.scalars().all()
        if not templates:
            raise ValueError("No active quiz template found for monthly quiz link")

        def _rank_template(template: QuizTemplate) -> int:
            name = (template.name or "").lower()
            category = (template.category or "").lower()
            if "mensal" in name or "monthly" in name:
                return 2
            if "mensal" in category or "monthly" in category:
                return 1
            return 0

        templates.sort(key=_rank_template, reverse=True)
        template = templates[0]

        config = get_monthly_quiz_config()
        enrollment_date = patient.enrollment_date or patient.created_at
        if isinstance(enrollment_date, datetime):
            if enrollment_date.tzinfo is None:
                enrollment_date = enrollment_date.replace(tzinfo=SAO_PAULO_TZ)
            enrollment_local_date = enrollment_date.astimezone(SAO_PAULO_TZ).date()
        else:
            enrollment_local_date = enrollment_date

        days_since_enrollment = (now_sao_paulo().date() - enrollment_local_date).days
        monthly_cycle, _ = QuizTriggerPolicy.calculate_monthly_cycle(days_since_enrollment)

        manager = QuizSessionManager(self.db)
        es_result = await self.db.execute(
            select(QuizSession)
            .filter(QuizSession.patient_id == patient.id)
            .filter(QuizSession.session_metadata["monthly_cycle"].astext == str(monthly_cycle))
            .order_by(QuizSession.started_at.desc())
        )
        existing_session = es_result.scalar_one_or_none()

        if existing_session:
            link_response = await manager.regenerate_link(existing_session.id)
        else:
            link_data = MonthlyQuizLinkCreate(
                patient_id=patient.id,
                quiz_template_id=template.id,
                delivery_method=DeliveryMethod.WHATSAPP,
                expiry_hours=config.MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS,
                send_immediately=False,
            )
            link_response = await manager.create_quiz_link(link_data)

        if link_response.session_id:
            sess_result = await self.db.execute(
                select(QuizSession).filter(QuizSession.id == link_response.session_id)
            )
            session = sess_result.scalar_one_or_none()
            if session:
                metadata = session.session_metadata or {}
                metadata["monthly_cycle"] = monthly_cycle
                session.session_metadata = metadata
                await self.db.commit()

        return content.replace(placeholder, link_response.link_url)


__all__ = ["QuizMixin"]
