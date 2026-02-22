"""Audio format conversion utilities for the Twilio ↔ Deepgram ↔ Kokoro pipeline."""

import audioop
import numpy as np

from app.config import (
    TWILIO_SAMPLE_RATE,
    DEEPGRAM_SAMPLE_RATE,
    KOKORO_SAMPLE_RATE,
    MULAW_SAMPLE_WIDTH,
    PCM_SAMPLE_WIDTH,
)


def mulaw_to_pcm16k(mulaw_bytes: bytes) -> bytes:
    """Convert mulaw 8kHz (from Twilio) → PCM 16-bit 16kHz (for Deepgram)."""
    # mulaw → linear PCM 16-bit
    pcm_8k = audioop.ulaw2lin(mulaw_bytes, PCM_SAMPLE_WIDTH)
    # resample 8kHz → 16kHz
    pcm_16k, _ = audioop.ratecv(
        pcm_8k, PCM_SAMPLE_WIDTH, 1,
        TWILIO_SAMPLE_RATE, DEEPGRAM_SAMPLE_RATE,
        None,
    )
    return pcm_16k


def pcm24k_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Convert PCM 16-bit 24kHz (from Kokoro) → mulaw 8kHz (for Twilio)."""
    # resample 24kHz → 8kHz
    pcm_8k, _ = audioop.ratecv(
        pcm_bytes, PCM_SAMPLE_WIDTH, 1,
        KOKORO_SAMPLE_RATE, TWILIO_SAMPLE_RATE,
        None,
    )
    # linear PCM → mulaw
    return audioop.lin2ulaw(pcm_8k, PCM_SAMPLE_WIDTH)


def numpy_to_pcm_bytes(audio: np.ndarray) -> bytes:
    """Convert Kokoro float32 numpy array → PCM 16-bit bytes."""
    # Clip and scale float32 [-1, 1] → int16
    audio = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (audio * 32767).astype(np.int16)
    return pcm_int16.tobytes()
