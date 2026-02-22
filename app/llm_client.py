"""Streaming chat completions via vLLM OpenAI-compatible API."""

import json
import re
import logging
from typing import AsyncGenerator

import httpx

from app.config import VLLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

# Regex to strip <think>...</think> blocks from Qwen3 output
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


async def stream_chat(
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream text tokens from vLLM. Yields cleaned text chunks."""
    url = f"{VLLM_BASE_URL}/chat/completions"
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": 256,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break

                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    yield content


def strip_think_blocks(text: str) -> str:
    """Remove any <think>...</think> blocks from LLM output."""
    return _THINK_RE.sub("", text).strip()
