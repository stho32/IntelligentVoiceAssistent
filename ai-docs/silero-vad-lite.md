# silero-vad-lite API Reference (v0.2.1)

Lightweight VAD using ONNX Runtime (bundled). No PyTorch required. Zero Python dependencies.

## Installation

```bash
pip install silero-vad-lite
```

## Audio Format Requirements

| Property | Value |
|---|---|
| Sample Rate | 16,000 Hz (or 8,000 Hz) |
| Frame Size (16kHz) | 512 samples = 32 ms |
| Sample Format | float32, normalized [-1.0, 1.0] |
| Channels | Mono |

## SileroVAD Class

```python
from silero_vad_lite import SileroVAD
```

### Constructor

```python
vad = SileroVAD(sample_rate=16000)
```

### Properties

- `vad.sample_rate` -> int (8000 or 16000)
- `vad.window_size_samples` -> int (512 for 16kHz, 256 for 8kHz)

### process()

```python
speech_prob = vad.process(audio_data)
# Returns: float 0.0-1.0 (speech probability)
```

**Accepted input types:** `bytes`, `bytearray`, `memoryview`, `array.array('f', ...)`, `ctypes.Array`, `list`/`tuple` of floats.

**For numpy arrays:** Convert first:
```python
import array
data = array.array('f', np_float32_array.tobytes())
prob = vad.process(data)
```

### Reset State

No `reset()` method available. Create a new instance:
```python
vad = SileroVAD(16000)  # fresh state
```

## Converting from int16 PCM

```python
float_sample = int16_sample / 32768.0
```

## Streaming Example

```python
import array
from silero_vad_lite import SileroVAD

vad = SileroVAD(16000)
THRESHOLD = 0.5

while True:
    # Get 512 float32 samples
    audio_frame = array.array('f', get_audio_bytes())
    prob = vad.process(audio_frame)
    if prob >= THRESHOLD:
        print("Speech detected")
```
