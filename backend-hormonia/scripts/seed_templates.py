"""
Script to seed default message templates into the database.
"""
import sys
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import get_scoped_session, create_tables
from app.models.template import MessageTemplate
from app.repositories.template import TemplateRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_templates():
    """Seed default templates."""
    logger.info("Creating tables if they don't exist...")
    create_tables()

    default_templates = [
        {
            "name": "appointment_reminder",
            "content": "Olá {patient_name}! Lembramos que você tem uma consulta marcada para {appointment_date} às {appointment_time} com Dr(a). {doctor_name}. Por favor, confirme sua presença.",
            "variables": ["patient_name", "appointment_date", "appointment_time", "doctor_name"]
        },
        {
            "name": "appointment_confirmation",
            "content": "Sua consulta foi confirmada para {appointment_date} às {appointment_time}. Endereço: {clinic_address}. Em caso de dúvidas, entre em contato conosco.",
            "variables": ["appointment_date", "appointment_time", "clinic_address"]
        },
        {
            "name": "test_results",
            "content": "Olá {patient_name}! Seus exames estão prontos. Por favor, entre em contato conosco para agendar uma consulta para discussão dos resultados.",
            "variables": ["patient_name"]
        },
        {
            "name": "prescription_ready",
            "content": "Sua receita médica está pronta para retirada. Horário de funcionamento: Segunda a Sexta das 8h às 18h.",
            "variables": []
        },
        {
            "name": "welcome_message",
            "content": "Bem-vindo(a) à Clínica Oncológica! Estamos aqui para cuidar de você. Em caso de emergência, ligue para {emergency_phone}.",
            "variables": ["emergency_phone"]
        },
        {
            "name": "payment_reminder",
            "content": "Olá {patient_name}! Temos uma pendência financeira em seu nome no valor de R$ {amount}. Por favor, entre em contato para regularização.",
            "variables": ["patient_name", "amount"]
        }
    ]

    with get_scoped_session() as db:
        repo = TemplateRepository(db)
        
        for tmpl_data in default_templates:
            existing = repo.get_by_name(tmpl_data["name"])
            if not existing:
                logger.info(f"Creating template: {tmpl_data['name']}")
                template = MessageTemplate(**tmpl_data)
                repo.create(template)
            else:
                logger.info(f"Template already exists: {tmpl_data['name']}")
                # Optional: Update content if needed
                # existing.content = tmpl_data["content"]
                # existing.variables = tmpl_data["variables"]
                # db.add(existing)
        
        logger.info("Seeding completed successfully.")

if __name__ == "__main__":
    seed_templates()
