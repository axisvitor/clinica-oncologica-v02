"""
Quiz template service for loading and managing quiz templates from PostgreSQL database.
Replaces YAML-based QuizTemplateLoader with database-backed service.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

logger = logging.getLogger(__name__)


class QuizTemplateLoadError(Exception):
    """Quiz template loading error."""

    pass


class QuizTemplateService:
    """
    Service for managing quiz templates from database.
    All templates MUST be in the database - no YAML fallback.
    """

    def __init__(self, db: Session, cache_ttl_hours: int = 1):
        """
        Initialize quiz template service.

        Args:
            db: Database session (required for database access)
            cache_ttl_hours: Cache time-to-live in hours
        """
        if not db:
            raise ValueError("Database session is required for QuizTemplateService")

        self.db = db
        self._templates_cache: Dict[str, tuple[Dict[str, Any], datetime]] = {}
        self._cache_ttl = timedelta(hours=cache_ttl_hours)
        logger.info(
            f"QuizTemplateService initialized - DB-only mode, cache TTL: {cache_ttl_hours}h"
        )

    def load_quiz_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific quiz template from database.

        Args:
            template_name: Name of the quiz template

        Returns:
            Template data dictionary or None if not found

        Raises:
            QuizTemplateLoadError: If template cannot be loaded
        """
        # Check cache first
        cache_key = f"quiz:{template_name}"
        if cache_key in self._templates_cache:
            cached_template, cached_time = self._templates_cache[cache_key]
            if datetime.now(timezone.utc) - cached_time < self._cache_ttl:
                logger.debug(f"Returning cached quiz template: {template_name}")
                return cached_template
            else:
                # Cache expired, remove it
                del self._templates_cache[cache_key]
                logger.debug(f"Cache expired for quiz template: {template_name}")

        try:
            # Import here to avoid circular imports
            from app.models.quiz import QuizTemplate

            # Load from database
            template = (
                self.db.query(QuizTemplate)
                .filter(
                    and_(QuizTemplate.name == template_name, QuizTemplate.is_active)
                )
                .first()
            )

            if not template:
                logger.warning(f"Quiz template not found in database: {template_name}")
                return None

            # Convert to dict format
            template_data = {
                "id": str(template.id),
                "name": template.name,
                "version": template.version,
                "description": template.description,
                "questions": template.questions,  # JSONB field
                "category": template.category,
                "tags": template.tags,
                "passing_score": template.passing_score,
                "time_limit_minutes": template.time_limit_minutes,
                "randomize_questions": template.randomize_questions,
                "is_active": template.is_active,
                "created_at": template.created_at,
                "updated_at": template.updated_at,
            }

            # Validate template structure
            if self._validate_template(template_data):
                # Cache the template
                self._cache_template(cache_key, template_data)
                logger.info(
                    f"Loaded quiz template from DB: {template_name} v{template.version}"
                )
                return template_data
            else:
                logger.error(f"Invalid template structure: {template_name}")
                return None

        except Exception as e:
            logger.error(f"Failed to load quiz template {template_name}: {e}")
            raise QuizTemplateLoadError(
                f"Failed to load quiz template {template_name}: {str(e)}"
            )

    def load_all_quiz_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all active quiz templates from database.

        Returns:
            Dictionary of template_name -> template_data
        """
        try:
            from app.models.quiz import QuizTemplate

            templates = {}
            db_templates = (
                self.db.query(QuizTemplate).filter(QuizTemplate.is_active).all()
            )

            for template in db_templates:
                template_data = {
                    "id": str(template.id),
                    "name": template.name,
                    "version": template.version,
                    "description": template.description,
                    "questions": template.questions,
                    "category": template.category,
                    "tags": template.tags,
                    "passing_score": template.passing_score,
                    "time_limit_minutes": template.time_limit_minutes,
                    "randomize_questions": template.randomize_questions,
                    "is_active": template.is_active,
                }

                if self._validate_template(template_data):
                    templates[template.name] = template_data

            logger.info(f"Loaded {len(templates)} quiz templates from database")
            return templates

        except Exception as e:
            logger.error(f"Error loading all quiz templates: {e}")
            return {}

    def get_template_by_id(self, template_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get quiz template by ID.

        Args:
            template_id: Template UUID

        Returns:
            Template data or None if not found
        """
        try:
            from app.models.quiz import QuizTemplate

            template = (
                self.db.query(QuizTemplate)
                .filter(QuizTemplate.id == template_id)
                .first()
            )

            if not template:
                return None

            return {
                "id": str(template.id),
                "name": template.name,
                "version": template.version,
                "description": template.description,
                "questions": template.questions,
                "category": template.category,
                "tags": template.tags,
                "passing_score": template.passing_score,
                "time_limit_minutes": template.time_limit_minutes,
                "randomize_questions": template.randomize_questions,
                "is_active": template.is_active,
                "created_at": template.created_at,
                "updated_at": template.updated_at,
            }

        except Exception as e:
            logger.error(f"Error getting template by ID {template_id}: {e}")
            return None

    def _validate_template(self, template_data: Dict[str, Any]) -> bool:
        """
        Validate quiz template structure.

        Args:
            template_data: Template data to validate

        Returns:
            True if valid, False otherwise
        """
        # Required fields
        required_fields = ["name", "version", "questions"]

        for field in required_fields:
            if field not in template_data:
                logger.error(f"Missing required field in template: {field}")
                return False

        # Validate questions structure
        questions = template_data.get("questions", [])
        if not isinstance(questions, list) or len(questions) == 0:
            logger.error("Template must have at least one question")
            return False

        # Validate each question
        for idx, question in enumerate(questions):
            if not self._validate_question(question, idx):
                return False

        return True

    def _validate_question(self, question: Dict[str, Any], index: int) -> bool:
        """
        Validate individual question structure.

        Args:
            question: Question data
            index: Question index

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["id", "type", "text"]

        for field in required_fields:
            if field not in question:
                logger.error(f"Question {index} missing required field: {field}")
                return False

        # Validate question type
        valid_types = ["multiple_choice", "scale", "open_text", "yes_no"]
        if question["type"] not in valid_types:
            logger.error(f"Question {index} has invalid type: {question['type']}")
            return False

        # Validate options for multiple choice
        if question["type"] == "multiple_choice":
            if "options" not in question or not isinstance(question["options"], list):
                logger.error(f"Multiple choice question {index} must have options")
                return False

            for opt_idx, option in enumerate(question["options"]):
                if not isinstance(option, dict) or "text" not in option:
                    logger.error(f"Question {index} option {opt_idx} is invalid")
                    return False

        # Validate scale questions
        if question["type"] == "scale":
            if "validation_rules" in question:
                for rule in question["validation_rules"]:
                    if rule.get("type") == "range":
                        if (
                            "value" not in rule
                            or "min" not in rule["value"]
                            or "max" not in rule["value"]
                        ):
                            logger.error(
                                f"Scale question {index} has invalid range validation"
                            )
                            return False

        return True

    def get_question_by_id(
        self, template_name: str, question_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific question from a template.

        Args:
            template_name: Name of the template
            question_id: ID of the question

        Returns:
            Question data or None if not found
        """
        template = self.load_quiz_template(template_name)
        if not template:
            return None

        questions = template.get("questions", [])
        for question in questions:
            if question.get("id") == question_id:
                return question

        return None

    def _cache_template(self, cache_key: str, template_data: Dict[str, Any]) -> None:
        """Cache template with TTL management."""
        self._templates_cache[cache_key] = (template_data, datetime.now(timezone.utc))
        logger.debug(f"Cached quiz template: {cache_key}")

    def refresh_cache(self):
        """Clear the templates cache to force reload from database."""
        self._templates_cache.clear()
        logger.info("Quiz template cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        now = datetime.now(timezone.utc)
        expired_count = sum(
            1
            for _, cached_time in self._templates_cache.values()
            if now - cached_time >= self._cache_ttl
        )

        return {
            "cache_size": len(self._templates_cache),
            "expired_entries": expired_count,
            "cache_ttl_hours": self._cache_ttl.total_seconds() / 3600,
            "database_enabled": True,
        }


# Global instance (optional, for compatibility)
_quiz_template_service: Optional[QuizTemplateService] = None


def get_quiz_template_service(db: Session) -> QuizTemplateService:
    """
    Get or create quiz template service instance.

    Args:
        db: Database session

    Returns:
        QuizTemplateService instance
    """
    # Always create new instance with provided db session
    # (global instance pattern doesn't work well with database sessions)
    return QuizTemplateService(db=db)
