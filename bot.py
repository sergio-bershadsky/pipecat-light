#!/usr/bin/env python3
"""Bot process - runs the pipecat pipeline for a single tutoring session.

Spawned as a subprocess by the FastAPI server for each voice session.
"""

import asyncio
import logging
import os
import sys

import aiohttp
from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.elevenlabs.stt import ElevenLabsSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot")

# ── Hardcoded lesson: Russian greetings ──────────────────────────────────────

SYSTEM_PROMPT = """\
You are a friendly and encouraging Russian language tutor named Anya.

## Current Lesson: Basic Greetings

Teach the student these Russian greetings through natural conversation:

1. Привет (Privet) - Hi / Hello (informal)
2. Здравствуйте (Zdravstvuyte) - Hello (formal)
3. Как дела? (Kak dela?) - How are you?
4. Хорошо, спасибо (Khorosho, spasibo) - Good, thank you
5. Меня зовут... (Menya zovut...) - My name is...
6. Очень приятно (Ochen' priyatno) - Nice to meet you
7. До свидания (Do svidaniya) - Goodbye
8. Пока (Poka) - Bye (informal)

## Instructions

- Speak primarily in English, introducing Russian phrases one at a time
- After introducing a phrase, ask the student to repeat it
- Give gentle pronunciation tips using transliteration
- Be patient and encouraging - celebrate small wins
- Keep responses concise (2-3 sentences max) since this is a voice conversation
- Start by greeting the student and introducing yourself
- Progress naturally through the phrases based on the student's pace
"""


async def run_bot():
    room_url = os.getenv("DAILY_ROOM_URL")
    token = os.getenv("DAILY_TOKEN")
    if not room_url or not token:
        logger.error("DAILY_ROOM_URL and DAILY_TOKEN must be set")
        sys.exit(1)

    transport = DailyTransport(
        room_url,
        token,
        "Anya",
        DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=None,  # use default Silero
            vad_audio_passthrough=True,
        ),
    )

    aiohttp_session = aiohttp.ClientSession()

    stt = ElevenLabsSTTService(
        api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        aiohttp_session=aiohttp_session,
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model="gpt-5-mini",
    )

    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY", ""),
        voice_id=os.getenv("ELEVENLABS_VOICE_ID", ""),
    )

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True, enable_metrics=True),
    )

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        logger.info(f"Participant joined: {participant['id']}")
        await task.queue_frames([])

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        logger.info(f"Participant left: {participant['id']}, reason: {reason}")
        await task.cancel()

    runner = PipelineRunner()
    try:
        await runner.run(task)
    finally:
        await aiohttp_session.close()


def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot interrupted")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
