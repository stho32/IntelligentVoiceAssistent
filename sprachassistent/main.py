"""Voice assistant "Jarvis" - main process.

Main loop: Wake-Word -> Ding -> Record -> STT -> AI -> TTS -> Repeat.
"""

import logging
import subprocess
import threading
from pathlib import Path

from sprachassistent.ai.claude_code import ClaudeCodeBackend
from sprachassistent.audio.microphone import MicrophoneStream
from sprachassistent.audio.player import AudioPlayer
from sprachassistent.audio.recorder import SpeechRecorder
from sprachassistent.audio.wake_word import WakeWordDetector
from sprachassistent.config import get_config
from sprachassistent.stt.whisper_api import WhisperTranscriber
from sprachassistent.tts.openai_tts import OpenAITextToSpeech
from sprachassistent.utils.logging import get_logger, setup_logging
from sprachassistent.utils.terminal_ui import AssistantState, TerminalUI

log = get_logger("main")

_PACKAGE_DIR = Path(__file__).parent
_SOUNDS_DIR = _PACKAGE_DIR / "audio" / "sounds"
_DING_PATH = _SOUNDS_DIR / "ding.wav"
_PROCESSING_PATH = _SOUNDS_DIR / "processing.wav"
_READY_PATH = _SOUNDS_DIR / "ready.wav"
_THINKING_PATH = _SOUNDS_DIR / "thinking.wav"
_ERROR_SOUND_PATH = _SOUNDS_DIR / "error.wav"

# Spoken error messages (German, matching language: de config)
_ERROR_MESSAGES = {
    "stt": "Entschuldigung, ich konnte dich nicht verstehen. Bitte versuche es nochmal.",
    "ai_timeout": "Die Verarbeitung hat zu lange gedauert. Bitte versuche es nochmal.",
    "ai_general": "Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten.",
}


def create_components(config: dict) -> dict:
    """Create all assistant components from config.

    Returns:
        Dictionary with component instances.
    """
    ww_cfg = config["wake_word"]
    audio_cfg = config["audio"]
    ai_cfg = config["ai"]
    stt_cfg = config["stt"]
    tts_cfg = config["tts"]

    # Load system prompt
    prompt_path = _PACKAGE_DIR / ai_cfg["system_prompt_path"]
    system_prompt = ""
    if prompt_path.exists():
        system_prompt = prompt_path.read_text().strip()

    return {
        "wake_word": WakeWordDetector(
            model_path=ww_cfg.get("model_path") or ww_cfg.get("model_name", "hey_jarvis"),
            threshold=ww_cfg.get("threshold", 0.5),
        ),
        "recorder": SpeechRecorder(
            sample_rate=audio_cfg["sample_rate"],
            vad_threshold=audio_cfg.get("vad_threshold", 0.5),
            silence_duration_sec=audio_cfg.get("silence_threshold_sec", 1.5),
            max_duration_sec=audio_cfg.get("max_recording_sec", 30),
        ),
        "transcriber": WhisperTranscriber(
            model=stt_cfg["model"],
            language=stt_cfg["language"],
        ),
        "ai_backend": ClaudeCodeBackend(
            working_directory=ai_cfg["working_directory"],
            system_prompt=system_prompt,
            timeout=ai_cfg.get("timeout", 300),
        ),
        "tts": OpenAITextToSpeech(
            model=tts_cfg["model"],
            voice=tts_cfg["voice"],
            speed=tts_cfg.get("speed", 1.0),
        ),
    }


def _thinking_beep_loop(
    player: AudioPlayer,
    stop_event: threading.Event,
    interval: float,
) -> None:
    """Play a periodic beep while the AI is thinking."""
    while not stop_event.wait(timeout=interval):
        if _THINKING_PATH.exists():
            try:
                player.play_wav(_THINKING_PATH)
            except Exception:
                pass


def _speak_error(
    tts: OpenAITextToSpeech,
    player: AudioPlayer,
    error_key: str,
    ui: TerminalUI,
) -> None:
    """Speak an error message to the user, with sound fallback.

    If TTS fails (because TTS itself is the problem), falls back to
    playing an error sound file.
    """
    message = _ERROR_MESSAGES.get(error_key, _ERROR_MESSAGES["ai_general"])
    try:
        tts.speak(message, pa=player._pa)
    except Exception as tts_err:
        ui.log(f"Error TTS also failed: {tts_err}")
        if _ERROR_SOUND_PATH.exists():
            try:
                player.play_wav(_ERROR_SOUND_PATH)
            except Exception:
                pass


