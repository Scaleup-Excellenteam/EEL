"""Speech-to-text helpers for the temporary Streamlit voice input experiment."""

from io import BytesIO
from pathlib import Path
import wave
from typing import Any

import speech_recognition as sr

DEFAULT_LANGUAGE = "en-US"
FALLBACK_LANGUAGE = "en-GB"
MIN_RECORDING_SECONDS = 0.25
NOT_RECOGNIZED_MESSAGE = (
    "Speech was not recognized. Try speaking clearly for 1-2 seconds and "
    "keep the microphone close."
)


class VoiceInputError(Exception):
    """Raised when WAV transcription cannot produce a usable transcript."""


def transcribe_wav(
    audio: str | Path | bytes | bytearray, language: str = DEFAULT_LANGUAGE
) -> str:
    """Transcribe a WAV file path or WAV bytes using SpeechRecognition."""
    wav_bytes = _read_wav_bytes(audio)
    _validate_wav_bytes(wav_bytes)

    recognizer = sr.Recognizer()

    try:
        with sr.AudioFile(BytesIO(wav_bytes)) as source:
            audio_data = recognizer.record(source)
    except (OSError, ValueError, EOFError, wave.Error) as error:
        raise VoiceInputError("Could not read the recorded WAV audio.") from error

    for current_language in _languages_to_try(language):
        try:
            response = recognizer.recognize_google(
                audio_data, language=current_language, show_all=True
            )
        except sr.UnknownValueError:
            response = None
        except sr.RequestError as error:
            raise VoiceInputError(f"Speech recognition service error: {error}") from error
        transcript = _best_transcript(response)
        if transcript:
            return transcript

    raise VoiceInputError(NOT_RECOGNIZED_MESSAGE)


def _read_wav_bytes(audio: str | Path | bytes | bytearray) -> bytes:
    if isinstance(audio, (bytes, bytearray)):
        return bytes(audio)
    try:
        return Path(audio).read_bytes()
    except OSError as error:
        raise VoiceInputError("Could not read the recorded WAV audio.") from error


def _validate_wav_bytes(wav_bytes: bytes) -> None:
    try:
        with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
    except (EOFError, wave.Error) as error:
        raise VoiceInputError("Could not read the recorded WAV audio.") from error

    if frame_count <= 0 or frame_rate <= 0:
        raise VoiceInputError(NOT_RECOGNIZED_MESSAGE)

    duration_seconds = frame_count / frame_rate
    if duration_seconds < MIN_RECORDING_SECONDS:
        raise VoiceInputError(NOT_RECOGNIZED_MESSAGE)


def _languages_to_try(language: str) -> tuple[str, ...]:
    if language == DEFAULT_LANGUAGE:
        return (DEFAULT_LANGUAGE, FALLBACK_LANGUAGE)
    return (language,)


def _best_transcript(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()

    if not response:
        return ""

    alternatives = response.get("alternative", []) if isinstance(response, dict) else response
    for alternative in alternatives:
        if isinstance(alternative, dict):
            transcript = str(alternative.get("transcript", "")).strip()
        else:
            transcript = str(alternative).strip()
        if transcript:
            return transcript

    return ""
