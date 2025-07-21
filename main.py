import os
import google.generativeai as genai
import pypdf
import docx
import io
import json
import httpx
import asyncio
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

# --- Helper Functions ---
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

def local_match_skill(candidate_skills_str: str, requested_skills_str: str) -> int:
    """A local version of the skill matcher to re-rank candidates."""
    if not candidate_skills_str or not requested_skills_str:
        return 0
    candidate_skills = {s.lower().strip() for s in candidate_skills_str.split(',')}
    requested_skills = {s.lower().strip() for s in requested_skills_str.split(',')}
    return len(candidate_skills.intersection(requested_skills))

async def get_details_with_gemini(text_content: str) -> dict | None:
    """Uses Gemini to extract skills and experience."""
    if not text_content:
        return None
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    prompt = f"""
    Analyze the following text and extract the key details.
    Return a clean JSON object with "skills" and "experience".
    - "skills": A comma-separated string of the top 5-7 most important technical skills.
    - "experience": An integer for total years of experience (default to 3 if not found).
    Text:
    ---
    {text_content}
    ---
    """
    try:
        response = await model.generate_content_async(prompt)
        json_str = response.text.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None

async def fetch_candidates_for_skill(details: dict, skill: str) -> list | None:
    """Makes a single API call for one skill."""
    params = {
        "skills": skill,
        "exp_l": max(0, int(details.get('experience', 3)) - 2),
        "exp_h": int(details.get('experience', 3)) + 2,
        "location": "bangalore",
        "job_id": "telegram_search_sub",
        "email_id": "bot@example.com",
        "job_title": f"Search for {skill}"
    }
    try:
        async with httpx.AsyncClient() as client:
            api_url = f"{ATS_API_BASE_URL}/candidates"
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"API call for skill '{skill}' failed: {e}")
        return None

async def find_intelligent_matches(details: dict) -> list | None:
    """Orchestrates multiple API calls and re-ranks the results."""
    original_skills_str = details.get('skills')
    if not original_skills_str:
        return None

    skill_list = [s.strip() for s in original_skills_str.split(',')]
    
    # Create and run API call tasks concurrently
    tasks = [fetch_candidates_for_skill(details, skill) for skill in skill_list]
    results_from_calls = await asyncio.gather(*tasks)

    # Aggregate unique candidates using their email as a key
    all_candidates = {}
    for result_list in results_from_calls:
        if result_list:
            for cand in result_list:
                email = cand.get('email')
                if email:
                    all_candidates[email] = cand
    
    if not all_candidates:
        return None

    unique_list = list(all_candidates.values())

    # Re-score candidates based on the original full list of skills
    for cand in unique_list:
        cand['final_match_score'] = local_match_skill(cand.get('skills'), original_skills_str)

    # Sort by the new, more accurate score in descending order
    return sorted(unique_list, key=lambda x: x.get('final_match_score', 0), reverse=True)

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