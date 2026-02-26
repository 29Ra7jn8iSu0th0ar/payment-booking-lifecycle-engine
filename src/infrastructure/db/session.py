# src/infrastructure/db/session.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.engine import Engine
from contextlib import contextmanager
from dotenv import load_dotenv
import socket
import os

load_dotenv()


# -----------------------------
# Database URL
# -----------------------------
def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _default_database_url() -> str:
    # On Windows local installs often run Postgres on 5433; prefer 5432, then 5433.
    if _is_port_open("localhost", 5432):
        port = 5432
    elif _is_port_open("localhost", 5433):
        port = 5433
    else:
        port = 5432
    return f"postgresql+psycopg2://postgres:postgres@localhost:{port}/district_engine"


DATABASE_URL = os.getenv("DATABASE_URL", _default_database_url())


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
