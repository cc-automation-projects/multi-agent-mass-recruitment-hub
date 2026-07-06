"""
Main FastAPI application for MassRecruitHub.
"""

from celery.result import AsyncResult
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api.campaigns import router as campaigns_router
from src.api.candidates import router as candidates_router
from src.api.deletion import router as deletion_router
from src.api.messenger_webhook import router as webhook_router
from src.api.rpa_webhook import router as rpa_webhook_router
from src.api.telegram_webhook import router as telegram_router
from src.celery_app import celery_app
from src.core.logging_config import setup_logging

setup_logging()

app = FastAPI(
    title="MassRecruitHub API",
    description="Multi-agent mass recruitment system",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="src/static"), name="static")

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(campaigns_router)
app.include_router(candidates_router)
app.include_router(deletion_router)
app.include_router(webhook_router)
app.include_router(rpa_webhook_router)
app.include_router(telegram_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    task = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.ready() else None,
    }


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
