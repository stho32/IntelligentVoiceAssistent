"""Download required ONNX models for the voice assistant.

Downloads:
- computer_v2.onnx wake-word model from the community collection
- OpenWakeWord embedding models (melspectrogram + embedding)
"""

from pathlib import Path

import requests
from tqdm import tqdm

MODELS_DIR = Path(__file__).parent.parent / "models"

MODELS = {
    "computer_v2.onnx": (
        "https://huggingface.co/fwartner/home-assistant-wakewords-collection/"
        "resolve/main/models/computer_v2.onnx"
    ),
    "melspectrogram.onnx": (
        "https://github.com/dscripka/openWakeWord/raw/main/openwakeword/"
        "resources/models/melspectrogram.onnx"
    ),
    "embedding_model.onnx": (
        "https://github.com/dscripka/openWakeWord/raw/main/openwakeword/"
        "resources/models/embedding_model.onnx"
    ),
}


def download_file(url: str, dest: Path) -> None:
    """Download a file with progress bar."""
    if dest.exists():
        print(f"  Already exists: {dest.name}")
        return

    print(f"  Downloading: {dest.name}")
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    total = int(response.headers.get("content-length", 0))
    with open(dest, "wb") as f, tqdm(total=total, unit="B", unit_scale=True) as bar:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))


def main() -> None:
    """Download all required models."""
    MODELS_DIR.mkdir(exist_ok=True)
    print(f"Downloading models to {MODELS_DIR}/\n")

    for filename, url in MODELS.items():
        download_file(url, MODELS_DIR / filename)

    print("\nAll models ready.")


if __name__ == "__main__":
    main()
