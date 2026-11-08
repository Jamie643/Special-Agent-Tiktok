"""FastAPI entrypoint for Special Agent TikTok."""

import logging
from fastapi import FastAPI, Request, BackgroundTasks
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.bot.handlers import router as bot_router
from app.core.daily_job import run_daily_pipeline
from app.core.outreach import send_to_warmbly

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="Special Agent TikTok")

bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()
dp.include_router(bot_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "special-agent-tiktok"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post(f"/webhook/{settings.TELEGRAM_BOT_TOKEN}")
async def telegram_webhook(request: Request):
    update = await request.json()
    from aiogram.types import Update
    await dp.feed_update(bot, Update.model_validate(update))
    return {"ok": True}


@app.post("/internal/run-daily")
async def trigger_daily(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_daily_pipeline, bot)
    return {"ok": True, "message": "Daily job started"}


@app.post("/internal/outreach/{lead_id}")
async def trigger_outreach(lead_id: str):
    """Called by the [Approve & Send] button."""
    result = await send_to_warmbly(lead_id)
    return result
