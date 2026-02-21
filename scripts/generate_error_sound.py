"""Generate an error notification sound (descending two-tone, ~350ms).

Creates a short, distinctive error sound for TTS fallback notification.
"""

import math
import struct
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).parent.parent / "sprachassistent" / "audio" / "sounds"

SAMPLE_RATE = 16000
AMPLITUDE = 0.4

# Descending two-tone: E4 (330Hz) -> A3 (220Hz)
TONES = [
    (330, 0.15),  # frequency Hz, duration seconds
    (220, 0.20),
]


def generate_error_sound() -> None:
    """Generate the error.wav notification sound."""
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = SOUNDS_DIR / "error.wav"

    samples = []
    for freq, duration in TONES:
        n_samples = int(SAMPLE_RATE * duration)
        for i in range(n_samples):
            t = i / SAMPLE_RATE
            fade_in = min(1.0, i / (n_samples * 0.1))
            fade_out = min(1.0, (n_samples - i) / (n_samples * 0.2))
            fade = fade_in * fade_out
            value = AMPLITUDE * fade * math.sin(2 * math.pi * freq * t)
            sample = int(value * 32767)
            sample = max(-32768, min(32767, sample))
            samples.append(struct.pack("<h", sample))

    with wave.open(str(output_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b"".join(samples))

    total_duration = sum(d for _, d in TONES)
    print(f"Generated: {output_path} ({len(samples)} samples, {total_duration}s)")


if __name__ == "__main__":
    generate_error_sound()
