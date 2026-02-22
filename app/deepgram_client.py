"""Streaming STT via Deepgram Nova-3 WebSocket."""

import asyncio
import json
import logging
from typing import Callable, Awaitable

import websockets

from app.config import DEEPGRAM_API_KEY, DEEPGRAM_WS_URL, DEEPGRAM_KEEPALIVE_INTERVAL

logger = logging.getLogger(__name__)

# Callback type: async fn(transcript: str) -> None
TranscriptCallback = Callable[[str], Awaitable[None]]


class DeepgramClient:
    """Manages a single Deepgram streaming WebSocket connection."""

    def __init__(self, on_transcript: TranscriptCallback):
        self.on_transcript = on_transcript
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._keepalive_task: asyncio.Task | None = None
        self._receive_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Open WebSocket to Deepgram and start background tasks."""
        headers = {"Authorization": f"Token {DEEPGRAM_API_KEY}"}
        self._ws = await websockets.connect(
            DEEPGRAM_WS_URL,
            additional_headers=headers,
        )
        logger.info("Deepgram WebSocket connected")
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send PCM audio bytes to Deepgram."""
        if self._ws and self._ws.open:
            await self._ws.send(pcm_bytes)

    async def close(self) -> None:
        """Gracefully shut down the connection."""
        if self._keepalive_task:
            self._keepalive_task.cancel()
        if self._receive_task:
            self._receive_task.cancel()
        if self._ws and self._ws.open:
            # Send close-stream message
            await self._ws.send(json.dumps({"type": "CloseStream"}))
            await self._ws.close()
        logger.info("Deepgram WebSocket closed")

    async def _keepalive_loop(self) -> None:
        """Send KeepAlive every N seconds to prevent disconnect."""
        try:
            while True:
                await asyncio.sleep(DEEPGRAM_KEEPALIVE_INTERVAL)
                if self._ws and self._ws.open:
                    await self._ws.send(json.dumps({"type": "KeepAlive"}))
        except asyncio.CancelledError:
            pass

    async def _receive_loop(self) -> None:
        """Listen for transcription results from Deepgram."""
        try:
            async for message in self._ws:
                data = json.loads(message)

                if data.get("type") == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if not alternatives:
                        continue

                    transcript = alternatives[0].get("transcript", "").strip()
                    is_final = data.get("is_final", False)

                    if is_final and transcript:
                        logger.info("Deepgram transcript: %s", transcript)
                        await self.on_transcript(transcript)

        except websockets.ConnectionClosed:
            logger.info("Deepgram WebSocket connection closed")
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Error in Deepgram receive loop")
