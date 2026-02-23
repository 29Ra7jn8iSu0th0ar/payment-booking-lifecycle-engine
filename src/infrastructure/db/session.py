# src/infrastructure/db/session.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.engine import Engine
from contextlib import contextmanager
import os


# -----------------------------
# Database URL
# -----------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/district_engine",
)


# -----------------------------
# Engine
# -----------------------------
engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)


# -----------------------------
# Base Class for Models
# -----------------------------
class Base(DeclarativeBase):
    pass


# -----------------------------
# Session Factory
# -----------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# -----------------------------
# Context Manager (Non-FastAPI usage)
# -----------------------------
@contextmanager
def get_db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
