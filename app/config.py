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


