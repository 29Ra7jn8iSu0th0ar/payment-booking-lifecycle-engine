from fastapi import FastAPI
from src.api.routes.routes import router
from src.infrastructure.db.session import engine
from src.infrastructure.db.models import Base

app = FastAPI(title="District Integrity Engine")

Base.metadata.create_all(bind=engine)

app.include_router(router)
