"""Check Q1 options"""
import sys
sys.path.insert(0, '.')
from app.database import get_db
from app.models.quiz import QuizTemplate

db = next(get_db())
q = db.query(QuizTemplate).filter(QuizTemplate.name=='monthly_comprehensive').first()
print(f"Q1: {q.questions[0].get('text')}")
print(f"allow_other: {q.questions[0].get('allow_other')}")
print("Options:")
for o in q.questions[0].get('options', []):
    print(f"  - {o.get('label')}")
