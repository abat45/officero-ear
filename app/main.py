"""FastAPI entry point: TwiML webhook + Twilio Media Stream WebSocket."""

import json
import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response

from app.call_handler import CallSession

PUBLIC_HOST = os.getenv("PUBLIC_HOST", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Officero EAR V0")


@app.post("/twilio/incoming")
async def twilio_incoming(request: Request):
    """Return TwiML that tells Twilio to open a media stream WebSocket."""
    # Use PUBLIC_HOST env var, or fall back to X-Forwarded-Host, then Host header
    host = PUBLIC_HOST or request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost:8080")
    ws_url = f"wss://{host}/twilio/stream"
    logger.info("TwiML stream URL: %s", ws_url)

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{ws_url}" />'
        "</Connect>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.websocket("/twilio/stream")
async def twilio_stream(ws: WebSocket):
    """Handle the Twilio Media Stream WebSocket for one call."""
    await ws.accept()
    session = CallSession(ws)
    logger.info("Twilio WebSocket connected")

    try:
        await session.start()

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "connected":
                logger.info("Twilio stream connected")

            elif event == "start":
                session.stream_sid = msg["start"]["streamSid"]
                session.call_sid = msg["start"]["callSid"]
                logger.info(
                    "Stream started — stream_sid=%s call_sid=%s",
                    session.stream_sid,
                    session.call_sid,
                )

            elif event == "media":
                payload = msg["media"]["payload"]
                await session.handle_media(payload)

            elif event == "mark":
                logger.debug("Mark received: %s", msg["mark"]["name"])

            elif event == "stop":
                logger.info("Twilio stream stopped")
                break

    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")
    except Exception:
        logger.exception("Error in Twilio stream handler")
    finally:
        await session.stop()
        logger.info("Call session cleaned up")
