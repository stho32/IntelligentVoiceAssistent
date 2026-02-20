# OpenWakeWord API Reference (v0.6.0)

## Installation

```bash
pip install openwakeword
# For ONNX-only (no tflite): just set inference_framework="onnx"
```

## Audio Format Requirements

| Property | Value |
|---|---|
| Sample Rate | 16,000 Hz |
| dtype | `np.int16` (16-bit PCM) |
| Channels | Mono |
| Frame Size | 1280 samples = 80 ms |

## Model Class

```python
from openwakeword.model import Model
```

### Constructor

```python
Model(
    wakeword_models: list[str] = [],       # paths to .onnx files or pretrained names
    inference_framework: str = "onnx",      # "onnx" or "tflite"
    enable_speex_noise_suppression: bool = False,
    vad_threshold: float = 0,               # 0 = disabled
)
```

### Loading Custom ONNX Models

```python
model = Model(
    wakeword_models=["/path/to/computer_v2.onnx"],
    inference_framework="onnx"
)
```

Model name derived from filename without extension (e.g., `computer_v2`).

### predict()

```python
predictions = model.predict(
    x: np.ndarray,          # int16, optimal 1280 samples
    threshold: dict = {},    # e.g. {"computer_v2": 0.5}
    debounce_time: float = 0.0,
)
# Returns: dict[str, float] - model_name -> score (0.0-1.0)
```

- Larger arrays processed as multiple windows (max score returned)
- Scores appended to `model.prediction_buffer[model_name]` (deque, maxlen=30)

### reset()

```python
model.reset()  # Clears prediction history and audio feature buffers
```

Call after wake word detected to prepare for next detection cycle.

## Complete Example

```python
import numpy as np
from openwakeword.model import Model

model = Model(
    wakeword_models=["models/computer_v2.onnx"],
    inference_framework="onnx"
)

CHUNK = 1280  # 80ms at 16kHz
while True:
    audio_frame = np.frombuffer(stream.read(CHUNK), dtype=np.int16)
    predictions = model.predict(audio_frame)
    if predictions["computer_v2"] > 0.5:
        print("Wake word detected!")
        model.reset()
```
