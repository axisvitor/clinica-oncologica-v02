"""Settings-free SQLAlchemy declarative base used by runtime and Alembic."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
