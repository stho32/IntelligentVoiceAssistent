"""Generate a thinking beep sound (440Hz sine wave, 100ms, soft).

Creates a short, gentle beep for periodic playback while the AI is processing.
Lower pitch and shorter than the confirmation ding to be unobtrusive.
"""

import math
import struct
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).parent.parent / "sprachassistent" / "audio" / "sounds"

SAMPLE_RATE = 16000
DURATION_SEC = 0.1
FREQUENCY = 440  # A4 note (lower than ding's A5)
AMPLITUDE = 0.25  # Softer than ding


def generate_thinking_beep() -> None:
    """Generate the thinking.wav beep sound."""
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SOUNDS_DIR / "thinking.wav"

    n_samples = int(SAMPLE_RATE * DURATION_SEC)
    samples = []

    for i in range(n_samples):
        t = i / SAMPLE_RATE
        # Sine wave with fade-in and fade-out for a soft beep
        fade_in = min(1.0, i / (n_samples * 0.2))
        fade_out = min(1.0, (n_samples - i) / (n_samples * 0.3))
        fade = fade_in * fade_out
        value = AMPLITUDE * fade * math.sin(2 * math.pi * FREQUENCY * t)
        sample = int(value * 32767)
        sample = max(-32768, min(32767, sample))
        samples.append(struct.pack("<h", sample))

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(samples))

    print(f"Generated: {output_path} ({n_samples} samples, {DURATION_SEC}s)")


if __name__ == "__main__":
    generate_thinking_beep()
