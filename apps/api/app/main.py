from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.batch_explorer import router as batch_explorer_router
from app.api.evaluation import router as evaluation_router
from app.api.health import router as health_router
from app.api.payment_health import router as payment_health_router
from app.api.razorpay import router as razorpay_router
from app.api.razorpay_evidence import router as razorpay_evidence_router
from app.api.safety import router as safety_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(debug=settings.debug)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await logger.ainfo("application_started", environment=settings.app_env)
    yield
    await logger.ainfo("application_stopped")


app = FastAPI(
    title="RecoverIQ API",
    version="0.1.0",
    description="Degradation-aware recurring-payment recovery foundation",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(batch_explorer_router)
app.include_router(health_router)
app.include_router(razorpay_router)
app.include_router(evaluation_router)
app.include_router(payment_health_router)
app.include_router(safety_router)
app.include_router(razorpay_evidence_router)
