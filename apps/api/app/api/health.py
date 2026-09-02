from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    service: str
    status: Literal["healthy"]
    environment: str
    database: Literal["sqlite", "postgresql", "other"]
    celery_eager: bool


@router.get("/health", response_model=HealthResponse)
def health(
    session: Annotated[Session, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    session.execute(text("SELECT 1"))
    return HealthResponse(
        service="recoveriq-api",
        status="healthy",
        environment=settings.app_env,
        database=settings.database_kind,
        celery_eager=settings.celery_task_always_eager,
    )
