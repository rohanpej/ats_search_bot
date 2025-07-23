from fastapi import APIRouter, Request
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    BotFrameworkAdapter,
    TurnContext,
    MessageFactory,
)
from botbuilder.schema import Activity, ActivityTypes
import httpx
import asyncio

from bots.common.helpers import (
    extract_text_from_file,
    get_details_with_gemini,
    find_intelligent_matches,
)
from app.config import settings

router = APIRouter()

SETTINGS = BotFrameworkAdapterSettings(
    app_id=settings.MICROSOFT_APP_ID, app_password=settings.MICROSOFT_APP_PASSWORD
)
ADAPTER = BotFrameworkAdapter(SETTINGS)


async def extract_text_from_attachment(attachment, turn_context):
    try:
        url = attachment.content_url
        headers = {}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            content_bytes = response.content
        filename = attachment.name or "file"
        return extract_text_from_file(filename, content_bytes)
    except Exception as e:
        print(f"Error extracting attachment text: {e}")
        return None


class CandidateSearchBot:
    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text
        attachments = turn_context.activity.attachments or []

        if attachments:
            await turn_context.send_activity("📄 Processing your uploaded resume...")
            for attachment in attachments:
                text_content = await extract_text_from_attachment(attachment, turn_context)
                if not text_content:
                    await turn_context.send_activity("⚠️ Could not extract text from your file.")
                    continue
                await self.process_and_reply(text_content, turn_context)
        elif text:
            await turn_context.send_activity("✍️ Processing your job description...")
            await self.process_and_reply(text, turn_context)
        else:
            await turn_context.send_activity(
                "Please send a job description or upload a resume file."
            )

    async def process_and_reply(self, text_content: str, turn_context: TurnContext):
        await turn_context.send_activity("🧠 Analyzing content with Gemini...")
        details = await get_details_with_gemini(text_content)
        if not details:
            await turn_context.send_activity(
                "Sorry, I couldn't understand the content."
            )
            return

        extracted_info = (
            f"🔍 Extracted Details:\n- Skills: {details.get('skills')}\n"
            f"- Experience: {details.get('experience')} years\n\nSearching matches..."
        )
        await turn_context.send_activity(extracted_info)

        similar_candidates = await find_intelligent_matches(details)
        if not similar_candidates:
            await turn_context.send_activity("No matching candidates found.")
            return

        for cand in similar_candidates[:5]:
            msg = (
                f"👤 Name: {cand.get('name', 'N/A')}\n"
                f"📧 Email: {cand.get('email', 'N/A')}\n"
                f"📍 Location: {cand.get('location', 'N/A')}\n"
                f"💼 Experience: {cand.get('experience', 'N/A')} years\n"
                f"✨ Match Score: {cand.get('final_match_score', 'N/A')}\n"
            )
            filename = cand.get("filenames")
            if filename and filename != "N/A":
                resume_url = f"{settings.ATS_API_BASE_URL}/download-resume/{filename}"
                msg += f"[Download Resume]({resume_url})\n"

            await turn_context.send_activity(MessageFactory.text(msg))


BOT = CandidateSearchBot()


@router.post("/")
async def messages(req: Request):
    body = await req.json()
    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def aux_func(turn_context: TurnContext):
        if activity.type == ActivityTypes.message:
            await BOT.on_message_activity(turn_context)
        else:
            await turn_context.send_activity(f"[{activity.type} event received.]")

    try:
        await ADAPTER.process_activity(activity, auth_header, aux_func)
        return {"status": "ok"}
    except Exception as e:
        print(f"Error handling Teams message: {e}")
        return {"error": str(e)}
