from io import BytesIO
from pathlib import Path
import wave

import pytest

from src import speech_service
from src.speech_service import VoiceInputError, transcribe_wav


def _wav_bytes(duration_seconds: float = 0.5, frame_rate: int = 16000) -> bytes:
    buffer = BytesIO()
    frame_count = int(duration_seconds * frame_rate)
    sample = (1000).to_bytes(2, byteorder="little", signed=True)
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(frame_rate)
        wav_file.writeframes(sample * frame_count)
    return buffer.getvalue()


class FakeAudioFile:
    last_input = None

    def __init__(self, audio_source):
        self.audio_source = audio_source
        FakeAudioFile.last_input = audio_source

    def __enter__(self):
        return "audio-source"

    def __exit__(self, exc_type, exc, traceback):
        return False


class FakeRecognizer:
    record_calls = []
    recognize_calls = []
    responses_by_language = {}
    errors_by_language = {}

    def record(self, source):
        self.record_calls.append(source)
        return "audio-data"

    def recognize_google(self, audio_data, language="en-US", show_all=False):
        self.recognize_calls.append((audio_data, language, show_all))
        error = self.errors_by_language.get(language)
        if error:
            raise error
        return self.responses_by_language.get(language, {})


@pytest.fixture(autouse=True)
def fake_speech_recognition(monkeypatch):
    FakeRecognizer.record_calls = []
    FakeRecognizer.recognize_calls = []
    FakeRecognizer.responses_by_language = {
        "en-US": {
            "alternative": [
                {"transcript": " recognized words ", "confidence": 0.9},
                {"transcript": "wreck a nice words", "confidence": 0.4},
            ]
        }
    }
    FakeRecognizer.errors_by_language = {}
    FakeAudioFile.last_input = None
    monkeypatch.setattr(speech_service.sr, "AudioFile", FakeAudioFile)
    monkeypatch.setattr(speech_service.sr, "Recognizer", FakeRecognizer)


def test_transcribes_wav_bytes_with_default_google_language() -> None:
    wav_bytes = _wav_bytes()

    transcript = transcribe_wav(wav_bytes)

    assert transcript == "recognized words"
    assert FakeAudioFile.last_input.read() == wav_bytes
    assert FakeRecognizer.record_calls == ["audio-source"]
    assert FakeRecognizer.recognize_calls == [("audio-data", "en-US", True)]


def test_transcribes_wav_path_with_custom_language(tmp_path: Path) -> None:
    wav_path = tmp_path / "sample.wav"
    wav_path.write_bytes(_wav_bytes())
    FakeRecognizer.responses_by_language = {
        "en-GB": {"alternative": [{"transcript": "custom language words"}]}
    }

    transcript = transcribe_wav(wav_path, language="en-GB")

    assert transcript == "custom language words"
    assert FakeAudioFile.last_input.read() == wav_path.read_bytes()
    assert FakeRecognizer.recognize_calls == [("audio-data", "en-GB", True)]


def test_falls_back_to_en_gb_when_en_us_has_no_usable_transcript() -> None:
    FakeRecognizer.responses_by_language = {
        "en-US": {"alternative": []},
        "en-GB": {"alternative": [{"transcript": "what"}]},
    }

    transcript = transcribe_wav(_wav_bytes())

    assert transcript == "what"
    assert FakeRecognizer.recognize_calls == [
        ("audio-data", "en-US", True),
        ("audio-data", "en-GB", True),
    ]


def test_unintelligible_speech_becomes_voice_input_error() -> None:
    FakeRecognizer.errors_by_language = {
        "en-US": speech_service.sr.UnknownValueError(),
        "en-GB": speech_service.sr.UnknownValueError(),
    }

    with pytest.raises(VoiceInputError, match="Speech was not recognized"):
        transcribe_wav(_wav_bytes())

    assert FakeRecognizer.recognize_calls == [
        ("audio-data", "en-US", True),
        ("audio-data", "en-GB", True),
    ]


def test_network_or_service_error_becomes_voice_input_error() -> None:
    FakeRecognizer.errors_by_language = {
        "en-US": speech_service.sr.RequestError("service unavailable")
    }

    with pytest.raises(VoiceInputError, match="service unavailable"):
        transcribe_wav(_wav_bytes())


def test_empty_alternatives_become_voice_input_error() -> None:
    FakeRecognizer.responses_by_language = {
        "en-US": {"alternative": [{"transcript": "   "}]},
        "en-GB": {"alternative": []},
    }

    with pytest.raises(VoiceInputError, match="Speech was not recognized"):
        transcribe_wav(_wav_bytes())


def test_too_short_recording_is_rejected_before_recognition() -> None:
    with pytest.raises(VoiceInputError, match="Speech was not recognized"):
        transcribe_wav(_wav_bytes(duration_seconds=0.05))

    assert FakeAudioFile.last_input is None
    assert FakeRecognizer.record_calls == []
    assert FakeRecognizer.recognize_calls == []
