# OpenAI Whisper Transcription API Reference

## Endpoint

`POST /v1/audio/transcriptions`

## Usage

```python
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY env var

result = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    language="de",
)
print(result.text)
```

## Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `model` | str | Yes | `"whisper-1"` |
| `file` | FileTypes | Yes | Audio file. Max 25 MB. |
| `language` | str | No | ISO-639-1 code (e.g., `"de"`, `"en"`) |
| `response_format` | str | No | `"json"` (default), `"text"`, `"verbose_json"`, `"srt"`, `"vtt"` |
| `prompt` | str | No | Guide transcription style |
| `temperature` | float | No | 0-1, default 0 |

## Supported Audio Formats

`flac`, `mp3`, `mp4`, `mpeg`, `mpga`, `m4a`, `ogg`, `wav`, `webm`

## Passing Audio Data

### File path
```python
result = client.audio.transcriptions.create(
    model="whisper-1",
    file=Path("recording.wav"),
)
```

### File object
```python
with open("recording.wav", "rb") as f:
    result = client.audio.transcriptions.create(model="whisper-1", file=f)
```

### In-memory BytesIO (must set .name)
```python
import io

buffer = io.BytesIO(wav_bytes)
buffer.name = "audio.wav"  # Required! SDK uses extension
result = client.audio.transcriptions.create(model="whisper-1", file=buffer)
```

### Tuple form
```python
result = client.audio.transcriptions.create(
    model="whisper-1",
    file=("audio.wav", raw_bytes, "audio/wav"),
)
```

## Return Type

- Default (`"json"`): `Transcription` object with `.text` attribute
- `"text"`: plain string
- `"verbose_json"`: `TranscriptionVerbose` with `.text`, `.language`, `.duration`, `.segments`
