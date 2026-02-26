"""FastAPI server for starpipe-simple.

Spawns a bot subprocess per voice session using Daily.co for WebRTC.
"""

import logging
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("server")

PROJECT_ROOT = Path(__file__).parent


class ConnectRequest(BaseModel):
    pass


app = FastAPI(title="starpipe-simple")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track active bot subprocesses
active_sessions: dict[str, dict] = {}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/api/connect")
async def connect(request: ConnectRequest):
    """Create a Daily room, spawn bot subprocess, return room URL + user token."""
    api_key = os.getenv("DAILY_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY not configured")

    session_id = str(uuid.uuid4())
    expiry = int(time.time()) + 3600

    async with httpx.AsyncClient() as client:
        # Create room
        room_resp = await client.post(
            "https://api.daily.co/v1/rooms",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "properties": {
                    "exp": expiry,
                    "enable_chat": False,
                    "start_video_off": True,
                    "start_audio_off": False,
                }
            },
        )
        if room_resp.status_code != 200:
            logger.error(f"Failed to create room: {room_resp.text}")
            raise HTTPException(status_code=500, detail="Failed to create Daily room")

        room_data = room_resp.json()
        room_url = room_data["url"]
        room_name = room_data["name"]

        # User token (for frontend)
        user_token_resp = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "properties": {
                    "room_name": room_name,
                    "exp": expiry,
                    "is_owner": False,
                    "user_name": "Student",
                }
            },
        )
        if user_token_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to create user token")
        user_token = user_token_resp.json()["token"]

        # Bot token
        bot_token_resp = await client.post(
            "https://api.daily.co/v1/meeting-tokens",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "properties": {
                    "room_name": room_name,
                    "exp": expiry,
                    "is_owner": True,
                    "user_name": "Anya Bot",
                }
            },
        )
        if bot_token_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to create bot token")
        bot_token = bot_token_resp.json()["token"]

    # Spawn bot subprocess
    bot_env = os.environ.copy()
    bot_env.update({
        "DAILY_ROOM_URL": room_url,
        "DAILY_TOKEN": bot_token,
    })

    try:
        bot_process = subprocess.Popen(
            [sys.executable, "-u", str(PROJECT_ROOT / "bot.py")],
            env=bot_env,
            stdout=None,
            stderr=None,
        )
        active_sessions[session_id] = {
            "process": bot_process,
            "room_name": room_name,
        }
        logger.info(f"Started bot for session {session_id}, room {room_name}, pid {bot_process.pid}")
    except Exception as e:
        logger.error(f"Failed to spawn bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"url": room_url, "token": user_token}


@app.get("/")
async def index():
    return FileResponse(PROJECT_ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")
