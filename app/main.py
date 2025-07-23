from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bots.teams.bot import router as teams_router
from bots.telegram.bot import router as telegram_router
from api.endpoints import router as api_router

app = FastAPI(title="ATS Candidate Search Bot API")

# CORS (adjust origins in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(teams_router, prefix="/api/messages", tags=["Microsoft Teams Bot"])
app.include_router(
    telegram_router, prefix="/api/telegram_webhook", tags=["Telegram Bot"]
)
app.include_router(api_router, prefix="/api", tags=["General API"])
