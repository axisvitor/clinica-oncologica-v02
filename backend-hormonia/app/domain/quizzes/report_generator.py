"""
Report Generator Module for Monthly Quiz Service.

Handles report creation, statistics generation, and summary formatting.
Responsibilities: Report generation, statistics calculation, metrics aggregation,
and data formatting for analytics.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_

from app.models.quiz import QuizSession
from app.schemas.monthly_quiz import MonthlyQuizStats
import logging
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates reports and statistics for quiz analytics."""

    def __init__(self, db: Session):
        self.db = db

    async def get_monthly_quiz_stats(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> MonthlyQuizStats:
        """
        Get statistics for monthly quizzes within a date range.

        Args:
            start_date: Start date for filtering (optional)
            end_date: End date for filtering (optional)

        Returns:
            MonthlyQuizStats with aggregated statistics
        """
        # Build query
        query = self.db.query(QuizSession).filter(
            QuizSession.session_metadata.isnot(None)
        )

        if start_date:
            query = query.filter(QuizSession.started_at >= start_date)
        if end_date:
            query = query.filter(QuizSession.started_at <= end_date)

        # FIX: Add eager loading to avoid N+1 queries when accessing related objects
        sessions = query.options(
            joinedload(QuizSession.quiz_template),
            selectinload(QuizSession.responses)
        ).all()

        # Calculate stats
        total_links = len(sessions)
        active_links = len(
            [
                s
                for s in sessions
                if s.status != "completed"
                and now_sao_paulo()
                <= datetime.fromisoformat(
                    (s.session_metadata or {}).get(
                        "expires_at", now_sao_paulo().isoformat()
                    )
                )
            ]
        )
        expired_links = len(
            [
                s
                for s in sessions
                if s.status != "completed"
                and now_sao_paulo()
                > datetime.fromisoformat(
                    (s.session_metadata or {}).get(
                        "expires_at", now_sao_paulo().isoformat()
                    )
                )
            ]
        )
        completed_quizzes = len([s for s in sessions if s.status == "completed"])

        completion_rate = (
            (completed_quizzes / total_links * 100) if total_links > 0 else 0
        )

        # Calculate average completion time
        completion_times = []
        for session in sessions:
            if session.status == "completed" and session.completed_at:
                duration = (
                    session.completed_at - session.started_at
                ).total_seconds() / 60
                completion_times.append(duration)

        avg_completion_time = (
            sum(completion_times) / len(completion_times) if completion_times else None
        )

        # Delivery methods distribution
        delivery_distribution: Dict[str, int] = {}
        for session in sessions:
            metadata = session.session_metadata or {}
            method = (
                metadata.get("delivery_method")
                or metadata.get("last_delivery_method")
                or "unknown"
            )
            delivery_distribution[method] = delivery_distribution.get(method, 0) + 1

        return MonthlyQuizStats(
            total_links_created=total_links,
            active_links=active_links,
            expired_links=expired_links,
            completed_quizzes=completed_quizzes,
            completion_rate=completion_rate,
            average_completion_time=avg_completion_time,
            delivery_methods_distribution=delivery_distribution,
        )

    async def get_quiz_stats(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get quiz statistics with backward-compatible field names.

        Args:
            user_id: Optional user ID for filtering

        Returns:
            Statistics dictionary with various metrics
        """
        query = self.db.query(QuizSession).filter(
            QuizSession.session_metadata.isnot(None)
        )

        if user_id:
            # Filter by creator if user_id provided (requires created_by column)
            pass  # Add created_by filter if column exists

        total = query.count()
        completed = query.filter(QuizSession.status == "completed").count()

        # Calculate expired links and average score
        current_time = now_sao_paulo()
        sessions = query.all()
        expired = 0
        active = 0
        total_score_sum = 0
        scored_sessions = 0

        for session in sessions:
            # Calculate average score from completed sessions
            if session.status == "completed" and session.score is not None:
                total_score_sum += session.score
                scored_sessions += 1

            # Skip completion check for expired/active calculation
            if session.status == "completed":
                continue

            metadata = session.session_metadata or {}
            expires_at_str = metadata.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if current_time > expires_at:
                        expired += 1
                    else:
                        active += 1
                except ValueError as e:
                    logger.debug(
                        f"Failed to parse expires_at from session metadata: {e}"
                    )

        # Calculate average score
        avg_score = (
            round((total_score_sum / scored_sessions), 2) if scored_sessions > 0 else 0
        )

        return {
            # New field names
            "total_sent": total,
            "total_completed": completed,
            "total_expired": expired,
            "total_active": active,
            "average_score": avg_score,
            # Old field names (backward compatibility)
            "total_links_created": total,
            "completed_quizzes": completed,
            "expired_links": expired,
            "active_links": active,
            # Calculated metrics
            "completion_rate": round((completed / total * 100), 2) if total > 0 else 0,
            "expiration_rate": round((expired / total * 100), 2) if total > 0 else 0,
        }

    def generate_session_report(self, session_id: UUID) -> Dict[str, Any]:
        """
        Generate detailed report for a single session.

        Args:
            session_id: Quiz session UUID

        Returns:
            Detailed session report
        """
        session = (
            self.db.query(QuizSession).filter(QuizSession.id == session_id).first()
        )

        if not session:
            return {"error": "Session not found"}

        metadata = session.session_metadata or {}

        # Calculate session duration
        duration = None
        if session.completed_at and session.started_at:
            duration = (session.completed_at - session.started_at).total_seconds()

        # Build report
        report = {
            "session_id": str(session.id),
            "patient_id": str(session.patient_id),
            "quiz_template_id": str(session.quiz_template_id),
            "status": session.status,
            "score": session.score,
            "started_at": session.started_at.isoformat()
            if session.started_at
            else None,
            "completed_at": session.completed_at.isoformat()
            if session.completed_at
            else None,
            "duration_seconds": duration,
            "current_question": session.current_question,
            "access_count": metadata.get("access_count", 0),
            "delivery_method": metadata.get("delivery_method")
            or metadata.get("last_delivery_method"),
            "expires_at": metadata.get("expires_at"),
            "link_status": metadata.get("link_status"),
            "delivery_attempts": metadata.get("delivery_attempts", []),
            "failure_count": metadata.get("failure_count", 0),
        }

        return report

    def generate_bulk_report(self, session_ids: List[UUID]) -> Dict[str, Any]:
        """
        Generate aggregate report for multiple sessions.

        Args:
            session_ids: List of session UUIDs

        Returns:
            Aggregate report with statistics
        """
        sessions = (
            self.db.query(QuizSession).filter(QuizSession.id.in_(session_ids)).all()
        )

        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.status == "completed"])
        in_progress_sessions = len([s for s in sessions if s.status == "in_progress"])

        # Calculate score statistics
        scores = [s.score for s in sessions if s.score is not None]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

        # Calculate completion times
        completion_times = []
        for session in sessions:
            if session.completed_at and session.started_at:
                duration = (session.completed_at - session.started_at).total_seconds()
                completion_times.append(duration)

        avg_completion_time = (
            round(sum(completion_times) / len(completion_times), 2)
            if completion_times
            else None
        )

        return {
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "in_progress_sessions": in_progress_sessions,
            "completion_rate": round((completed_sessions / total_sessions * 100), 2)
            if total_sessions > 0
            else 0,
            "average_score": avg_score,
            "average_completion_time_seconds": avg_completion_time,
            "sessions": [str(s.id) for s in sessions],
        }

    def generate_patient_report(
        self, patient_id: UUID, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Generate report for all sessions of a specific patient.

        Args:
            patient_id: Patient UUID
            limit: Maximum number of sessions to include

        Returns:
            Patient quiz history report
        """
        sessions = (
            self.db.query(QuizSession)
            .filter(
                and_(
                    QuizSession.patient_id == patient_id,
                    QuizSession.session_metadata.isnot(None),
                )
            )
            .order_by(QuizSession.started_at.desc())
            .limit(limit)
            .all()
        )

        total_sessions = len(sessions)
        completed_sessions = len([s for s in sessions if s.status == "completed"])

        # Calculate scores
        scores = [s.score for s in sessions if s.score is not None]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        best_score = max(scores) if scores else 0.0
        latest_score = scores[0] if scores else 0.0

        # Get latest session info
        latest_session = sessions[0] if sessions else None

        return {
            "patient_id": str(patient_id),
            "total_sessions": total_sessions,
            "completed_sessions": completed_sessions,
            "average_score": avg_score,
            "best_score": best_score,
            "latest_score": latest_score,
            "latest_session_id": str(latest_session.id) if latest_session else None,
            "latest_session_status": latest_session.status if latest_session else None,
            "latest_session_date": latest_session.started_at.isoformat()
            if latest_session and latest_session.started_at
            else None,
            "session_history": [
                {
                    "session_id": str(s.id),
                    "status": s.status,
                    "score": s.score,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "completed_at": s.completed_at.isoformat()
                    if s.completed_at
                    else None,
                }
                for s in sessions
            ],
        }

    def generate_delivery_report(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Generate report on delivery success rates.

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Delivery statistics report
        """
        query = self.db.query(QuizSession).filter(
            QuizSession.session_metadata.isnot(None)
        )

        if start_date:
            query = query.filter(QuizSession.started_at >= start_date)
        if end_date:
            query = query.filter(QuizSession.started_at <= end_date)

        sessions = query.all()

        delivery_stats = {
            "total_attempts": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "pending_deliveries": 0,
            "by_method": {},
        }

        for session in sessions:
            metadata = session.session_metadata or {}
            attempts = metadata.get("delivery_attempts", [])

            for attempt in attempts:
                delivery_stats["total_attempts"] += 1
                status = attempt.get("status", "unknown")
                method = (
                    attempt.get("delivery_method")
                    or attempt.get("method")
                    or metadata.get("delivery_method")
                    or metadata.get("last_delivery_method")
                    or "unknown"
                )

                if status == "sent":
                    delivery_stats["successful_deliveries"] += 1
                elif status == "failed":
                    delivery_stats["failed_deliveries"] += 1
                elif status == "pending":
                    delivery_stats["pending_deliveries"] += 1

                # Track by method
                if method not in delivery_stats["by_method"]:
                    delivery_stats["by_method"][method] = {
                        "total": 0,
                        "successful": 0,
                        "failed": 0,
                        "pending": 0,
                    }

                delivery_stats["by_method"][method]["total"] += 1
                if status == "sent":
                    delivery_stats["by_method"][method]["successful"] += 1
                elif status == "failed":
                    delivery_stats["by_method"][method]["failed"] += 1
                elif status == "pending":
                    delivery_stats["by_method"][method]["pending"] += 1

        # Calculate success rate
        delivery_stats["success_rate"] = round(
            (
                delivery_stats["successful_deliveries"]
                / delivery_stats["total_attempts"]
                * 100
            )
            if delivery_stats["total_attempts"] > 0
            else 0,
            2,
        )

        return delivery_stats

    def generate_time_based_report(
        self, start_date: datetime, end_date: datetime, granularity: str = "day"
    ) -> Dict[str, Any]:
        """
        Generate time-based report with specified granularity.

        Args:
            start_date: Report start date
            end_date: Report end date
            granularity: Time granularity (day, week, month)

        Returns:
            Time-based statistics report
        """
        sessions = (
            self.db.query(QuizSession)
            .filter(
                and_(
                    QuizSession.started_at >= start_date,
                    QuizSession.started_at <= end_date,
                    QuizSession.session_metadata.isnot(None),
                )
            )
            .all()
        )

        # Group sessions by time period
        time_groups: Dict[str, List[QuizSession]] = {}

        for session in sessions:
            if granularity == "day":
                period_key = session.started_at.strftime("%Y-%m-%d")
            elif granularity == "week":
                period_key = session.started_at.strftime("%Y-W%U")
            elif granularity == "month":
                period_key = session.started_at.strftime("%Y-%m")
            else:
                period_key = session.started_at.strftime("%Y-%m-%d")

            if period_key not in time_groups:
                time_groups[period_key] = []
            time_groups[period_key].append(session)

        # Calculate statistics for each period
        time_series = []
        for period, period_sessions in sorted(time_groups.items()):
            completed = len([s for s in period_sessions if s.status == "completed"])
            scores = [s.score for s in period_sessions if s.score is not None]

            time_series.append(
                {
                    "period": period,
                    "total_sessions": len(period_sessions),
                    "completed_sessions": completed,
                    "completion_rate": round(
                        (completed / len(period_sessions) * 100), 2
                    )
                    if period_sessions
                    else 0,
                    "average_score": round(sum(scores) / len(scores), 2)
                    if scores
                    else 0.0,
                }
            )

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "granularity": granularity,
            "total_periods": len(time_series),
            "time_series": time_series,
        }
