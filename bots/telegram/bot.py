from fastapi import APIRouter, Request
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from bots.common.helpers import get_details_with_gemini, find_intelligent_matches
from app.config import settings

router = APIRouter()

telegram_app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to the ATS Candidate Search Bot!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_content = update.message.text
    await update.message.reply_text("✍️ Processing your job description...")

    details = await get_details_with_gemini(text_content)
    if not details:
        await update.message.reply_text("Sorry, could not extract details from your text.")
        return

    similar_candidates = await find_intelligent_matches(details)
    if not similar_candidates:
        await update.message.reply_text("No matching candidates found.")
        return

    for cand in similar_candidates[:5]:
        msg = (
            f"👤 Name: {cand.get('name', 'N/A')}\n"
            f"📧 Email: {cand.get('email', 'N/A')}\n"
            f"📍 Location: {cand.get('location', 'N/A')}\n"
            f"💼 Experience: {cand.get('experience', 'N/A')} years\n"
            f"✨ Match Score: {cand.get('final_match_score', 'N/A')}\n"
        )
        await update.message.reply_text(msg)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


@router.post("/")
async def telegram_webhook(request: Request):
    body = await request.json()
    update = Update.de_json(body, telegram_app.bot)
    await telegram_app.update_queue.put(update)
    return {"status": "ok"}
