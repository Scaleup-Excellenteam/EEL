"""Streamlit entry point for the EEL autocomplete engine."""

from pathlib import Path

import streamlit as st

from src.autocomplete import AutoCompleteEngine
from src.index import InvertedIndex
from src.loader import Corpus

DEFAULT_CORPUS_ROOT = Path("Archive")
RESULT_LIMIT = 5


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

    query = st.text_input("Text to autocomplete")
    search_clicked = st.button("Search")

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