def run_loop(
    components: dict,
    mic: MicrophoneStream,
    player: AudioPlayer,
    ui: TerminalUI,
    thinking_beep_interval: float = 3,
) -> None:
    """Run the main assistant loop.

    Args:
        components: Dictionary of component instances from create_components.
        mic: Open microphone stream.
        player: Open audio player.
        ui: Active terminal UI.
    """
    wake_word: WakeWordDetector = components["wake_word"]
    recorder: SpeechRecorder = components["recorder"]
    transcriber: WhisperTranscriber = components["transcriber"]
    ai_backend: ClaudeCodeBackend = components["ai_backend"]
    tts: OpenAITextToSpeech = components["tts"]

    ui.set_state(AssistantState.LISTENING)
    ui.log("Assistant ready. Say 'Hey Jarvis' to activate.")

    while True:
        # Phase 1: Listen for wake word
        audio_chunk = mic.read_chunk()
        if not wake_word.process(audio_chunk):
            continue

        # Wake word detected
        ui.log("Wake word detected!")
        wake_word.reset()

        # Play confirmation sound
        if _DING_PATH.exists():
            player.play_wav(_DING_PATH)

        # Phase 2: Record speech
        ui.set_state(AssistantState.RECORDING)
        ui.set_transcription("")
        ui.set_response("")
        recorder.start()

        while recorder.process_chunk(mic.read_chunk()):
            pass

        recorded_audio = recorder.get_audio()
        if not recorded_audio:
            ui.set_state(AssistantState.LISTENING)
            continue

        # Signal: Recording done, now processing
        if _PROCESSING_PATH.exists():
            player.play_wav(_PROCESSING_PATH)

        # Phase 3: Transcribe
        ui.set_state(AssistantState.PROCESSING)
        try:
            text = transcriber.transcribe(recorded_audio)
        except Exception as e:
            ui.set_state(AssistantState.ERROR)
            ui.log(f"STT error: {e}")
            _speak_error(tts, player, "stt", ui)
            if _READY_PATH.exists():
                player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
            continue

        if not text.strip():
            ui.set_state(AssistantState.LISTENING)
            continue

        ui.set_transcription(text)
        ui.log(f"Transcription: {text}")

        # Phase 4: Get AI response (with periodic beep)
        stop_beep = threading.Event()
        beep_thread = threading.Thread(
            target=_thinking_beep_loop,
            args=(player, stop_beep, thinking_beep_interval),
            daemon=True,
        )
        beep_thread.start()
        try:
            response = ai_backend.ask(text)
        except Exception as e:
            stop_beep.set()
            beep_thread.join(timeout=1)
            ui.set_state(AssistantState.ERROR)
            ui.log(f"AI error: {e}")
            if isinstance(e.__cause__, subprocess.TimeoutExpired):
                _speak_error(tts, player, "ai_timeout", ui)
            else:
                _speak_error(tts, player, "ai_general", ui)
            if _READY_PATH.exists():
                player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
            continue
        finally:
            stop_beep.set()
            beep_thread.join(timeout=1)

        ui.set_response(response)
        ui.log(f"Response: {response}")

        # Phase 5: Speak response
        ui.set_state(AssistantState.SPEAKING)
        try:
            tts.speak(response, pa=player._pa)
        except Exception as e:
            ui.log(f"TTS error: {e}")
            if _ERROR_SOUND_PATH.exists():
                try:
                    player.play_wav(_ERROR_SOUND_PATH)
                except Exception:
                    pass

        # Signal: Ready for next command
        if _READY_PATH.exists():
            player.play_wav(_READY_PATH)

        # Back to listening
        ui.set_state(AssistantState.LISTENING)


def main() -> None:
    """Start the voice assistant."""
    setup_logging(level=logging.DEBUG)

    try:
        config = get_config()
    except Exception as e:
        log.error("Failed to load config: %s", e)
        raise SystemExit(1) from e

    audio_cfg = config["audio"]

    try:
        components = create_components(config)
    except Exception as e:
        log.error("Failed to initialize components: %s", e)
        raise SystemExit(1) from e

    with (
        MicrophoneStream(
            rate=audio_cfg["sample_rate"],
            channels=audio_cfg.get("channels", 1),
            chunk_size=audio_cfg.get("chunk_size", 1280),
        ) as mic,
        AudioPlayer() as player,
        TerminalUI() as ui,
    ):
        try:
            beep_interval = config["ai"].get("thinking_beep_interval", 3)
            run_loop(components, mic, player, ui, thinking_beep_interval=beep_interval)
        except KeyboardInterrupt:
            ui.log("Shutting down...")


if __name__ == "__main__":
    main()
