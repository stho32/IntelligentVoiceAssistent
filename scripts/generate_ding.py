"""Generate a confirmation ding sound (880Hz sine wave, 200ms).

Creates a short, pleasant WAV file for the wake-word confirmation tone.
"""

import math
import struct
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).parent.parent / "sprachassistent" / "audio" / "sounds"

SAMPLE_RATE = 16000
DURATION_SEC = 0.2
FREQUENCY = 880  # A5 note
AMPLITUDE = 0.5


def generate_ding() -> None:
    """Generate the ding.wav confirmation sound."""
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SOUNDS_DIR / "ding.wav"

    n_samples = int(SAMPLE_RATE * DURATION_SEC)
    samples = []

    for i in range(n_samples):
        t = i / SAMPLE_RATE
        # Sine wave with linear fade-out for a clean sound
        fade = 1.0 - (i / n_samples)
        value = AMPLITUDE * fade * math.sin(2 * math.pi * FREQUENCY * t)
        # Convert to int16
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
    generate_ding()
