"""
IMS Backend — FastAPI application entrypoint.
"""
import asyncio
import logging
import logging.config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, rca, signals, workitems
from app.core.config import get_settings
from app.db.connections import close_mongo, close_redis, engine
from app.models.orm import Base
from app.workers.signal_worker import run_worker

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Incident Management System",
    description="Mission-critical IMS for distributed stack monitoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(signals.router)
app.include_router(workitems.router)
app.include_router(rca.router)


@app.on_event("startup")
async def startup():
    logger.info("IMS backend starting up (env=%s)", settings.environment)

    # Create all tables (idempotent — does not drop existing)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables verified/created")

    # Start background signal worker
    asyncio.create_task(run_worker(concurrency=20))
    logger.info("Signal worker task scheduled")


@app.on_event("shutdown")
async def shutdown():
    logger.info("IMS backend shutting down")
    await close_mongo()
    await close_redis()
    await engine.dispose()
