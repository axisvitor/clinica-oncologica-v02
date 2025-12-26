
import os
import sys
import logging
import random
import traceback
from datetime import date, timedelta
from typing import List
from uuid import uuid4

from dotenv import load_dotenv

# Load/reload .env file explicitly
load_dotenv(override=True)

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verify keys BEFORE importing app modules
if not os.getenv("ENCRYPTION_KEY_CURRENT"):
    print("CRITICAL: ENCRYPTION_KEY_CURRENT missing from environment.", file=sys.stderr)
    sys.exit(1)

from faker import Faker
from sqlalchemy import text
from sqlalchemy.orm import Session

# VALIDATION: Ensure app imports work
try:
    from app.database import SessionLocal
    from app.models.patient import Patient, FlowState
    from app.models.user import User
except ImportError as e:
    print(f"CRITICAL: Failed to import app modules: {e}", file=sys.stderr)
    sys.exit(1)

# Configure logging - reduced noise
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

fake = Faker('pt_BR')

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_admin_user(db: Session) -> User:
    """Get the admin user to associate patients with."""
    user = db.query(User).filter(User.email == "admin@neoplasiaslitoral.com").first()
    if not user:
        # Fallback
        user = db.query(User).first()
        if not user:
             raise ValueError("No users found in database. Cannot create patients without a doctor.")
        logger.warning(f"Admin user not found. Using first available user: {user.email}")
    return user

def truncate_patients_table(db: Session):
    """Truncate the patients table and cascade delete related data."""
    logger.info("Truncating patients table...")
    db.execute(text("TRUNCATE TABLE patients CASCADE"))
    db.commit()
    logger.info("Patients table truncated successfully.")

def create_dummy_patients(db: Session, doctor: User, count: int = 50):
    """Create dummy patients with valid encryption."""
    logger.info(f"Creating {count} dummy patients...")
    
    patients = []
    for _ in range(count):
        name = fake.name()
        birth_date = fake.date_of_birth(minimum_age=18, maximum_age=90)
        cpf = fake.cpf()
        email = fake.email()
        phone = fake.cellphone_number()
        diagnosis = fake.sentence(nb_words=6)
        
        flow_state = random.choice(list(FlowState))
        current_day = random.randint(0, 30)
        
        patient = Patient(
            id=uuid4(),
            doctor_id=doctor.id,
            name=name,
            birth_date=birth_date,
            treatment_type="Hormonioterapia",
            treatment_start_date=date.today() - timedelta(days=random.randint(0, 365)),
            flow_state=flow_state,
            current_day=current_day,
            diagnosis=diagnosis,
            treatment_phase="Manutenção",
            doctor_notes=fake.text(),
            patient_data={"custom_fields": {"generated": True}}
        )
        
        # Encryption
        patient.set_cpf(cpf)
        patient.set_email(email)
        patient.set_phone(phone)
        
        patients.append(patient)
    
    db.add_all(patients)
    db.commit()
    logger.info(f"Successfully created {count} patients.")

def main():
    logger.info(f"Starting reset process. Key prefix: {os.getenv('ENCRYPTION_KEY_CURRENT')[:5]}...")
        
    try:
        db = next(get_db())
        admin_user = get_admin_user(db)
        logger.info(f"Using user: {admin_user.email}")
        
        truncate_patients_table(db)
        create_dummy_patients(db, admin_user)
        
        logger.info("DONE: Reset and seed completed successfully!")
        
    except Exception:
        logger.error("An error occurred during execution:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
