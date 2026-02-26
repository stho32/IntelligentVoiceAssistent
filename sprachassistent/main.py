"""Voice assistant "Jarvis" - main process.

Main loop: Wake-Word -> Ding -> Record -> STT -> AI -> TTS -> Repeat.
Optionally bridges Matrix chat messages into the same AI backend.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import queue
import subprocess
import threading
from pathlib import Path

from sprachassistent.ai.claude_code import ClaudeCodeBackend
from sprachassistent.audio.recorder import SpeechRecorder
from sprachassistent.audio.wake_word import WakeWordDetector
from sprachassistent.chat.message import ChatMessage
from sprachassistent.config import get_config

try:
    from sprachassistent.input.keyboard import KeyboardMonitor
    from sprachassistent.input.text_input import TextInput
except ImportError:
    KeyboardMonitor = None  # type: ignore[assignment,misc]
    TextInput = None  # type: ignore[assignment,misc]
from sprachassistent.platform.factory import (
    create_audio_input,
    create_audio_output,
    create_restart_strategy,
)
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


def _process_chat_message(
    msg: ChatMessage,
    ai_backend: ClaudeCodeBackend,
    outgoing_queue: queue.Queue,
    ui: TerminalUI,
    cancel_keywords: list[str],
    reset_keywords: list[str],
) -> None:
    """Process a single chat message from Matrix.

    Handles cancel/reset keywords and forwards normal messages to the AI backend.
    Restart keywords are intentionally ignored for chat (no sense restarting
    the local process from a phone).

    Args:
        msg: The incoming chat message.
        ai_backend: The AI backend instance.
        outgoing_queue: Queue for sending responses back to Matrix.
        ui: Terminal UI for logging.
        cancel_keywords: Keywords that cancel the current AI request.
        reset_keywords: Keywords that reset the conversation.
    """
    text = msg.text.strip()
    normalized = text.lower()

    # Check for cancel command
    if cancel_keywords and any(kw in normalized for kw in cancel_keywords):
        ai_backend.cancel()
        outgoing_queue.put((msg.room_id, "Abgebrochen."))
        ui.log(f"Chat cancel from {msg.sender}")
        return

    # Check for reset command
    if reset_keywords and any(kw in normalized for kw in reset_keywords):
        ai_backend.reset_session()
        outgoing_queue.put((msg.room_id, "Konversation zurueckgesetzt."))
        ui.log(f"Chat reset from {msg.sender}")
        return

    # Normal message -- forward to AI with chat prefix
    ui.log(f"Chat from {msg.sender}: {text[:80]}")
    try:
        response = ai_backend.ask(f"[Chat-Nachricht, Markdown-Antwort erlaubt]: {text}")
        outgoing_queue.put((msg.room_id, response))
        ui.log(f"Chat response sent ({len(response)} chars)")
    except Exception as e:
        ui.log(f"Chat AI error: {e}")
        outgoing_queue.put((msg.room_id, f"Fehler bei der Verarbeitung: {e}"))


def create_components(
    config: dict,
    *,
    resume_session: bool = True,
    chat_only: bool = False,
) -> dict:
    """Create all assistant components from config.

    Args:
        config: Application configuration dictionary.
        resume_session: If True (default), the AI backend resumes the
            most recent Claude Code session on first call.
        chat_only: If True, skip audio components (wake word, recorder,
            STT, TTS) and only create the AI backend.

    Returns:
        Dictionary with component instances.
    """
    ai_cfg = config["ai"]

    # Load system prompt
    prompt_path = _PACKAGE_DIR / ai_cfg["system_prompt_path"]
    system_prompt = ""
    if prompt_path.exists():
        system_prompt = prompt_path.read_text().strip()

    components = {
        "ai_backend": ClaudeCodeBackend(
            working_directory=ai_cfg["working_directory"],
            system_prompt=system_prompt,
            timeout=ai_cfg.get("timeout", 300),
            resume_session=resume_session,
        ),
    }

    if not chat_only:
        ww_cfg = config["wake_word"]
        audio_cfg = config["audio"]
        stt_cfg = config["stt"]
        tts_cfg = config["tts"]

        components.update(
            {
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
                "tts": OpenAITextToSpeech(
                    model=tts_cfg["model"],
                    voice=tts_cfg["voice"],
                    speed=tts_cfg.get("speed", 1.0),
                ),
            }
        )

    return components


def _thinking_beep_loop(
    player,
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


class _RestartRequested(Exception):
    """Raised when the user requests a restart via voice command."""


def _restart_assistant() -> None:
    """Restart the assistant process using a platform-appropriate strategy."""
    strategy = create_restart_strategy()
    strategy()


def _is_cancel_command(text: str, cancel_keywords: list[str]) -> bool:
    """Check if transcribed text is a cancel command."""
    normalized = text.strip().lower()
    return any(keyword in normalized for keyword in cancel_keywords)


def _speak_error(
    tts: OpenAITextToSpeech,
    player,
    error_key: str,
    ui: TerminalUI,
) -> None:
    """Speak an error message to the user, with sound fallback.

    If TTS fails (because TTS itself is the problem), falls back to
    playing an error sound file.
    """
    message = _ERROR_MESSAGES.get(error_key, _ERROR_MESSAGES["ai_general"])
    try:
        tts.speak(message, player=player)
    except Exception as tts_err:
        ui.log(f"Error TTS also failed: {tts_err}")
        if _ERROR_SOUND_PATH.exists():
            try:
                player.play_wav(_ERROR_SOUND_PATH)
            except Exception:
                pass


def run_loop(
    components: dict,
    mic,
    player,
    ui: TerminalUI,
    thinking_beep_interval: float = 3,
    cancel_keywords: list[str] | None = None,
    reset_keywords: list[str] | None = None,
    restart_keywords: list[str] | None = None,
    keyboard_monitor: KeyboardMonitor | None = None,
    text_input: TextInput | None = None,
    matrix_incoming: queue.Queue | None = None,
    matrix_outgoing: queue.Queue | None = None,
) -> None:
    """Run the main assistant loop.

    Args:
        components: Dictionary of component instances from create_components.
        mic: Open microphone stream.
        player: Open audio player.
        ui: Active terminal UI.
        thinking_beep_interval: Seconds between beeps while AI is thinking.
        cancel_keywords: List of keywords that cancel the current command.
        reset_keywords: List of keywords that reset the conversation session.
        restart_keywords: List of keywords that restart the assistant process.
        keyboard_monitor: Optional keyboard monitor for text input activation.
        text_input: Optional text input handler for keyboard-based input.
        matrix_incoming: Optional queue for incoming Matrix chat messages.
        matrix_outgoing: Optional queue for outgoing Matrix chat responses.
    """
    if cancel_keywords is None:
        cancel_keywords = []
    if reset_keywords is None:
        reset_keywords = []
    if restart_keywords is None:
        restart_keywords = []
    wake_word: WakeWordDetector = components["wake_word"]
    recorder: SpeechRecorder = components["recorder"]
    transcriber: WhisperTranscriber = components["transcriber"]
    ai_backend: ClaudeCodeBackend = components["ai_backend"]
    tts: OpenAITextToSpeech = components["tts"]

    ui.set_state(AssistantState.LISTENING)
    ui.log("Assistant ready. Say 'Hey Jarvis' to activate.")

    while True:
        text = None
        from_keyboard = False

        # Keyboard check (non-blocking) — before mic.read_chunk()
        if keyboard_monitor is not None and text_input is not None:
            key = keyboard_monitor.check()
            if key is not None:
                ui.set_state(AssistantState.TYPING)
                keyboard_monitor.pause()
                try:
                    text = text_input.collect(initial_char=key, ui=ui)
                finally:
                    keyboard_monitor.resume()
                if not text or not text.strip():
                    ui.set_state(AssistantState.LISTENING)
                    continue
                from_keyboard = True

        if text is None:
            # Phase 1: Listen for wake word (normal voice path)
            audio_chunk = mic.read_chunk()
            if not wake_word.process(audio_chunk):
                # Check for Matrix chat messages while idle
                if matrix_incoming is not None and matrix_outgoing is not None:
                    try:
                        chat_msg = matrix_incoming.get_nowait()
                        _process_chat_message(
                            chat_msg,
                            ai_backend,
                            matrix_outgoing,
                            ui,
                            cancel_keywords,
                            reset_keywords,
                        )
                    except queue.Empty:
                        pass
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

        # === COMMON PATH (voice + keyboard) ===
        ui.set_input_source("keyboard" if from_keyboard else "voice")
        ui.set_transcription(text)

        # Check for cancel command
        if cancel_keywords and _is_cancel_command(text, cancel_keywords):
            ui.log("Command cancelled by user.")
            try:
                tts.speak("Alles klar.", player=player)
            except Exception:
                pass
            if _READY_PATH.exists():
                player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
            continue

        # Check for reset command
        if reset_keywords and _is_cancel_command(text, reset_keywords):
            ai_backend.reset_session()
            ui.log("Conversation reset by user.")
            try:
                tts.speak(
                    "Alles klar, ich starte eine neue Konversation.",
                    player=player,
                )
            except Exception:
                pass
            if _READY_PATH.exists():
                player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
            continue

        # Check for restart command
        if restart_keywords and _is_cancel_command(text, restart_keywords):
            ui.log("Restart requested by user.")
            try:
                tts.speak(
                    "Alles klar, ich starte jetzt neu.",
                    player=player,
                )
            except Exception:
                pass
            raise _RestartRequested

        # Phase 4: Get AI response (with periodic beep + cancel support)
        stop_beep = threading.Event()
        beep_thread = threading.Thread(
            target=_thinking_beep_loop,
            args=(player, stop_beep, thinking_beep_interval),
            daemon=True,
        )
        beep_thread.start()

        # Run AI in a thread so main thread can listen for cancel
        ai_result: dict = {"response": None, "error": None}
        ai_done = threading.Event()

        def _run_ai() -> None:
            try:
                ai_result["response"] = ai_backend.ask(text)
            except Exception as e:
                ai_result["error"] = e
            finally:
                ai_done.set()

        ai_thread = threading.Thread(target=_run_ai, daemon=True)
        ai_thread.start()

        # Listen for cancel while AI is working
        cancelled = False
        while not ai_done.is_set():
            try:
                chunk = mic.read_chunk()
            except Exception:
                break
            if cancel_keywords and wake_word.process(chunk):
                wake_word.reset()
                if _DING_PATH.exists():
                    player.play_wav(_DING_PATH)
                # Record the cancel utterance
                recorder.start()
                while recorder.process_chunk(mic.read_chunk()):
                    if ai_done.is_set():
                        break
                cancel_audio = recorder.get_audio()
                if cancel_audio:
                    try:
                        cancel_text = transcriber.transcribe(cancel_audio)
                        if _is_cancel_command(cancel_text, cancel_keywords):
                            ai_backend.cancel()
                            cancelled = True
                            break
                    except Exception:
                        pass

        stop_beep.set()
        beep_thread.join(timeout=1)
        ai_thread.join(timeout=2)

        if cancelled:
            ui.log("AI processing cancelled by user.")
            try:
                tts.speak("Abgebrochen.", player=player)
            except Exception:
                pass
            if _READY_PATH.exists():
                player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
            continue

        if ai_result["error"] is not None:
            e = ai_result["error"]
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

        response = ai_result["response"]

        ui.set_response(response)
        ui.print_conversation_turn()

        # Phase 5: Speak response
        ui.set_state(AssistantState.SPEAKING)
        try:
            tts.speak(response, player=player)
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
        ui.set_input_source("voice")
        ui.set_state(AssistantState.LISTENING)


def run_chat_loop(
    ai_backend: ClaudeCodeBackend,
    ui: TerminalUI,
    matrix_incoming: queue.Queue,
    matrix_outgoing: queue.Queue,
    cancel_keywords: list[str] | None = None,
    reset_keywords: list[str] | None = None,
) -> None:
    """Run a chat-only loop without any audio components.

    Blocks on the incoming queue instead of polling audio.

    Args:
        ai_backend: The AI backend instance.
        ui: Active terminal UI.
        matrix_incoming: Queue for incoming Matrix chat messages.
        matrix_outgoing: Queue for outgoing Matrix chat responses.
        cancel_keywords: Keywords that cancel the current AI request.
        reset_keywords: Keywords that reset the conversation session.
    """
    if cancel_keywords is None:
        cancel_keywords = []
    if reset_keywords is None:
        reset_keywords = []

    ui.set_state(AssistantState.LISTENING)
    ui.log("Chat-only mode. Waiting for Matrix messages...")

    while True:
        try:
            chat_msg = matrix_incoming.get(timeout=1.0)
        except queue.Empty:
            continue

        ui.set_state(AssistantState.PROCESSING)
        _process_chat_message(
            chat_msg,
            ai_backend,
            matrix_outgoing,
            ui,
            cancel_keywords,
            reset_keywords,
        )
        ui.set_state(AssistantState.LISTENING)


def main() -> None:
    """Start the voice assistant."""
    parser = argparse.ArgumentParser(description="Jarvis Voice Assistant")
    parser.add_argument(
        "--new-session",
        action="store_true",
        help="Start with a fresh conversation instead of resuming the previous one",
    )
    parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Run in chat-only mode (no audio, Matrix messages only)",
    )
    args = parser.parse_args()

    # Load config first, then set up file-based logging from config values.
    # If config loading fails, fall back to stderr logging.
    try:
        config = get_config()
    except Exception as e:
        setup_logging(level=logging.DEBUG)
        log.error("Failed to load config: %s", e)
        raise SystemExit(1) from e

    log_cfg = config.get("logging", {})
    log_file = log_cfg.get("file")
    log_level_name = log_cfg.get("level", "DEBUG")
    log_level = getattr(logging, log_level_name.upper(), logging.DEBUG)
    setup_logging(level=log_level, log_file=log_file)

    # Start Matrix bridge if configured
    matrix_cfg = config.get("matrix")
    matrix_incoming = None
    matrix_outgoing = None
    matrix_bridge = None
    if matrix_cfg:
        matrix_incoming = queue.Queue()
        matrix_outgoing = queue.Queue()
        try:
            from sprachassistent.chat.matrix_client import start_matrix_thread

            _matrix_thread, matrix_bridge = start_matrix_thread(
                matrix_cfg, matrix_incoming, matrix_outgoing
            )
            log.info("Matrix chat integration enabled")
        except Exception as e:
            log.error("Failed to start Matrix bridge: %s", e)
            matrix_incoming = None
            matrix_outgoing = None

    chat_only = args.chat_only

    if chat_only:
        if matrix_incoming is None:
            log.error("Matrix configuration required for --chat-only mode")
            raise SystemExit(1)

        try:
            components = create_components(
                config, resume_session=not args.new_session, chat_only=True
            )
        except Exception as e:
            log.error("Failed to initialize components: %s", e)
            raise SystemExit(1) from e

        commands_cfg = config.get("commands", {})
        cancel_kw = commands_cfg.get("cancel_keywords", [])
        reset_kw = commands_cfg.get("reset_keywords", [])

        with TerminalUI() as ui:
            try:
                run_chat_loop(
                    components["ai_backend"],
                    ui,
                    matrix_incoming,
                    matrix_outgoing,
                    cancel_keywords=cancel_kw,
                    reset_keywords=reset_kw,
                )
            except KeyboardInterrupt:
                ui.log("Shutting down...")
            finally:
                if matrix_bridge:
                    matrix_bridge.request_stop()
        return

    audio_cfg = config["audio"]

    try:
        components = create_components(config, resume_session=not args.new_session)
    except Exception as e:
        log.error("Failed to initialize components: %s", e)
        raise SystemExit(1) from e

    kb_ctx = KeyboardMonitor() if KeyboardMonitor is not None else contextlib.nullcontext()

    with (
        create_audio_input(
            rate=audio_cfg["sample_rate"],
            channels=audio_cfg.get("channels", 1),
            chunk_size=audio_cfg.get("chunk_size", 1280),
        ) as mic,
        create_audio_output() as player,
        TerminalUI() as ui,
        kb_ctx as keyboard_monitor,
    ):
        text_input = TextInput() if TextInput is not None else None
        try:
            beep_interval = config["ai"].get("thinking_beep_interval", 3)
            commands_cfg = config.get("commands", {})
            cancel_kw = commands_cfg.get("cancel_keywords", [])
            reset_kw = commands_cfg.get("reset_keywords", [])
            restart_kw = commands_cfg.get("restart_keywords", [])
            run_loop(
                components,
                mic,
                player,
                ui,
                thinking_beep_interval=beep_interval,
                cancel_keywords=cancel_kw,
                reset_keywords=reset_kw,
                restart_keywords=restart_kw,
                keyboard_monitor=keyboard_monitor,
                text_input=text_input,
                matrix_incoming=matrix_incoming,
                matrix_outgoing=matrix_outgoing,
            )
        except KeyboardInterrupt:
            ui.log("Shutting down...")
        except _RestartRequested:
            ui.log("Restarting...")
            # Resources are cleaned up by the with-block exiting
            _restart_assistant()
        finally:
            if matrix_bridge:
                matrix_bridge.request_stop()


if __name__ == "__main__":
    main()
