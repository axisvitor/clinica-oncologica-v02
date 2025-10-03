"""
Quiz template loader for loading quiz templates from YAML files.
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class QuizTemplateLoader:
    """
    Loads quiz templates from YAML files.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize quiz template loader.
        
        Args:
            templates_dir: Directory containing quiz templates
        """
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            # Default to app/templates/quiz directory
            self.templates_dir = Path(__file__).parent.parent / "templates" / "quiz"
        
        self._templates_cache: Dict[str, Dict[str, Any]] = {}
        logger.info(f"QuizTemplateLoader initialized with directory: {self.templates_dir}")
    
    def load_quiz_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a specific quiz template from YAML file.
        
        Args:
            template_name: Name of the template (without .yaml extension)
            
        Returns:
            Template data dictionary or None if not found
        """
        # Check cache first
        if template_name in self._templates_cache:
            logger.debug(f"Returning cached template: {template_name}")
            return self._templates_cache[template_name]
        
        # Try to load from file
        template_path = self.templates_dir / f"{template_name}.yaml"
        
        if not template_path.exists():
            logger.warning(f"Template file not found: {template_path}")
            return None
        
        try:
            with open(template_path, 'r', encoding='utf-8') as file:
                template_data = yaml.safe_load(file)
            
            # Validate template structure
            if self._validate_template(template_data):
                # Cache the template
                self._templates_cache[template_name] = template_data
                logger.info(f"Loaded quiz template: {template_name}")
                return template_data
            else:
                logger.error(f"Invalid template structure: {template_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {e}")
            return None
    
    def load_all_quiz_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all quiz templates from the templates directory.
        
        Returns:
            Dictionary of template_name -> template_data
        """
        templates = {}
        
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory does not exist: {self.templates_dir}")
            return templates
        
        # Load all YAML files in the directory
        for template_file in self.templates_dir.glob("*.yaml"):
            template_name = template_file.stem  # filename without extension
            
            template_data = self.load_quiz_template(template_name)
            if template_data:
                templates[template_name] = template_data
        
        logger.info(f"Loaded {len(templates)} quiz templates")
        return templates
    
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
                        if "value" not in rule or "min" not in rule["value"] or "max" not in rule["value"]:
                            logger.error(f"Scale question {index} has invalid range validation")
                            return False
        
        return True
    
    def get_question_by_id(self, template_name: str, question_id: str) -> Optional[Dict[str, Any]]:
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
    
    def refresh_cache(self):
        """Clear the templates cache to force reload from files."""
        self._templates_cache.clear()
        logger.info("Quiz template cache cleared")


# Global instance
_quiz_template_loader: Optional[QuizTemplateLoader] = None


def get_quiz_template_loader() -> QuizTemplateLoader:
    """
    Get or create global quiz template loader instance.
    
    Returns:
        QuizTemplateLoader instance
    """
    global _quiz_template_loader
    
    if _quiz_template_loader is None:
        _quiz_template_loader = QuizTemplateLoader()
    
    return _quiz_template_loader