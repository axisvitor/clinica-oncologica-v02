"""Compare quiz questions in DB vs markdown file"""
import sys
sys.path.insert(0, '.')
from app.database import get_db
from app.models.quiz import QuizTemplate

db = next(get_db())
quiz = db.query(QuizTemplate).filter(QuizTemplate.name=='monthly_comprehensive').first()
print(f"Quiz name: {quiz.name}")
print(f"Total questions: {len(quiz.questions)}")
print("\nFirst 10 questions in database:")
for i, q in enumerate(quiz.questions[:10]):
    text = q.get("text", "")[:80]
    print(f"Q{i+1}: {text}")
