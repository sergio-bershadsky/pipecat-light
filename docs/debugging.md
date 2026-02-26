# Debugging

## Quick Test: Daily Prebuilt

The fastest way to test without building a frontend. After starting the server:

```bash
# 1. Start server
make dev

# 2. Create a session
curl -s -X POST http://localhost:8000/api/connect \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
```

This returns:
```json
{
  "url": "https://yourdomain.daily.co/RoomName",
  "token": "eyJ..."
}
```

Open the `url` in your browser. Daily's prebuilt UI will let you join with your microphone and talk to the bot. No frontend code needed.

> **Note:** The prebuilt page doesn't use the token — it joins as a guest. This works because the room doesn't require authentication by default. For token-based join, use the pipecat SDK or Daily's JavaScript SDK.

## Daily Prebuilt with Token

To join with the exact token (matches production behavior):

```
https://yourdomain.daily.co/RoomName?t=YOUR_TOKEN_HERE
```

Replace `YOUR_TOKEN_HERE` with the `token` value from the `/api/connect` response.

## Debug with a Minimal HTML Page

Save this as `debug.html` and open in a browser:

```html
<!DOCTYPE html>
<html>
<head><title>Pipecat Debug</title></head>
<body>
  <button id="start">Start Session</button>
  <button id="stop" disabled>Stop</button>
  <pre id="log"></pre>

  <script src="https://unpkg.com/@daily-co/daily-js"></script>
  <script>
    const log = (msg) => {
      document.getElementById('log').textContent += msg + '\n';
      console.log(msg);
    };

    let callFrame;

    document.getElementById('start').onclick = async () => {
      log('Connecting...');
      const resp = await fetch('http://localhost:8000/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      const { url, token } = await resp.json();
      log(`Room: ${url}`);

      callFrame = window.DailyIframe.createCallObject();

      callFrame.on('joined-meeting', () => log('Joined room'));
      callFrame.on('participant-joined', (e) => log(`Participant joined: ${e.participant.user_name}`));
      callFrame.on('participant-left', (e) => log(`Participant left: ${e.participant.user_name}`));
      callFrame.on('app-message', (e) => log(`Message: ${JSON.stringify(e.data)}`));
      callFrame.on('error', (e) => log(`Error: ${JSON.stringify(e)}`));

      await callFrame.join({ url, token });
      log('Connected - speak into your microphone');

      document.getElementById('start').disabled = true;
      document.getElementById('stop').disabled = false;
    };

    document.getElementById('stop').onclick = async () => {
      if (callFrame) {
        await callFrame.leave();
        callFrame.destroy();
        log('Disconnected');
      }
      document.getElementById('start').disabled = false;
      document.getElementById('stop').disabled = true;
    };
  </script>
</body>
</html>
```

Open this file directly in your browser (or serve it). Click "Start Session" — it will:
1. Call `/api/connect` to create a room
2. Join with your microphone
3. Log all events (participant joins, app messages, errors)

## Bot Process Debugging

### Run bot standalone

```bash
# Set env vars for an existing room
export DAILY_ROOM_URL=https://yourdomain.daily.co/RoomName
export DAILY_TOKEN=eyJ...

# Run bot directly (not via server)
make bot
```

### Verbose logging

Set `LOG_LEVEL=DEBUG` in your `.env` or when running:

```bash
LOG_LEVEL=DEBUG make bot
```

### Watch bot subprocess output

When using `make dev`, bot subprocess output goes to the same terminal. Look for lines prefixed with the bot logger:

```
13:33:54 | INFO     | bot | Participant joined: abc123
13:33:55 | INFO     | pipecat | Pipeline running
```

## Common Issues

### Bot spawns but no audio

- Check that `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` are set in `.env`
- Check that `OPENAI_API_KEY` is set and has credits
- Make sure your browser has microphone permission

### "Failed to create Daily room"

- Verify `DAILY_API_KEY` is correct
- Check Daily.co dashboard for quota/billing

### Bot exits immediately

- Look at the terminal output for Python errors
- Common: missing dependencies (`make install`)
- Common: invalid API keys

### No STT transcription

- ElevenLabs STT requires a valid API key
- Check that your microphone is working (browser mic test)
- VAD may not be detecting speech — try speaking louder/closer

### High latency

Normal end-to-end is ~2 seconds. If much higher:
- Check your internet connection
- Try a different ElevenLabs voice (some are faster)
- `gpt-5-mini` is fast; if using a different model, latency will vary
