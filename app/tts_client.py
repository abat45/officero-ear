"""Kokoro TTS wrapper — runs synthesis in a thread executor."""

import asyncio
import logging

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded pipeline
_pipeline = None


def _get_pipeline():
    """Initialize Kokoro pipeline on first use."""
    global _pipeline
    if _pipeline is None:
        from kokoro import KPipeline
        logger.info("Loading Kokoro TTS pipeline...")
        _pipeline = KPipeline(lang_code="a")  # American English
        logger.info("Kokoro TTS pipeline loaded")
    return _pipeline


def _synthesize_sync(text: str) -> np.ndarray:
    """Run Kokoro TTS synchronously. Returns float32 audio at 24kHz."""
    pipeline = _get_pipeline()
    # Kokoro returns a generator of (graphemes, phonemes, audio) tuples
    chunks = []
    for _, _, audio in pipeline(text):
        chunks.append(audio)

    if not chunks:
        return np.array([], dtype=np.float32)

    return np.concatenate(chunks)


async def synthesize(text: str) -> np.ndarray:
    """Async wrapper — runs TTS in a thread executor to avoid blocking."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _synthesize_sync, text)
