# Quickstart

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- API keys for: [Daily.co](https://www.daily.co/), [OpenAI](https://platform.openai.com/), [ElevenLabs](https://elevenlabs.io/)

## Setup

```bash
# Clone
git clone git@github.com:sergio-bershadsky/pipecat-light.git
cd pipecat-light

# Create virtual environment and install
uv venv
make install

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DAILY_API_KEY` | Yes | Daily.co API key for room creation |
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM (gpt-5-mini) |
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs API key for STT and TTS |
| `ELEVENLABS_VOICE_ID` | Yes | ElevenLabs voice ID for TTS output |

## Run

```bash
make dev
```

Server starts on `http://localhost:8000`.

## Test

```bash
# Health check
curl http://localhost:8000/health

# Create a voice session (returns Daily room URL + token)
curl -X POST http://localhost:8000/api/connect \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Connect a Client

Use the [pipecat React SDK](https://github.com/pipecat-ai/pipecat-client-web):

```typescript
import { PipecatClient } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";

const client = new PipecatClient({
  transport: new DailyTransport(),
  enableMic: true,
  enableCam: false,
});

await client.startBotAndConnect({
  endpoint: "http://localhost:8000/api/connect",
});
```

Or join the Daily room directly using the URL and token from the `/api/connect` response.

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make install` | Install dependencies |
| `make dev` | Start server with hot reload |
| `make bot` | Run bot.py standalone (needs `DAILY_ROOM_URL` and `DAILY_TOKEN`) |
| `make kill` | Kill process on port 8000 |
| `make lint` | Check code with ruff |
| `make format` | Auto-format code with ruff |
| `make clean` | Remove cache files |

## Project Structure

```
pipecat-light/
├── server.py       FastAPI server, /api/connect endpoint
├── bot.py          Pipecat pipeline (STT → LLM → TTS)
├── Makefile        Dev commands
├── pyproject.toml  Dependencies
├── .env.example    Environment template
├── .env            Your API keys (git-ignored)
└── docs/
    ├── quickstart.md       This file
    ├── architecture.md     System design and pipeline details
    └── protocol.md         Connection protocol and API reference
```
