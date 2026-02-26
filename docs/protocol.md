# Connection Protocol

## Connect Flow

The full sequence from client to voice conversation:

```
  Browser                     Server                      Daily.co API
     │                          │                              │
     │  POST /api/connect       │                              │
     │  { }                     │                              │
     │─────────────────────────►│                              │
     │                          │  POST /v1/rooms              │
     │                          │─────────────────────────────►│
     │                          │◄─────────────────────────────│
     │                          │  { url, name }               │
     │                          │                              │
     │                          │  POST /v1/meeting-tokens     │
     │                          │  (user token, is_owner=false)│
     │                          │─────────────────────────────►│
     │                          │◄─────────────────────────────│
     │                          │                              │
     │                          │  POST /v1/meeting-tokens     │
     │                          │  (bot token, is_owner=true)  │
     │                          │─────────────────────────────►│
     │                          │◄─────────────────────────────│
     │                          │                              │
     │                          │  spawn bot.py subprocess     │
     │                          │  env: DAILY_ROOM_URL,        │
     │                          │       DAILY_TOKEN (bot)      │
     │                          │                              │
     │  { url, token }          │                              │
     │◄─────────────────────────│                              │
     │                          │                              │
     │  Join Daily room         │         Daily Room           │
     │  with user token         │              │               │
     │─────────────────────────────────────────►               │
     │                          │              │               │
     │                          │  Bot joins   │               │
     │                          │  room with   │               │
     │                          │  bot token   │               │
     │                    bot.py│──────────────►               │
     │                          │              │               │
     │◄════════ WebRTC Audio + RTVI Messages ═══════════════►  │
```

## API Reference

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

### `POST /api/connect`

Create a voice session. This endpoint:
1. Creates a Daily.co room (expires in 1 hour)
2. Generates a user token (for the client) and a bot token (for the server)
3. Spawns a `bot.py` subprocess with the bot token
4. Returns the room URL and user token

**Request body:** empty JSON object `{}`

**Response:**
```json
{
  "url": "https://yourdomain.daily.co/RoomName",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Errors:**

| Status | Reason |
|--------|--------|
| 500 | `DAILY_API_KEY` not set in environment |
| 500 | Daily API returned error creating room |
| 500 | Failed to create meeting tokens |
| 500 | Failed to spawn bot subprocess |

## Pipecat React SDK Integration

The `/api/connect` response format is designed for the pipecat React SDK:

```typescript
import { PipecatClient } from "@pipecat-ai/client-js";
import { DailyTransport } from "@pipecat-ai/daily-transport";

const client = new PipecatClient({
  transport: new DailyTransport(),
  enableMic: true,
  enableCam: false,
});

// This calls POST /api/connect,
// gets { url, token },
// and joins the Daily room automatically
await client.startBotAndConnect({
  endpoint: "http://localhost:8000/api/connect",
  requestData: {},
});
```

The SDK expects exactly `{ url: string, token: string }` in the response.

## WebRTC Transport

Audio flows over WebRTC through Daily.co:

```
  Browser Microphone                          Bot Speaker
        │                                          ▲
        ▼                                          │
  ┌───────────┐                              ┌───────────┐
  │  Opus     │                              │  Opus     │
  │  Encode   │                              │  Decode   │
  └─────┬─────┘                              └─────┬─────┘
        │                                          ▲
        ▼              Daily.co                    │
  ┌─────────────────────────────────────────────────────┐
  │                  WebRTC Room                        │
  │                                                     │
  │   User audio track ──────► Bot receives audio      │
  │   User hears audio ◄────── Bot sends audio         │
  │                                                     │
  │   App messages (JSON) ◄──► App messages (JSON)     │
  └─────────────────────────────────────────────────────┘
        │                                          ▲
        ▼                                          │
  ┌───────────┐                              ┌───────────┐
  │  Bot      │                              │  Bot      │
  │  Receives │                              │  Sends    │
  │  PCM      │                              │  PCM      │
  └───────────┘                              └───────────┘
```

### Token Permissions

Two tokens are created per session with different permissions:

| Token | `is_owner` | Used by | Purpose |
|-------|-----------|---------|---------|
| User token | `false` | Browser client | Can send/receive audio, limited control |
| Bot token | `true` | Bot subprocess | Full room control, can eject participants |

### Room Lifecycle

1. Room created with 1-hour expiry
2. Bot subprocess joins immediately
3. Client joins after receiving `{ url, token }`
4. When client leaves, bot detects `on_participant_left` and shuts down
5. Room auto-expires after 1 hour even if participants remain

## Environment Variables

The bot subprocess inherits all server environment variables plus session-specific ones:

```
Inherited from server .env:
  OPENAI_API_KEY          → Used by OpenAI LLM service
  ELEVENLABS_API_KEY      → Used by ElevenLabs STT and TTS
  ELEVENLABS_VOICE_ID     → Voice for TTS output

Set per-session by server:
  DAILY_ROOM_URL          → Room URL for this session
  DAILY_TOKEN             → Bot token for this session
```

## Audio Latency Budget

Typical end-to-end latency for a voice exchange:

```
  User speaks          0ms
       │
       ▼
  WebRTC transit     ~80ms
       │
       ▼
  VAD detection     ~200ms  (waits for speech end)
       │
       ▼
  STT processing    ~500ms  (ElevenLabs transcription)
       │
       ▼
  LLM generation   ~800ms  (time-to-first-token, gpt-5-mini)
       │
       ▼
  TTS synthesis     ~300ms  (ElevenLabs streaming, first chunk)
       │
       ▼
  WebRTC transit     ~80ms
       │
       ▼
  User hears bot   ~2000ms  total (first audio chunk)
```

TTS and LLM both stream, so the user hears the first words before the full response is generated. The LLM streams text tokens to TTS, which streams audio chunks to WebRTC in real time.
