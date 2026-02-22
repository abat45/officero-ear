# OFFICERO EAR V0 — Minimal Voice AI Call

## Goal
Call Twilio number → AI answers → have a conversation. That's it.

## Pipeline
```
Caller → Twilio (mulaw 8kHz) → FastAPI WebSocket → Deepgram STT → Qwen3-8B (vLLM) → Kokoro TTS → Twilio → Caller hears response
```

## Infrastructure
- **RunPod** — A40 48GB. Runs LLM + TTS + backend.
- **Twilio** — Phone number active. Media Streams for bidirectional WebSocket audio.

## Models on A40

| Model | Purpose | Serve with |
|-------|---------|------------|
| Qwen3-8B-Instruct | Conversational LLM | vLLM (OpenAI-compatible API) |
| Kokoro-82M | Text-to-speech | Python library `kokoro` |

## External API
- **Deepgram Nova-3** — Streaming STT with end-of-turn detection. $0.0043/min.

## Backend
- **FastAPI** with WebSocket endpoint
- Twilio sends mulaw 8kHz base64 audio chunks every 20ms
- Convert mulaw 8kHz → PCM 16kHz → send to Deepgram WebSocket
- Deepgram returns transcript → send to vLLM
- vLLM returns text → send to Kokoro
- Kokoro returns PCM 24kHz audio → convert to mulaw 8kHz → send back to Twilio

## LLM System Prompt (simple for now)
```
You are a friendly receptionist for an electrical company. 
Keep responses short and conversational — 1-2 sentences max.
You're on a phone call, not writing an essay.
```

## Twilio Config
Incoming call webhook returns TwiML:
```xml
<Response>
  <Connect>
    <Stream url="wss://YOUR_RUNPOD_URL/twilio/stream" />
  </Connect>
</Response>
```

## Audio Format Conversion
- Twilio → Backend: mulaw 8kHz mono base64 → PCM 16kHz (for Deepgram)
- Kokoro → Twilio: PCM 24kHz → mulaw 8kHz mono base64

## Dependencies
```
fastapi uvicorn websockets twilio python-dotenv
audioop-lts numpy httpx
kokoro>=0.9.2
```

Plus vLLM running separately:
```
vllm serve Qwen/Qwen3-8B --gpu-memory-utilization 0.3
```

## ENV
```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
DEEPGRAM_API_KEY=
VLLM_BASE_URL=http://localhost:8000/v1
```

## Success Criteria
Call the Twilio number. Hear AI voice answer. Have a basic back-and-forth conversation. That's V0 done.
