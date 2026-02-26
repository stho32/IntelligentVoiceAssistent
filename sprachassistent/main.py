"""Voice assistant "Jarvis" - main process.

Producers (main thread, Matrix bridge) enqueue AssistantMessages into a shared
work_queue.  A single worker thread processes them sequentially and routes
responses back to the correct output channel (TTS, terminal, Matrix).
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import queue
import subprocess
import threading
import time
from pathlib import Path

from sprachassistent.ai.claude_code import ClaudeCodeBackend
from sprachassistent.audio.recorder import SpeechRecorder
from sprachassistent.audio.wake_word import WakeWordDetector
from sprachassistent.chat.message import AssistantMessage, InputType, MessageSource
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
                    filter_phrases=stt_cfg.get("filter_phrases", []),
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


def _route_response(
    msg: AssistantMessage,
    response: str,
    *,
    ui: TerminalUI,
    tts: OpenAITextToSpeech | None,
    player,
    matrix_outgoing: queue.Queue | None,
) -> None:
    """Display the response and route it to the appropriate output channel."""
    ui.set_response(response)
    ui.print_conversation_turn()

    if msg.source == MessageSource.VOICE:
        if tts is not None and player is not None:
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
            if _READY_PATH.exists():
                try:
                    player.play_wav(_READY_PATH)
                except Exception:
                    pass
    elif msg.source == MessageSource.MATRIX:
        if matrix_outgoing is not None and msg.room_id is not None:
            matrix_outgoing.put((msg.room_id, response))


def _route_error(
    msg: AssistantMessage,
    error_text: str,
    *,
    matrix_outgoing: queue.Queue | None,
) -> None:
    """Send an error message back to the originating channel."""
    if msg.source == MessageSource.MATRIX:
        if matrix_outgoing is not None and msg.room_id is not None:
            matrix_outgoing.put((msg.room_id, error_text))


def _worker_loop(
    work_queue: queue.Queue,
    components: dict,
    player,
    ui: TerminalUI,
    *,
    thinking_beep_interval: float = 3,
    cancel_keywords: list[str],
    reset_keywords: list[str],
    restart_keywords: list[str],
    matrix_outgoing: queue.Queue | None = None,
    sample_rate: int = 16000,
    min_recording_sec: float = 0.0,
    stop_event: threading.Event,
    restart_event: threading.Event,
) -> None:
    """Worker thread: consume messages from work_queue and process them.

    Runs until *stop_event* is set.  Each message is fully processed
    (STT if needed -> filter -> keywords -> AI -> routing) before the
    next one is taken from the queue.
    """
    ai_backend: ClaudeCodeBackend = components["ai_backend"]
    transcriber = components.get("transcriber")
    tts = components.get("tts")

    while not stop_event.is_set():
        try:
            msg: AssistantMessage = work_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            _process_message(
                msg,
                ai_backend=ai_backend,
                transcriber=transcriber,
                tts=tts,
                player=player,
                ui=ui,
                thinking_beep_interval=thinking_beep_interval,
                cancel_keywords=cancel_keywords,
                reset_keywords=reset_keywords,
                restart_keywords=restart_keywords,
                matrix_outgoing=matrix_outgoing,
                sample_rate=sample_rate,
                min_recording_sec=min_recording_sec,
                restart_event=restart_event,
            )
        except Exception as exc:
            log.error("Worker error processing message: %s", exc)
        finally:
            work_queue.task_done()


def _process_message(
    msg: AssistantMessage,
    *,
    ai_backend: ClaudeCodeBackend,
    transcriber,
    tts,
    player,
    ui: TerminalUI,
    thinking_beep_interval: float,
    cancel_keywords: list[str],
    reset_keywords: list[str],
    restart_keywords: list[str],
    matrix_outgoing: queue.Queue | None,
    sample_rate: int,
    min_recording_sec: float,
    restart_event: threading.Event,
) -> None:
    """Process a single AssistantMessage (runs inside the worker thread)."""
    # --- 1. Determine text content ---
    text: str | None = None

    if msg.input_type == InputType.AUDIO:
        if transcriber is None:
            log.warning("Received AUDIO message but no transcriber available")
            return

        audio_data = msg.content
        if not isinstance(audio_data, bytes) or not audio_data:
            return

        # Check minimum recording duration
        if min_recording_sec > 0:
            duration = len(audio_data) / (sample_rate * 2)
            if duration < min_recording_sec:
                log.info(
                    "Recording too short (%.1fs < %.1fs), ignoring.", duration, min_recording_sec
                )
                return

        ui.set_state(AssistantState.PROCESSING)
        try:
            text = transcriber.transcribe(audio_data)
        except Exception as e:
            ui.set_state(AssistantState.ERROR)
            ui.log(f"STT error: {e}")
            if msg.source == MessageSource.VOICE and tts is not None and player is not None:
                _speak_error(tts, player, "stt", ui)
                if _READY_PATH.exists():
                    player.play_wav(_READY_PATH)
            _route_error(
                msg, f"Fehler bei der Transkription: {e}", matrix_outgoing=matrix_outgoing
            )
            ui.set_state(AssistantState.LISTENING)
            return

        text = transcriber.filter_transcript(text)
    else:
        # TEXT input
        raw = msg.content
        text = raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace")

        # Apply transcript filtering for voice/keyboard text (Matrix text is already filtered)
        if msg.source in (MessageSource.VOICE, MessageSource.KEYBOARD) and transcriber is not None:
            text = transcriber.filter_transcript(text)

    if not text or not text.strip():
        return

    # --- 2. UI update ---
    ui.set_input_source(msg.source.value)
    ui.set_transcription(text)

    # --- 3. Keyword checks ---
    normalized = text.strip().lower()

    # Cancel
    if cancel_keywords and any(kw in normalized for kw in cancel_keywords):
        if msg.source == MessageSource.VOICE:
            ui.log("Command cancelled by user.")
            if tts is not None and player is not None:
                try:
                    tts.speak("Alles klar.", player=player)
                except Exception:
                    pass
                if _READY_PATH.exists():
                    player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
        elif msg.source == MessageSource.KEYBOARD:
            ui.log("Command cancelled by user.")
            ui.set_state(AssistantState.LISTENING)
        elif msg.source == MessageSource.MATRIX:
            ai_backend.cancel()
            if matrix_outgoing is not None and msg.room_id is not None:
                matrix_outgoing.put((msg.room_id, "Abgebrochen."))
            ui.log(f"Chat cancel from {msg.sender}")
        return

    # Reset
    if reset_keywords and any(kw in normalized for kw in reset_keywords):
        ai_backend.reset_session()
        if msg.source == MessageSource.VOICE:
            ui.log("Conversation reset by user.")
            if tts is not None and player is not None:
                try:
                    tts.speak("Alles klar, ich starte eine neue Konversation.", player=player)
                except Exception:
                    pass
                if _READY_PATH.exists():
                    player.play_wav(_READY_PATH)
            ui.set_state(AssistantState.LISTENING)
        elif msg.source == MessageSource.KEYBOARD:
            ui.log("Conversation reset by user.")
            ui.set_state(AssistantState.LISTENING)
        elif msg.source == MessageSource.MATRIX:
            if matrix_outgoing is not None and msg.room_id is not None:
                matrix_outgoing.put((msg.room_id, "Konversation zurueckgesetzt."))
            ui.log(f"Chat reset from {msg.sender}")
        return

    # Restart (only for voice/keyboard -- Matrix restart is treated as normal message)
    if restart_keywords and msg.source in (MessageSource.VOICE, MessageSource.KEYBOARD):
        if any(kw in normalized for kw in restart_keywords):
            ui.log("Restart requested by user.")
            if msg.source == MessageSource.VOICE and tts is not None and player is not None:
                try:
                    tts.speak("Alles klar, ich starte jetzt neu.", player=player)
                except Exception:
                    pass
            restart_event.set()
            return

    # --- 4. AI request ---
    ui.set_state(AssistantState.PROCESSING)

    # Thinking beep for voice input
    stop_beep = None
    beep_thread = None
    if msg.source == MessageSource.VOICE and player is not None:
        stop_beep = threading.Event()
        beep_thread = threading.Thread(
            target=_thinking_beep_loop,
            args=(player, stop_beep, thinking_beep_interval),
            daemon=True,
        )
        beep_thread.start()

    try:
        if msg.source == MessageSource.MATRIX:
            prompt = f"[Chat-Nachricht, Markdown-Antwort erlaubt]: {text}"
        else:
            prompt = text

        response = ai_backend.ask(prompt)
    except Exception as e:
        if stop_beep is not None:
            stop_beep.set()
        if beep_thread is not None:
            beep_thread.join(timeout=1)
        ui.set_state(AssistantState.ERROR)
        ui.log(f"AI error: {e}")
        if msg.source == MessageSource.VOICE and tts is not None and player is not None:
            if isinstance(e.__cause__, subprocess.TimeoutExpired):
                _speak_error(tts, player, "ai_timeout", ui)
            else:
                _speak_error(tts, player, "ai_general", ui)
            if _READY_PATH.exists():
                player.play_wav(_READY_PATH)
        _route_error(msg, f"Fehler bei der Verarbeitung: {e}", matrix_outgoing=matrix_outgoing)
        ui.set_state(AssistantState.LISTENING)
        return

    if stop_beep is not None:
        stop_beep.set()
    if beep_thread is not None:
        beep_thread.join(timeout=1)

    # --- 5. Route response ---
    _route_response(
        msg,
        response,
        ui=ui,
        tts=tts,
        player=player,
        matrix_outgoing=matrix_outgoing,
    )

    ui.set_input_source("voice")
    ui.set_state(AssistantState.LISTENING)


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
    matrix_outgoing: queue.Queue | None = None,
    work_queue: queue.Queue | None = None,
    sample_rate: int = 16000,
    min_recording_sec: float = 0.0,
) -> None:
    """Run the main assistant loop (producer side).

    The main thread produces AssistantMessages from wake-word and keyboard
    input and places them on *work_queue*.  A background worker thread
    processes them sequentially.

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
        matrix_outgoing: Optional queue for outgoing Matrix chat responses.
        work_queue: Shared work queue (created internally if None).
        sample_rate: Audio sample rate in Hz (for duration calculation).
        min_recording_sec: Minimum recording duration; shorter recordings are ignored.
    """
    if cancel_keywords is None:
        cancel_keywords = []
    if reset_keywords is None:
        reset_keywords = []
    if restart_keywords is None:
        restart_keywords = []
    if work_queue is None:
        work_queue = queue.Queue()

    wake_word: WakeWordDetector = components["wake_word"]
    recorder: SpeechRecorder = components["recorder"]

    stop_event = threading.Event()
    restart_event = threading.Event()

    worker = threading.Thread(
        target=_worker_loop,
        args=(work_queue, components, player, ui),
        kwargs={
            "thinking_beep_interval": thinking_beep_interval,
            "cancel_keywords": cancel_keywords,
            "reset_keywords": reset_keywords,
            "restart_keywords": restart_keywords,
            "matrix_outgoing": matrix_outgoing,
            "sample_rate": sample_rate,
            "min_recording_sec": min_recording_sec,
            "stop_event": stop_event,
            "restart_event": restart_event,
        },
        daemon=True,
        name="worker",
    )
    worker.start()

    ui.set_state(AssistantState.LISTENING)
    ui.log("Assistant ready. Say 'Hey Jarvis' to activate.")

    try:
        while True:
            # Check restart request from worker
            if restart_event.is_set():
                raise _RestartRequested

            # Keyboard check (non-blocking)
            if keyboard_monitor is not None and text_input is not None:
                key = keyboard_monitor.check()
                if key is not None:
                    ui.set_state(AssistantState.TYPING)
                    keyboard_monitor.pause()
                    try:
                        typed_text = text_input.collect(initial_char=key, ui=ui)
                    finally:
                        keyboard_monitor.resume()
                    if typed_text and typed_text.strip():
                        work_queue.put(
                            AssistantMessage(
                                source=MessageSource.KEYBOARD,
                                input_type=InputType.TEXT,
                                content=typed_text,
                            )
                        )
                    else:
                        ui.set_state(AssistantState.LISTENING)
                    continue

            # Listen for wake word
            audio_chunk = mic.read_chunk()
            if not wake_word.process(audio_chunk):
                continue

            # Wake word detected
            ui.log("Wake word detected!")
            wake_word.reset()

            if _DING_PATH.exists():
                player.play_wav(_DING_PATH)

            # Record speech
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

            # Signal: recording done
            if _PROCESSING_PATH.exists():
                player.play_wav(_PROCESSING_PATH)

            # Enqueue for worker
            work_queue.put(
                AssistantMessage(
                    source=MessageSource.VOICE,
                    input_type=InputType.AUDIO,
                    content=recorded_audio,
                )
            )
    finally:
        # Wait for queued messages to finish, then stop the worker
        try:
            work_queue.join()
        except Exception:
            pass
        stop_event.set()
        worker.join(timeout=5)


def run_chat_loop(
    ai_backend: ClaudeCodeBackend,
    ui: TerminalUI,
    work_queue: queue.Queue,
    matrix_outgoing: queue.Queue,
    cancel_keywords: list[str] | None = None,
    reset_keywords: list[str] | None = None,
) -> None:
    """Run a chat-only loop without any audio components.

    The Matrix bridge writes directly into *work_queue*.  This function
    starts a worker thread and then blocks until interrupted.

    Args:
        ai_backend: The AI backend instance.
        ui: Active terminal UI.
        work_queue: Shared work queue (Matrix bridge writes here).
        matrix_outgoing: Queue for outgoing Matrix chat responses.
        cancel_keywords: Keywords that cancel the current AI request.
        reset_keywords: Keywords that reset the conversation session.
    """
    if cancel_keywords is None:
        cancel_keywords = []
    if reset_keywords is None:
        reset_keywords = []

    components = {"ai_backend": ai_backend}
    stop_event = threading.Event()
    restart_event = threading.Event()

    worker = threading.Thread(
        target=_worker_loop,
        args=(work_queue, components, None, ui),
        kwargs={
            "cancel_keywords": cancel_keywords,
            "reset_keywords": reset_keywords,
            "restart_keywords": [],
            "matrix_outgoing": matrix_outgoing,
            "stop_event": stop_event,
            "restart_event": restart_event,
        },
        daemon=True,
        name="worker",
    )
    worker.start()

    ui.set_state(AssistantState.LISTENING)
    ui.log("Chat-only mode. Waiting for Matrix messages...")

    try:
        while not stop_event.is_set():
            stop_event.wait(timeout=1.0)
    finally:
        stop_event.set()
        worker.join(timeout=5)


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

    # Create shared queues
    work_queue = queue.Queue()
    matrix_outgoing: queue.Queue | None = None

    # Start Matrix bridge if configured
    matrix_cfg = config.get("matrix")
    matrix_bridge = None
    if matrix_cfg:
        matrix_outgoing = queue.Queue()
        try:
            from sprachassistent.chat.matrix_client import start_matrix_thread

            stt_cfg = config["stt"]
            matrix_transcriber = WhisperTranscriber(
                model=stt_cfg["model"],
                language=stt_cfg["language"],
                filter_phrases=stt_cfg.get("filter_phrases", []),
            )
            _matrix_thread, matrix_bridge = start_matrix_thread(
                matrix_cfg,
                work_queue,
                matrix_outgoing,
                transcriber=matrix_transcriber,
                start_timestamp=int(time.time() * 1000),
            )
            log.info("Matrix chat integration enabled (with audio transcription)")
        except Exception as e:
            log.error("Failed to start Matrix bridge: %s", e)
            matrix_outgoing = None

    chat_only = args.chat_only

    if chat_only:
        if matrix_outgoing is None:
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
                    work_queue,
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
        text_input_inst = TextInput() if TextInput is not None else None
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
                text_input=text_input_inst,
                matrix_outgoing=matrix_outgoing,
                work_queue=work_queue,
                sample_rate=audio_cfg["sample_rate"],
                min_recording_sec=audio_cfg.get("min_recording_sec", 0.0),
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
