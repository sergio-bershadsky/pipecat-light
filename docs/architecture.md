# Architecture

## Overview

pipecat-light is a minimal voice AI server built on [Pipecat](https://github.com/pipecat-ai/pipecat). It runs a **subprocess-per-session** model: the FastAPI server handles HTTP requests and spawns an isolated bot process for each voice conversation.

```
                         ┌──────────────────────────────┐
                         │        FastAPI Server         │
                         │         (server.py)           │
                         │                               │
  Browser ──POST──────►  │  /api/connect                 │
                         │    1. Create Daily room       │
                         │    2. Generate tokens         │
                         │    3. Spawn bot subprocess    │
                         │                               │
                         │  Returns { url, token }       │
                         └──────────┬───────────────────┘
                                    │
                                    │ subprocess.Popen
                                    ▼
                         ┌──────────────────────────────┐
                         │       Bot Process             │
                         │        (bot.py)               │
                         │                               │
                         │  Pipecat Pipeline:            │
                         │  transport.input()            │
                         │       ↓                       │
                         │  ElevenLabs STT               │
                         │       ↓                       │
                         │  context_aggregator.user()    │
                         │       ↓                       │
                         │  OpenAI LLM (gpt-5-mini)     │
                         │       ↓                       │
                         │  ElevenLabs TTS               │
                         │       ↓                       │
                         │  transport.output()           │
                         │       ↓                       │
                         │  context_aggregator.assistant()│
                         └──────────────────────────────┘
```

## Process Model

Each voice session runs in its own Python process. This provides:

- **Isolation** — a crash in one session doesn't affect others
- **Simplicity** — no shared state, no async coordination between sessions
- **Scaling** — each process holds one WebRTC connection, one LLM context

```
  server.py (FastAPI)
       │
       ├── bot.py  (session A, pid 1234)
       ├── bot.py  (session B, pid 1235)
       └── bot.py  (session C, pid 1236)
```

The server tracks active sessions by `session_id → { process, room_name }` and can terminate them on demand.

## Pipeline Detail

Pipecat processes audio as a chain of **frames** flowing through **processors**:

```
  ┌─────────────────────────────────────────────────────────────┐
  │                     Pipecat Pipeline                        │
  │                                                             │
  │  ┌──────────────┐    User audio (PCM)                      │
  │  │  transport    │──────────────────────►┌──────────────┐   │
  │  │  .input()     │                       │ ElevenLabs   │   │
  │  │              │                       │ STT          │   │
  │  │  Daily WebRTC │◄──────────────────────│              │   │
  │  │  .output()    │    Bot audio (PCM)    └──────┬───────┘   │
  │  └──────────────┘                               │           │
  │                                      TranscriptionFrame     │
  │                                                 │           │
  │                                      ┌──────────▼───────┐   │
  │                                      │ context_agg      │   │
  │                                      │ .user()          │   │
  │                                      │ (appends to      │   │
  │                                      │  conversation)   │   │
  │                                      └──────────┬───────┘   │
  │                                                 │           │
  │                                      ┌──────────▼───────┐   │
  │                                      │ OpenAI LLM       │   │
  │                                      │ gpt-5-mini       │   │
  │                                      │ (streaming)      │   │
  │                                      └──────────┬───────┘   │
  │                                                 │           │
  │                                      ┌──────────▼───────┐   │
  │                                      │ ElevenLabs       │   │
  │                                      │ TTS              │   │
  │                                      │ (streaming)      │   │
  │                                      └──────────┬───────┘   │
  │                                                 │           │
  │                                      ┌──────────▼───────┐   │
  │                                      │ transport        │   │
  │                                      │ .output()        │   │
  │                                      └──────────┬───────┘   │
  │                                                 │           │
  │                                      ┌──────────▼───────┐   │
  │                                      │ context_agg      │   │
  │                                      │ .assistant()     │   │
  │                                      │ (saves bot reply │   │
  │                                      │  to context)     │   │
  │                                      └──────────────────┘   │
  └─────────────────────────────────────────────────────────────┘
```

### Frame Types

| Frame | Direction | Description |
|-------|-----------|-------------|
| `InputAudioRawFrame` | Downstream | Raw PCM audio from user microphone |
| `TranscriptionFrame` | Downstream | Text from STT (interim or final) |
| `LLMFullResponseStartFrame` | Downstream | LLM begins generating |
| `TextFrame` | Downstream | Chunks of LLM text output |
| `TTSAudioRawFrame` | Downstream | Synthesized speech audio |
| `OutputAudioRawFrame` | Downstream | Audio sent to WebRTC |
| `UserStartedSpeakingFrame` | Downstream | VAD detected speech start |
| `UserStoppedSpeakingFrame` | Downstream | VAD detected speech end |

### Interruption Handling

The pipeline runs with `allow_interruptions=True`. When the user starts speaking while the bot is talking:

1. VAD detects user speech → `UserStartedSpeakingFrame`
2. Pipeline cancels in-progress TTS audio
3. LLM generation is cancelled
4. STT begins processing the new user utterance
5. Pipeline restarts from the new user input

## Voice Activity Detection (VAD)

VAD is handled by Daily's built-in Silero model, configured through `DailyParams`:

```python
DailyParams(
    vad_enabled=True,
    vad_analyzer=None,          # default Silero
    vad_audio_passthrough=True, # forward audio after VAD
)
```

The VAD determines when the user has finished speaking before sending audio to STT. This prevents partial utterances from triggering LLM responses.
