import os
from dotenv import load_dotenv

load_dotenv()

# Twilio
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_PHONE_NUMBER = os.environ["TWILIO_PHONE_NUMBER"]

# Deepgram
DEEPGRAM_API_KEY = os.environ["DEEPGRAM_API_KEY"]
DEEPGRAM_WS_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=linear16"
    "&sample_rate=16000"
    "&channels=1"
    "&model=nova-3"
    "&interim_results=false"
    "&endpointing=300"
    "&punctuate=true"
    "&smart_format=true"
)

# vLLM
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
LLM_MODEL = "Qwen/Qwen3-8B"

# Audio
TWILIO_SAMPLE_RATE = 8000
DEEPGRAM_SAMPLE_RATE = 16000
KOKORO_SAMPLE_RATE = 24000
MULAW_SAMPLE_WIDTH = 1  # 8-bit mulaw
PCM_SAMPLE_WIDTH = 2    # 16-bit PCM

# Conversation
MAX_HISTORY_EXCHANGES = 10  # keep last N user/assistant pairs

SYSTEM_PROMPT = """\
You are a friendly receptionist for an electrical company. \
Keep responses short and conversational — 1-2 sentences max. \
You're on a phone call, not writing an essay. /no_think"""

# Deepgram keepalive interval (seconds)
DEEPGRAM_KEEPALIVE_INTERVAL = 8
