# OpenAI Text-to-Speech API Reference

## Endpoint

`POST /v1/audio/speech`

## Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | str | Yes | `"tts-1"` (fast) or `"tts-1-hd"` (quality) |
| `voice` | str | Yes | `"alloy"`, `"echo"`, `"fable"`, `"nova"`, `"onyx"`, `"shimmer"` |
| `input` | str | Yes | Text to speak. Max 4096 chars. |
| `response_format` | str | No | `"mp3"` (default), `"pcm"`, `"wav"`, `"opus"`, `"aac"`, `"flac"` |
| `speed` | float | No | 0.25-4.0, default 1.0 |

## PCM Format

When `response_format="pcm"`:
- **Sample rate:** 24,000 Hz
- **Bit depth:** 16-bit signed integer (little-endian)
- **Channels:** Mono
- **No header** (raw samples)

## PCM Streaming (Low Latency)

```python
import pyaudio
from openai import OpenAI

client = OpenAI()
pa = pyaudio.PyAudio()
player = pa.open(format=pyaudio.paInt16, channels=1, rate=24000, output=True)

with client.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="nova",
    input="Hallo, wie kann ich helfen?",
    response_format="pcm",
) as response:
    for chunk in response.iter_bytes(chunk_size=1024):
        player.write(chunk)

player.stop_stream()
player.close()
```

## Non-Streaming

```python
response = client.audio.speech.create(
    model="tts-1",
    voice="onyx",
    input="Hello world",
    response_format="mp3",
)
response.stream_to_file("output.mp3")
```

## Streaming Response Methods

Inside `with_streaming_response` context:
- `response.iter_bytes(chunk_size=1024)` - iterate raw byte chunks
- `response.read()` - read entire body
- `response.stream_to_file(path)` - stream to file
