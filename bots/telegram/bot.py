from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    if update.message:
        await update.message.reply_text(
            "👋 Welcome to the ATS Candidate Search Bot!\n\n"
            "You can either:\n"
            "1. **Upload a resume file** (PDF or DOCX).\n"
            "2. **Paste the text** of a job description.\n\n"
            "I will analyze the content and find the most relevant candidates."
        )

async def process_and_reply(text_content: str, update: Update, processing_message) -> None:
    """General purpose function to process text, find candidates, and reply."""
    await processing_message.edit_text("🧠 Analyzing content with Gemini...")
    details = await get_details_with_gemini(text_content)

    if not details:
        await processing_message.edit_text("Sorry, I couldn't understand the content. Please try again.")
        return

    extracted_info = (
        f"🔍 **Extracted Details:**\n"
        f"  - **Skills:** {details.get('skills')}\n"
        f"  - **Experience:** {details.get('experience')} years\n\n"
        "Searching for the best matches..."
    )
    await processing_message.edit_text(extracted_info, parse_mode='Markdown')

    # Use the new intelligent search function
    similar_candidates = await find_intelligent_matches(details)

    if not similar_candidates:
        await processing_message.edit_text("Could not find any matching candidates in the database.")
        return

    await processing_message.edit_text(f"✅ Found {len(similar_candidates)} relevant candidates. Here are the top 5:")
    
    for cand in similar_candidates[:5]:
        message_parts = [
            f"👤 **Name:** {cand.get('name', 'N/A')}",
            f"📧 **Email:** {cand.get('email', 'N/A')}",
            f"📍 **Location:** {cand.get('location', 'N/A')}",
            f"💼 **Experience:** {cand.get('experience', 'N/A')} years",
            # Use the new, more accurate score
            f"✨ **Match Score:** {cand.get('final_match_score', 'N/A')}"
        ]
        filename = cand.get('filenames')
        if filename and filename != 'N/A':
            resume_url = f"{ATS_API_BASE_URL}/download-resume/{filename}"
            message_parts.append(f"📄 [Download Resume]({resume_url})")
            
        message = "\n".join(message_parts)
        await update.message.reply_text(message, parse_mode='Markdown')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles document uploads (resumes)."""
    if not update.message or not update.message.document: return
    document = update.message.document
    if not document.file_name or not document.file_name.lower().endswith(('.pdf', '.docx')):
        await update.message.reply_text("Unsupported file type. Please upload a PDF or DOCX file.")
        return
    processing_message = await update.message.reply_text(f"📄 Processing '{document.file_name}'...")
    file = await context.bot.get_file(document.file_id)
    file_content = await file.download_as_bytearray()
    text_content = extract_text_from_file(document.file_name, bytes(file_content))
    if not text_content:
        await processing_message.edit_text("Could not extract text from the file.")
        return
    await process_and_reply(text_content, update, processing_message)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles plain text messages (job descriptions)."""
    if not update.message or not update.message.text: return
    text_content = update.message.text
    processing_message = await update.message.reply_text("✍️ Processing job description...")
    await process_and_reply(text_content, update, processing_message)



def main() -> None:
    """Start the bot."""
    print("Starting ATS Candidate Search Bot...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.run_polling()

if __name__ == "__main__":
    main()