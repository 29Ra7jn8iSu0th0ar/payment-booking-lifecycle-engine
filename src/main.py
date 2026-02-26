import logging
import os
import time

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.api.routes.routes import router
from src.infrastructure.db.session import engine
from src.infrastructure.db.models import Base

app = FastAPI(title="District Integrity Engine")

app.include_router(router)
logger = logging.getLogger(__name__)


def _wait_for_db() -> None:
    # Handles the common case where API starts before Postgres is ready.
    max_retries = int(os.getenv("DB_CONNECT_MAX_RETRIES", "30"))
    retry_delay_seconds = float(os.getenv("DB_CONNECT_RETRY_DELAY", "1.5"))

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database is reachable.")
            return
        except OperationalError:
            if attempt == max_retries:
                logger.exception(
                    "Database not reachable after %s attempts. Check DATABASE_URL and Postgres status.",
                    max_retries,
                )
                raise
            logger.warning(
                "Database not ready (attempt %s/%s). Retrying in %.1f seconds...",
                attempt,
                max_retries,
                retry_delay_seconds,
            )
            time.sleep(retry_delay_seconds)


@app.on_event("startup")
def on_startup() -> None:
    _wait_for_db()
    Base.metadata.create_all(bind=engine)
