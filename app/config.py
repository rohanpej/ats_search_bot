import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN")
    ATS_API_BASE_URL: str = os.getenv("ATS_API_BASE_URL")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY")
    MICROSOFT_APP_ID: str = os.getenv("MICROSOFT_APP_ID")
    MICROSOFT_APP_PASSWORD: str = os.getenv("MICROSOFT_APP_PASSWORD")


settings = Settings()

# Validate required env vars
required_vars = [
    settings.TELEGRAM_BOT_TOKEN,
    settings.ATS_API_BASE_URL,
    settings.GEMINI_API_KEY,
    settings.MICROSOFT_APP_ID,
    settings.MICROSOFT_APP_PASSWORD,
]

if not all(required_vars):
    missing = [
        name
        for name, val in zip(
            [
                "TELEGRAM_BOT_TOKEN",
                "ATS_API_BASE_URL",
                "GEMINI_API_KEY",
                "MICROSOFT_APP_ID",
                "MICROSOFT_APP_PASSWORD",
            ],
            required_vars,
        )
        if not val
    ]
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing)}"
    )
