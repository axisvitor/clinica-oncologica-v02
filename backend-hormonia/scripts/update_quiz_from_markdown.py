"""
Script to update quiz template from markdown file
Parses the Quizz de Bem-Estar Mensal.md and updates the database
"""
import sys
sys.path.insert(0, '.')
import re
from app.database import get_db
from app.models.quiz import QuizTemplate

def parse_markdown_quiz(filepath):
    """Parse the markdown quiz file and extract questions"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    questions = []
    current_category = ""
    
    # Split content by question headers (### **X.X. ...)
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check for topic header
        if '## **✅' in line or '## **✅ CHECKUP' in line:
            # Extract category name
            match = re.search(r'TÓPICO\s*(\d+)[^—–-]*[—–-]\s*(.+?)\*\*', line)
            if match:
                current_category = f"TÓPICO {match.group(1)} — {match.group(2).strip()}"
            elif 'CHECKUP MENSAL' in line:
                match2 = re.search(r'TÓPICO\s*(\d+)[^—–-]*[:\s—–-]+\s*(.+?)\*\*', line)
                if match2:
                    current_category = f"TÓPICO {match2.group(1)} — {match2.group(2).strip()}"
                else:
                    current_category = "ADESÃO AO TRATAMENTO"
            i += 1
            continue
        
        # Check for question header (### **X.X. Question text**)
        q_match = re.search(r'###\s*\*\*(\d+\.\d+)\.\s*(.+?)(\*\*)?$', line)
        if q_match:
            q_num = q_match.group(1)
            q_text = q_match.group(2).strip()
            if q_text.endswith('**'):
                q_text = q_text[:-2].strip()
            
            # Collect content until next question or section
            i += 1
            q_content = []
            while i < len(lines):
                next_line = lines[i]
                if next_line.startswith('###') or ('## **✅' in next_line):
                    break
                q_content.append(next_line)
                i += 1
            
            q_content_str = '\n'.join(q_content)
            
            # Find options - look for **( ) text**
            options = []
            option_matches = re.findall(r'\*\*\(\s*\)\s*(.+?)\*\*', q_content_str)
            for opt in option_matches:
                opt_text = opt.strip()
                # Skip empty options, placeholders, and "Outro" options (interface adds them automatically)
                if opt_text and not opt_text.startswith('[') and not opt_text.lower().startswith('outro'):
                    options.append({
                        "label": opt_text,
                        "value": opt_text[:50].lower().replace(' ', '_').replace(',', '').replace('.', '')
                    })
            
            # Determine question type
            has_open_response = '[Resposta aberta' in q_content_str or '📬' in q_content_str
            has_numeric = '[Resposta numérica]' in q_content_str or 'escala de 0 a 10' in q_text.lower()
            
            if has_numeric:
                q_type = "scale"
            elif len(options) > 0:
                q_type = "single_choice"
            else:
                q_type = "free_text"
            
            # Check for "Outro" option
            allow_other = any('outro' in opt.lower() for opt in option_matches)
            
            question = {
                "id": f"q_{len(questions) + 1}",
                "text": q_text,
                "type": q_type,
                "options": options,
                "category": current_category,
                "required": True,
                "allow_other": allow_other
            }
            
            questions.append(question)
            print(f"Q{len(questions)}: [{q_type}] {q_text[:50]}...")
            continue
        
        i += 1
    
    return questions


def update_quiz_template(questions):
    """Update the monthly_comprehensive quiz template with new questions"""
    db = next(get_db())
    
    quiz = db.query(QuizTemplate).filter(QuizTemplate.name == 'monthly_comprehensive').first()
    
    if not quiz:
        print("Quiz template 'monthly_comprehensive' not found!")
        return False
    
    print(f"\nUpdating quiz: {quiz.name}")
    print(f"Old questions count: {len(quiz.questions)}")
    print(f"New questions count: {len(questions)}")
    
    # Update
    quiz.questions = questions
    quiz.description = "Questionário Mensal de Bem-Estar - Checkup completo para acompanhamento do tratamento hormonal"
    
    db.commit()
    print("\n✅ Quiz template updated successfully!")
    
    return True


if __name__ == "__main__":
    filepath = "app/templates/arquivo/Quizz de Bem-Estar Mensal.md"
    
    print("Parsing markdown file...")
    questions = parse_markdown_quiz(filepath)
    
    print(f"\nTotal questions parsed: {len(questions)}")
    
    if questions:
        confirm = input("Update database? (y/n): ")
        if confirm.lower() == 'y':
            update_quiz_template(questions)
        else:
            print("Cancelled.")
