#!/usr/bin/env python3
"""
Test that quiz templates can be loaded after fixing the ValidationRule schema.
"""
import os
import sys
sys.path.append('.')

from app.core.database import get_db_service_role
from app.repositories.quiz import QuizTemplateRepository
from app.schemas.quiz import QuizTemplateResponse

def test_quiz_templates_fix():
    """Test that quiz templates can be loaded after schema fix."""
    db = next(get_db_service_role())
    
    try:
        print("Testing QuizTemplateRepository...")
        repo = QuizTemplateRepository(db)
        
        # Try to get all templates
        print("Fetching quiz templates...")
        templates = repo.get_all()
        print(f"✅ Found {len(templates)} quiz templates")
        
        if templates:
            # Try to convert first template to response schema
            template = templates[0]
            print(f"Testing schema conversion for template: {template.name}")
            
            # This should work now with the fixed ValidationRule schema
            response = QuizTemplateResponse.from_orm(template)
            print(f"✅ Schema conversion successful!")
            print(f"   Template ID: {response.id}")
            print(f"   Template name: {response.name}")
            print(f"   Questions count: {len(response.questions)}")
            
            # Check validation rules in first question
            if response.questions and response.questions[0].validation_rules:
                rule = response.questions[0].validation_rules[0]
                print(f"   First validation rule:")
                print(f"     Type: {rule.type}")
                print(f"     Value: {rule.value} (type: {type(rule.value)})")
                print(f"     Message: {rule.message}")
        
    except Exception as e:
        print(f'❌ Test failed: {e}')
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == '__main__':
    test_quiz_templates_fix()