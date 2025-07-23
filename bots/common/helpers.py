import io
import json
import asyncio
import pypdf
import docx
import httpx
import google.generativeai as genai

from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)


def extract_text_from_file(file_path: str, file_content: bytes) -> str | None:
    """Extract text from PDF or DOCX files."""
    text = ""
    try:
        if file_path.lower().endswith(".pdf"):
            with io.BytesIO(file_content) as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
        elif file_path.lower().endswith(".docx"):
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
    """Calculate number of matching skills between candidate and requested skills."""
    if not candidate_skills_str or not requested_skills_str:
        return 0
    candidate_skills = {s.lower().strip() for s in candidate_skills_str.split(",")}
    requested_skills = {s.lower().strip() for s in requested_skills_str.split(",")}
    return len(candidate_skills.intersection(requested_skills))


async def get_details_with_gemini(text_content: str) -> dict | None:
    """Use Gemini to extract skills and experience from text content."""
    if not text_content:
        return None
    model = genai.GenerativeModel("gemini-1.5-flash-latest")
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
        json_str = (
            response.text.strip().replace("```json", "").replace("```", "").strip()
        )
        return json.loads(json_str)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None


async def fetch_candidates_for_skill(details: dict, skill: str) -> list | None:
    """Call ATS API for candidates matching a skill and experience range."""
    params = {
        "skills": skill,
        "exp_l": max(0, int(details.get("experience", 3)) - 2),
        "exp_h": int(details.get("experience", 3)) + 2,
        "location": "bangalore",
        "job_id": "telegram_search_sub",
        "email_id": "bot@example.com",
        "job_title": f"Search for {skill}",
    }
    try:
        async with httpx.AsyncClient() as client:
            api_url = f"{settings.ATS_API_BASE_URL}/candidates"
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            return response.json()
    except httpx.RequestError as e:
        print(f"API call for skill '{skill}' failed: {e}")
        return None


async def find_intelligent_matches(details: dict) -> list | None:
    """Call ATS API for each skill concurrently and aggregate unique candidates sorted by match score."""
    original_skills_str = details.get("skills")
    if not original_skills_str:
        return None

    skill_list = [s.strip() for s in original_skills_str.split(",")]

    tasks = [fetch_candidates_for_skill(details, skill) for skill in skill_list]
    results_from_calls = await asyncio.gather(*tasks)

    all_candidates = {}
    for result_list in results_from_calls:
        if result_list:
            for cand in result_list:
                email = cand.get("email")
                if email:
                    all_candidates[email] = cand

    if not all_candidates:
        return None

    unique_list = list(all_candidates.values())

    for cand in unique_list:
        cand["final_match_score"] = local_match_skill(
            cand.get("skills"), original_skills_str
        )

    return sorted(
        unique_list, key=lambda x: x.get("final_match_score", 0), reverse=True
    )
