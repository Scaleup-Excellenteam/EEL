"""Streamlit entry point for the EEL autocomplete engine."""

import hashlib
from pathlib import Path

import streamlit as st

from src.autocomplete import AutoCompleteEngine
from src.index import InvertedIndex
from src.loader import Corpus
from src.models import AutoCompleteData
from src.speech_service import VoiceInputError, transcribe_wav

DEFAULT_CORPUS_ROOT = Path("Archive")
RESULT_LIMIT = 5

QUERY_KEY = "query"
VOICE_ERROR_KEY = "voice_error"
PROCESSED_RECORDING_KEY = "processed_recording_id"


@st.cache_resource(show_spinner="Loading corpus and building index...")
def load_engine(corpus_root: str) -> AutoCompleteEngine:
    """Build the reusable autocomplete engine for Streamlit reruns."""
    root = Path(corpus_root)
    corpus = Corpus.load(root)
    index = InvertedIndex.build(corpus)
    return AutoCompleteEngine(corpus, index)


def main() -> None:
    st.title("EEL Autocomplete")
    st.write(
        "Search the local text corpus with the existing autocomplete engine. "
        "Results come from `./Archive` and show the original sentence, source, "
        "line, and score."
    )

    query, search_clicked = show_search_controls()

    corpus_root = DEFAULT_CORPUS_ROOT
    if not corpus_root.exists() or not corpus_root.is_dir():
        st.error("Archive folder not found. Unzip the corpus to `./Archive`.")
        return

    if not search_clicked:
        return

    if not query.strip():
        st.info("Enter some text before searching.")
        return

    try:
        engine = load_engine(str(corpus_root))
    except OSError as error:
        st.error(f"Could not load the corpus from `./Archive`: {error}")
        return

    results = engine.get_best_k_completions(query, k=RESULT_LIMIT)
    if not results:
        st.info("No results found.")
        return

    show_results(results)


def show_search_controls() -> tuple[str, bool]:
    st.session_state.setdefault(QUERY_KEY, "")

    input_column, microphone_column, button_column = st.columns(
        [7, 2, 1.5], vertical_alignment="bottom"
    )

    with microphone_column:
        recorded_audio = st.audio_input(
            "Microphone",
            sample_rate=16000,
            key="microphone_recording",
            label_visibility="collapsed",
        )

    if recorded_audio is not None:
        process_microphone_recording(recorded_audio.getvalue())

    with input_column:
        query = st.text_input(
            "Search text",
            key=QUERY_KEY,
            type="search",
            placeholder="Type a search, or record with the microphone",
            label_visibility="collapsed",
        )

    with button_column:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    voice_error = st.session_state.get(VOICE_ERROR_KEY)
    if voice_error:
        st.warning(voice_error)

    return query, search_clicked


def process_microphone_recording(audio_bytes: bytes) -> None:
    recording_id = hashlib.sha256(audio_bytes).hexdigest()
    if st.session_state.get(PROCESSED_RECORDING_KEY) == recording_id:
        return

    st.session_state[PROCESSED_RECORDING_KEY] = recording_id
    try:
        st.session_state[QUERY_KEY] = transcribe_wav(audio_bytes)
        st.session_state.pop(VOICE_ERROR_KEY, None)
    except VoiceInputError as error:
        st.session_state[VOICE_ERROR_KEY] = str(error)


def show_results(results: list[AutoCompleteData]) -> None:
    st.subheader(f"Top {len(results)} results")
    for rank, result in enumerate(results, start=1):
        st.markdown(f"**{rank}. Completed sentence**")
        st.text(result.completed_sentence)
        st.caption(
            f"Source file: {result.source_text} | "
            f"Offset / line number: {result.offset} | "
            f"Score: {result.score}"
        )


if __name__ == "__main__":
    main()
