#!/usr/bin/env python3
"""
Test that ValidationRule schema accepts dict values.
"""
import sys
import os
sys.path.append('.')

from app.schemas.quiz import ValidationRule, QuizQuestion, QuizTemplateResponse
from app.schemas.quiz import QuestionType
import json

def test_validation_rule_schema():
    """Test that ValidationRule schema accepts dict values."""
    
    try:
        print("Testing ValidationRule with dict value...")
        
        # Test the problematic validation rule
        rule_data = {
            "type": "range",
            "value": {"max": 5, "min": 1},
            "message": "Por favor, escolha um valor entre 1 e 5"
        }
        
        rule = ValidationRule(**rule_data)
        print(f"✅ ValidationRule created successfully!")
        print(f"   Type: {rule.type}")
        print(f"   Value: {rule.value} (type: {type(rule.value)})")
        print(f"   Message: {rule.message}")
        
        # Test with primitive values too
        print("\nTesting ValidationRule with primitive values...")
        
        rule_primitive = ValidationRule(
            type="min_length",
            value=5,
            message="Minimum 5 characters required"
        )
        print(f"✅ ValidationRule with int value works!")
        
        rule_string = ValidationRule(
            type="pattern",
            value="^[A-Za-z]+$",
            message="Only letters allowed"
        )
        print(f"✅ ValidationRule with string value works!")
        
        # Test a complete question with validation rules
        print("\nTesting complete QuizQuestion with validation rules...")
        
        question_data = {
            "id": "test_question",
            "type": "scale",
            "text": "Test question",
            "required": True,
            "validation_rules": [rule_data],
            "metadata": {}
        }
        
        question = QuizQuestion(**question_data)
        print(f"✅ QuizQuestion with dict validation rule works!")
        print(f"   Question ID: {question.id}")
        print(f"   Validation rules count: {len(question.validation_rules)}")
        
    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_validation_rule_schema()