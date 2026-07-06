"""
Вебхук для Telegram-бота.
"""

from aiogram.types import Update
from fastapi import APIRouter, Request, Response

from src.bot.telegram import bot, dp, on_shutdown, on_startup

router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.on_event("startup")
async def startup_event():
    await on_startup()


@router.on_event("shutdown")
async def shutdown_event():
    await on_shutdown()


@router.post("/webhook")
async def telegram_webhook(request: Request) -> Response:
    update_data = await request.json()
    update = Update(**update_data)
    await dp.feed_update(bot, update)
    return Response(status_code=200)
