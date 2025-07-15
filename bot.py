import os
import requests
import google.generativeai as genai
import pypdf
import docx
import io
import json
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Securely fetch credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ATS_API_BASE_URL = os.getenv("ATS_API_BASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Ensure all required environment variables are set
if not all([TELEGRAM_BOT_TOKEN, ATS_API_BASE_URL, GEMINI_API_KEY]):
    raise ValueError("One or more required environment variables are missing.")

# Configure the Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Helper Functions
def extract_text_from_file(file_path: str, file_content: bytes) -> str:
    """Extracts text from PDF or DOCX files."""
    text = ""
    try:
        if file_path.lower().endswith('.pdf'):
            with io.BytesIO(file_content) as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
        elif file_path.lower().endswith('.docx'):
            with io.BytesIO(file_content) as f:
                doc = docx.Document(f)
                for para in doc.paragraphs:
                    text += para.text + "\n"
        else:
            return None
    except Exception as e:
        print(f"Error extracting text: {e}")
        return None
    return text

# Uses Gemini to extract a summary of skills, experience, and location from text.
async def get_details_with_gemini(text_content: str) -> dict | None:    
    if not text_content:
        return None

    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    
    prompt = f"""
    Analyze the following text from a resume or job description and extract the key details.
    Return the output as a single, clean JSON object with three keys: "skills", "experience", and "location".

    - "skills": A short, comma-separated string of the **top 5 to 7 most important technical skills only**.
    - "experience": An integer representing the total years of work experience. Default to 3 if not found.
    - "location": A single city name. Default to "any" if not found.

    Text Content:
    ---
    {text_content}
    ---
    """
    try:
        response = await model.generate_content_async(prompt)
        # Clean up the response to ensure it's a valid JSON string
        json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

async def find_similar_resumes(details: dict) -> list | None:
    if not all(k in details for k in ['skills', 'experience', 'location']):
        return None

    params = {
        "job_id": "telegram_search",
        "email_id": "bot@example.com",
        "skills": details['skills'],
        "exp_l": max(0, int(details.get('experience', 3)) - 2),
        "exp_h": int(details.get('experience', 3)) + 2,
        "location": details['location'],
        "job_title": "Similar Profile"
    }

    try:
        async with httpx.AsyncClient() as client:
            api_url = f"{ATS_API_BASE_URL}/candidates"
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"Error calling FastAPI: {e}")
        return None


# Telegram Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    if update.message:
        await update.message.reply_text(
            "👋 Welcome to the ATS Candidate Search Bot!\n\n"
            "To get started, please upload a resume file (PDF or DOCX). "
            "I will analyze it and find similar candidates from the database."
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles document uploads (resumes)."""
    if not update.message or not update.message.document:
        return

    document = update.message.document
    if not document.file_name or not document.file_name.lower().endswith(('.pdf', '.docx')):
        await update.message.reply_text("Unsupported file type. Please upload a PDF or DOCX file.")
        return

    processing_message = await update.message.reply_text(f"📄 Processing '{document.file_name}'... Please wait.")

    file = await context.bot.get_file(document.file_id)
    file_content = await file.download_as_bytearray()
    text_content = extract_text_from_file(document.file_name, bytes(file_content))

    if not text_content:
        await processing_message.edit_text("Could not extract text from the file. It might be empty or corrupted.")
        return

    await processing_message.edit_text("🧠 Analyzing content with Gemini to extract key details...")
    details = await get_details_with_gemini(text_content)

    if not details:
        await processing_message.edit_text("Sorry, I couldn't understand the file's content. Please try another one.")
        return

    extracted_info = (
        f"🔍 **Extracted Details:**\n"
        f"  - **Skills:** {details.get('skills')}\n"
        f"  - **Experience:** {details.get('experience')} years\n"
        f"  - **Location:** {details.get('location')}\n\n"
        "Now searching for similar candidates in the database..."
    )
    await processing_message.edit_text(extracted_info, parse_mode='Markdown')

    similar_candidates = await find_similar_resumes(details)

    if not similar_candidates:
        await processing_message.edit_text("Could not find any matching candidates in the database.")
        return

    await processing_message.edit_text(f"✅ Found {len(similar_candidates)} similar candidates:")
    for cand in similar_candidates[:5]:  # Display top 5 matches
        message = (
            f"👤 **Name:** {cand.get('name', 'N/A')}\n"
            f"📧 **Email:** {cand.get('email', 'N/A')}\n"
            f"📍 **Location:** {cand.get('location', 'N/A')}\n"
            f"💼 **Experience:** {cand.get('experience', 'N/A')} years\n"
            f"✨ **Match Score:** {cand.get('match_score', 'N/A')}"
        )
        await update.message.reply_text(message, parse_mode='Markdown')

def main() -> None:
    """Start the bot."""
    print("Starting ATS Candidate Search Bot...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers for commands and messages
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    # Run bot
    application.run_polling()

if __name__ == "__main__":
    main()