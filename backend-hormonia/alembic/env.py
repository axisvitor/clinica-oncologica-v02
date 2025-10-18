"""
Alembic environment configuration for Hormonia Backend System.

CRITICAL FIX: Import ALL models to ensure migrations capture complete schema.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.config import settings
from app.database import Base

# ============================================================================
# CRITICAL: Import ALL models to register with SQLAlchemy metadata
# ============================================================================
from app.models.base import BaseModel
from app.models.user import User, UserRole, AuthProvider
from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageDirection, MessageType, MessageStatus
from app.models.message_events import MessageStatusEvent, EvolutionWebhookEvent
from app.models.flow import PatientFlowState, FlowKind, FlowTemplateVersion
from app.models.quiz import QuizTemplate, QuizResponse
from app.models.report import MedicalReport
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.flow_analytics import FlowAnalytics, FlowMessage, QuizQuestion
from app.models.ab_experiment import (
    ABExperiment,
    ABVariantAssignment,
    ABExperimentMetric,
    ABExperimentResult,
    ABExperimentAudit,
    ABExperimentMonitoring,
    ExperimentStatus,
    VariantType,
    PatientSafetyLevel,
)
from app.models.audit_log import AuditLog, AuditEventType
from app.models.user_sync_log import UserSyncLog
from app.models.treatment import Treatment, TreatmentStatus, TreatmentType
from app.models.appointment import Appointment, AppointmentStatus, AppointmentType
from app.models.medication import Medication
from app.models.notification import Notification, NotificationType, NotificationPriority
from app.models.session import Session
from app.models.consent import Consent, ConsentType, ConsentStatus
from app.models.webhook_event import WebhookEvent
from app.models.failed_message import FailedMessage, FailureReason, DLQStatus
from app.models.error_tracking import ErrorLog

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from environment or settings."""
    # First try environment variable (Railway/production)
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Railway/Supabase often provides postgres:// URLs, but SQLAlchemy 1.4+ requires postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        return database_url

    # Fallback to app settings
    try:
        return settings.DATABASE_URL
    except Exception:
        # Last resort fallback
        return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,  # Better compatibility with PostgreSQL
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,  # Better compatibility with PostgreSQL
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
