from fastapi import APIRouter, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from bots.common.helpers import (
    extract_text_from_file,
    get_details_with_gemini,
    find_intelligent_matches,
)

router = APIRouter()


@router.post("/analyze_resume")
async def analyze_resume(file: UploadFile = None, text: str = Form(None)):
    """Analyze uploaded resume file or job description text and return matched candidates."""
    if file:
        contents = await file.read()
        text_content = extract_text_from_file(file.filename, contents)
        if not text_content:
            raise HTTPException(
                status_code=400, detail="Could not extract text from file."
            )
    elif text:
        text_content = text
    else:
        raise HTTPException(status_code=400, detail="No file or text provided.")

    details = await get_details_with_gemini(text_content)
    if not details:
        raise HTTPException(
            status_code=400, detail="Could not extract details from text."
        )

    matches = await find_intelligent_matches(details)
    return JSONResponse(content={"matches": matches[:5] if matches else []})
