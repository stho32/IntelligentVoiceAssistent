"""Tests zur Verifizierung der Projektstruktur."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def test_sprachassistent_package_exists():
    """Das Hauptpaket sprachassistent/ muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent").is_dir()


def test_audio_module_exists():
    """Das Audio-Modul muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "audio").is_dir()
    assert (PROJECT_ROOT / "sprachassistent" / "audio" / "wake_word.py").is_file()
    assert (PROJECT_ROOT / "sprachassistent" / "audio" / "recorder.py").is_file()


def test_stt_module_exists():
    """Das STT-Modul muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "stt").is_dir()
    assert (PROJECT_ROOT / "sprachassistent" / "stt" / "whisper_api.py").is_file()


def test_ai_module_exists():
    """Das KI-Modul muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "ai").is_dir()
    assert (PROJECT_ROOT / "sprachassistent" / "ai" / "claude_code.py").is_file()
    assert (PROJECT_ROOT / "sprachassistent" / "ai" / "prompts" / "system.md").is_file()


def test_tts_module_exists():
    """Das TTS-Modul muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "tts").is_dir()
    assert (PROJECT_ROOT / "sprachassistent" / "tts" / "openai_tts.py").is_file()


def test_utils_module_exists():
    """Das Utils-Modul muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "utils").is_dir()
    assert (PROJECT_ROOT / "sprachassistent" / "utils" / "terminal_ui.py").is_file()


def test_config_exists():
    """Die Konfigurationsdatei muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "config.yaml").is_file()


def test_requirements_directory_exists():
    """Das Requirements-Verzeichnis muss existieren."""
    assert (PROJECT_ROOT / "Requirements").is_dir()
    assert (PROJECT_ROOT / "Requirements" / "001-Basisanforderungen.md").is_file()


def test_main_entry_point_exists():
    """Der Haupteinstiegspunkt muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "main.py").is_file()


def test_sounds_directory_exists():
    """Das Sounds-Verzeichnis muss existieren."""
    assert (PROJECT_ROOT / "sprachassistent" / "audio" / "sounds").is_dir()
