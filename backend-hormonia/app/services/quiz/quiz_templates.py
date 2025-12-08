"""
Quiz Templates - Template Management and Validation (QW-023).

Consolidates:
    - quiz_template_loader.py
    - quiz_template_service.py (partial)
    - quiz_question_humanizer_integration.py
    - quiz_link_resilience.py
    - quiz_token_rotation_patch.py

Total: 5 files → 1 file
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import json
from pathlib import Path

from app.models.quiz import QuizTemplate
from app.repositories.quiz import QuizTemplateRepository
from app.schemas.quiz import (
    QuizQuestion,
    QuestionType,
    QuizValidationResult,
    QuizTemplateResponse
)
from app.exceptions import NotFoundError, ValidationError


class TemplateLoader:
    """Service for loading quiz templates from various sources."""
    
    def __init__(self, db: Any):
        self.db = db
        self.repository = QuizTemplateRepository(db)
    
    def load_from_file(self, file_path: str) -> QuizTemplate:
        """Load template from JSON file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Template file not found: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return self._create_template_from_dict(data)
    
    def load_from_dict(self, data: Dict[str, Any]) -> QuizTemplate:
        """Load template from dictionary."""
        return self._create_template_from_dict(data)
    
    def _create_template_from_dict(self, data: Dict[str, Any]) -> QuizTemplate:
        """Create template object from dictionary."""
        return QuizTemplate(
            name=data['name'],
            version=data.get('version', '1.0'),
            questions=data['questions'],
            is_active=data.get('is_active', True)
        )


class TemplateValidator:
    """Service for validating quiz templates."""
    
    @staticmethod
    def validate(questions: List[QuizQuestion]) -> QuizValidationResult:
        """Validate quiz template questions."""
        errors = []
        warnings = []
        
        if not questions:
            errors.append("Template must have at least one question")
            return QuizValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings
            )
        
        question_ids = set()
        
        for i, question in enumerate(questions):
            # Check duplicate IDs
            if question.id in question_ids:
                errors.append(f"Duplicate question ID: {question.id}")
            question_ids.add(question.id)
            
            # Validate question text
            if not question.text.strip():
                errors.append(f"Question {i+1} has empty text")
            
            # Validate question type requirements
            if question.type == QuestionType.MULTIPLE_CHOICE:
                if not question.options or len(question.options) == 0:
                    errors.append(f"Question '{question.id}' must have options")
                elif len(question.options) < 2:
                    warnings.append(f"Question '{question.id}' has only one option")
            
            # Validate scale range
            elif question.type == QuestionType.SCALE:
                if not hasattr(question, 'min_value') or not hasattr(question, 'max_value'):
                    errors.append(f"Scale question '{question.id}' must have min/max values")
        
        return QuizValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    @staticmethod
    def validate_template_compatibility(old_version: QuizTemplate, new_version: QuizTemplate) -> bool:
        """Validate if new version is compatible with old version."""
        old_question_ids = {q['id'] for q in old_version.questions}
        new_question_ids = {q['id'] for q in new_version.questions}
        
        # Check if all old questions are in new version
        return old_question_ids.issubset(new_question_ids)


class TemplateVersionManager:
    """Service for managing template versions."""
    
    def __init__(self, db: Any):
        self.db = db
        self.repository = QuizTemplateRepository(db)
    
    def create_version(self, template_id: UUID, new_version: str) -> QuizTemplateResponse:
        """Create new version of template."""
        original = self.repository.get(template_id)
        if not original:
            raise NotFoundError(f"Template {template_id} not found")
        
        # Check if version already exists
        existing = self.repository.get_by_name_and_version(original.name, new_version)
        if existing:
            raise ValidationError(f"Version {new_version} already exists")
        
        # Create new version
        new_template = QuizTemplate(
            name=original.name,
            version=new_version,
            questions=original.questions,
            is_active=True
        )
        
        created = self.repository.create(new_template)
        self.db.commit()
        
        return QuizTemplateResponse.from_orm(created)
    
    def get_versions(self, template_name: str) -> List[QuizTemplateResponse]:
        """Get all versions of a template."""
        templates = self.repository.get_all_versions(template_name)
        return [QuizTemplateResponse.from_orm(t) for t in templates]
    
    def get_latest_version(self, template_name: str) -> Optional[QuizTemplateResponse]:
        """Get latest version of template."""
        templates = self.repository.get_all_versions(template_name)
        if not templates:
            return None
        
        # Sort by version (assuming semantic versioning)
        sorted_templates = sorted(
            templates,
            key=lambda t: tuple(map(int, t.version.split('.'))),
            reverse=True
        )
        
        return QuizTemplateResponse.from_orm(sorted_templates[0])


class TemplateCache:
    """Simple in-memory cache for templates."""
    
    def __init__(self):
        self._cache: Dict[UUID, QuizTemplate] = {}
        self._cache_times: Dict[UUID, datetime] = {}
        self._ttl_seconds = 3600  # 1 hour
    
    def get(self, template_id: UUID) -> Optional[QuizTemplate]:
        """Get template from cache."""
        if template_id not in self._cache:
            return None
        
        # Check if expired
        cached_time = self._cache_times.get(template_id)
        if cached_time and (datetime.utcnow() - cached_time).total_seconds() > self._ttl_seconds:
            self.invalidate(template_id)
            return None
        
        return self._cache.get(template_id)
    
    def set(self, template_id: UUID, template: QuizTemplate) -> None:
        """Set template in cache."""
        self._cache[template_id] = template
        self._cache_times[template_id] = datetime.utcnow()
    
    def invalidate(self, template_id: UUID) -> None:
        """Invalidate cache entry."""
        self._cache.pop(template_id, None)
        self._cache_times.pop(template_id, None)
    
    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        self._cache_times.clear()


def get_template_loader(db: Any) -> TemplateLoader:
    """Get TemplateLoader instance."""
    return TemplateLoader(db)


def get_template_validator() -> TemplateValidator:
    """Get TemplateValidator instance."""
    return TemplateValidator()


def get_version_manager(db: Any) -> TemplateVersionManager:
    """Get TemplateVersionManager instance."""
    return TemplateVersionManager(db)
