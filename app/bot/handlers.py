"""Telegram bot handlers — TikTok version with Approve & Send."""

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from app.config import settings
from app.core.gemini_audit import AdInput, generate_audit
from app.bot.cards import format_internal_card, format_email_block
from app.db.client import get_db

log = logging.getLogger(__name__)
router = Router()


def _is_authorized(user_id: int) -> bool:
    return user_id == settings.TELEGRAM_USER_ID


def audit_keyboard(lead_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Copy Email", callback_data=f"copy:{lead_id}"),
                InlineKeyboardButton(text="🔄 Regenerate", callback_data=f"regen:{lead_id}"),
            ],
            [
                InlineKeyboardButton(text="✅ Approve & Send", callback_data=f"send:{lead_id}"),
                InlineKeyboardButton(text="❌ Skip Lead", callback_data=f"skip:{lead_id}"),
            ],
        ]
    )


@router.message(Command("start"))
async def cmd_start(message: Message):
    if not _is_authorized(message.from_user.id):
        await message.answer("Not authorized.")
        return
    await message.answer(
        "✅ Special Agent TikTok online.\n\n"
        "You'll receive TikTok audit cards here. Tap [Approve & Send] to trigger Warmbly."
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    if not _is_authorized(message.from_user.id):
        await message.answer("Not authorized.")
        return
    db = get_db()
    leads = db.table("leads").select("status").execute().data or []
    sends = db.table("sends").select("id").execute().data or []
    by_status = {}
    for row in leads:
        s = row.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
    await message.answer(f"📊 <b>Status</b>\nLeads: {by_status}\nSends: {len(sends)}")


@router.callback_query(F.data.startswith("copy:"))
async def cb_copy(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    row = get_db().table("audits").select("*").eq("lead_id", lead_id).execute().data
    if not row:
        await cb.answer("Audit not found.")
        return
    await cb.message.answer(format_email_block(row[0]), parse_mode=None)
    await cb.answer("Email copied below ↑")


@router.callback_query(F.data.startswith("send:"))
async def cb_send(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    db = get_db()
    db.table("leads").update({"status": "queued"}).eq("id", lead_id).execute()
    
    # In the next step, we'll call /internal/outreach from here
    await cb.answer("Queued for Warmbly ✅")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("skip:"))
async def cb_skip(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    get_db().table("leads").update({"status": "skipped"}).eq("id", lead_id).execute()
    await cb.answer("Skipped")
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith("regen:"))
async def cb_regen(cb: CallbackQuery):
    if not _is_authorized(cb.from_user.id):
        await cb.answer("Not authorized.")
        return
    lead_id = cb.data.split(":", 1)[1]
    db = get_db()
    lead = db.table("leads").select("*").eq("id", lead_id).execute().data
    if not lead:
        await cb.answer("Lead not found.")
        return
    lead = lead[0]
    store = db.table("stores").select("*").eq("id", lead["store_id"]).execute().data[0]
    await cb.answer("Regenerating…")
    try:
        ad = AdInput(
            domain=store.get("domain", ""),
            brand=store.get("name"),
            headline=lead.get("ad_headline"),
            primary_text=lead.get("ad_primary"),
            image_url=lead.get("ad_image_url"),
            days_active=lead.get("days_active"),
            sender="James Liberty"
        )
        audit = generate_audit(ad)
        db.table("audits").update({
            "diagnosis": audit.diagnosis,
            "hook1_headline": audit.hook1_headline, "hook1_text": audit.hook1_text, "hook1_image": audit.hook1_image,
            "hook2_headline": audit.hook2_headline, "hook2_text": audit.hook2_text, "hook2_image": audit.hook2_image,
            "email_subject": audit.email_subject, "email_body": audit.email_body,
        }).eq("lead_id", lead_id).execute()
        updated_row = db.table("audits").select("*").eq("lead_id", lead_id).execute().data[0]
        card = format_internal_card(
            {"brand": store.get("name"), "domain": store.get("domain"), "days_active": lead.get("days_active"), "page_profile_uri": store.get("page_profile_uri")},
            updated_row
        )
        await cb.message.answer(card, reply_markup=audit_keyboard(lead_id))
    except Exception as e:
        log.exception("regen failed")
        await cb.message.answer(f"Regenerate failed: {e}")
