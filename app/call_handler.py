"""Orchestrates a single call session: STT → LLM → TTS → Twilio."""

import asyncio
import base64
import json
import logging

from fastapi import WebSocket

from app.config import SYSTEM_PROMPT, MAX_HISTORY_EXCHANGES
from app.audio import mulaw_to_pcm16k, pcm24k_to_mulaw, numpy_to_pcm_bytes
from app.deepgram_client import DeepgramClient
from app.llm_client import stream_chat, strip_think_blocks
from app.tts_client import synthesize

logger = logging.getLogger(__name__)

# How many mulaw bytes to pack into each Twilio media message (~20ms at 8kHz)
TWILIO_CHUNK_SIZE = 160


class CallSession:
    """Manages one active phone call."""

    def __init__(self, twilio_ws: WebSocket):
        self.twilio_ws = twilio_ws
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.history: list[dict] = []
        self._response_task: asyncio.Task | None = None
        self._speaking = False
        self._mark_counter = 0

        self.deepgram = DeepgramClient(on_transcript=self._on_transcript)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialize Deepgram connection."""
        await self.deepgram.connect()

    async def stop(self) -> None:
        """Tear down everything."""
        if self._response_task and not self._response_task.done():
            self._response_task.cancel()
        await self.deepgram.close()

    # ------------------------------------------------------------------
    # Inbound audio from Twilio
    # ------------------------------------------------------------------

    async def handle_media(self, payload: str) -> None:
        """Process a base64-encoded mulaw audio chunk from Twilio."""
        mulaw_bytes = base64.b64decode(payload)
        pcm_16k = mulaw_to_pcm16k(mulaw_bytes)
        await self.deepgram.send_audio(pcm_16k)

    # ------------------------------------------------------------------
    # Transcript callback (from Deepgram)
    # ------------------------------------------------------------------

    async def _on_transcript(self, transcript: str) -> None:
        """Called when Deepgram produces a final transcript."""
        logger.info("User said: %s", transcript)

        # Barge-in: cancel any ongoing response
        if self._response_task and not self._response_task.done():
            logger.info("Barge-in detected, cancelling current response")
            self._response_task.cancel()
            await self._send_clear()
            self._speaking = False

        # Add to history and generate response
        self.history.append({"role": "user", "content": transcript})
        self._trim_history()
        self._response_task = asyncio.create_task(self._generate_response())

    # ------------------------------------------------------------------
    # Response pipeline: LLM → TTS → Twilio
    # ------------------------------------------------------------------

    async def _generate_response(self) -> None:
        """Collect full LLM response, synthesize TTS, send audio to Twilio."""
        try:
            # Build messages with system prompt
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history

            # Collect full LLM response (streaming but accumulating)
            full_text = ""
            async for token in stream_chat(messages):
                full_text += token

            # Clean up think blocks
            full_text = strip_think_blocks(full_text)
            if not full_text:
                return

            logger.info("LLM response: %s", full_text)
            self.history.append({"role": "assistant", "content": full_text})
            self._trim_history()

            # TTS
            audio_np = await synthesize(full_text)
            pcm_bytes = numpy_to_pcm_bytes(audio_np)
            mulaw_bytes = pcm24k_to_mulaw(pcm_bytes)

            # Send audio to Twilio in chunks
            self._speaking = True
            await self._send_audio_chunks(mulaw_bytes)
            self._speaking = False

        except asyncio.CancelledError:
            logger.info("Response generation cancelled (barge-in)")
        except Exception:
            logger.exception("Error generating response")

    # ------------------------------------------------------------------
    # Twilio outbound helpers
    # ------------------------------------------------------------------

    async def _send_audio_chunks(self, mulaw_bytes: bytes) -> None:
        """Send mulaw audio to Twilio as base64-encoded media messages."""
        offset = 0
        while offset < len(mulaw_bytes):
            chunk = mulaw_bytes[offset : offset + TWILIO_CHUNK_SIZE]
            offset += TWILIO_CHUNK_SIZE

            media_msg = {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": base64.b64encode(chunk).decode("ascii"),
                },
            }
            await self.twilio_ws.send_json(media_msg)

        # Send a mark so we know when playback finishes
        self._mark_counter += 1
        mark_msg = {
            "event": "mark",
            "streamSid": self.stream_sid,
            "mark": {"name": f"end-{self._mark_counter}"},
        }
        await self.twilio_ws.send_json(mark_msg)

    async def _send_clear(self) -> None:
        """Tell Twilio to stop playing any queued audio."""
        if self.stream_sid:
            clear_msg = {
                "event": "clear",
                "streamSid": self.stream_sid,
            }
            await self.twilio_ws.send_json(clear_msg)

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def _trim_history(self) -> None:
        """Keep only the last N exchanges (user+assistant pairs)."""
        max_messages = MAX_HISTORY_EXCHANGES * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]
