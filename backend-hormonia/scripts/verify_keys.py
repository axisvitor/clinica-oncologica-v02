
import os
import sys
import logging
from uuid import UUID

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load .env explicitly to compare
load_dotenv(override=True)
env_key = os.getenv("ENCRYPTION_KEY_CURRENT")

from app.core.encryption import EncryptionService
from app.database import SessionLocal
from app.models.patient import Patient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print(f"Environment Key (Direct): {env_key[:5]}..." if env_key else "None")
    
    try:
        service = EncryptionService()
        app_key = service.current_key.decode()
        print(f"App Service Key:        {app_key[:5]}...")
        
        if env_key != app_key:
            print("MISMATCH: Environment key does not match App Service key!")
        else:
            print("MATCH: Keys match.")
            
        # Test Roundtrip
        original = "test-data"
        encrypted = service.encrypt(original)
        decrypted = service.decrypt(encrypted)
        print(f"Roundtrip Test: {'SUCCESS' if original == decrypted else 'FAILED'}")
        
        # Test Database Record
        db = SessionLocal()
        try:
            patient = db.query(Patient).first()
            if patient:
                print(f"Found Patient: {patient.id}")
                print(f"Encrypted Name: {patient.name}") # Name is not encrypted, but let's check PII
                print(f"Encrypted CPF: {patient.cpf_encrypted[:10]}..." if patient.cpf_encrypted else "None")
                
                try:
                    decrypted_cpf = patient.cpf_decrypted
                    print(f"Decrypted CPF: {decrypted_cpf}")
                except Exception as e:
                    print(f"Decryption FAILED for DB record: {e}")
            else:
                print("No patients found in DB.")
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error initializing service: {e}")

if __name__ == "__main__":
    main()
