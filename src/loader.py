"""Corpus loading and line-ID assignment."""

from collections.abc import Iterator
from pathlib import Path

from src.models import SentenceData
from src.normalizer import normalize


class Corpus:
    """A normalized text corpus ordered by the shared line-ID contract."""

    alphabet: str

    def __init__(
        self,
        originals: tuple[str, ...],
        normalized_sentences: tuple[str, ...],
        sources: tuple[str, ...],
        offsets: tuple[int, ...],
        alphabet: str,
    ) -> None:
        self._originals = originals
        self._normalized_sentences = normalized_sentences
        self._sources = sources
        self._offsets = offsets
        self.alphabet = alphabet

    @classmethod
    def load(cls, root: Path) -> "Corpus":
        """Recursively load non-empty normalized lines from ``root``."""
        root = Path(root)
        records: list[tuple[str, str, str, int]] = []
        alphabet_characters: set[str] = set()

        text_files = sorted(
            (path for path in root.rglob("*.txt") if path.is_file()),
            key=lambda path: path.relative_to(root).as_posix(),
        )
        for path in text_files:
            source_text = path.relative_to(root).as_posix()
            with path.open("r", encoding="utf-8", errors="replace", newline="") as file:
                for offset, physical_line in enumerate(file, start=1):
                    original_sentence = _without_line_terminator(physical_line)
                    normalized_sentence = normalize(original_sentence)
                    if normalized_sentence:
                        alphabet_characters.update(normalized_sentence)
                        records.append(
                            (
                                original_sentence,
                                normalized_sentence,
                                source_text,
                                offset,
                            )
                        )

        records.sort(key=lambda record: (record[0].casefold(), record[2], record[3]))
        originals = tuple(record[0] for record in records)
        normalized_sentences = tuple(record[1] for record in records)
        sources = tuple(record[2] for record in records)
        offsets = tuple(record[3] for record in records)
        alphabet = "".join(sorted(alphabet_characters))

        return cls(originals, normalized_sentences, sources, offsets, alphabet)

    def __len__(self) -> int:
        return len(self._originals)

    def __getitem__(self, line_id: int) -> SentenceData:
        return SentenceData(
            original_sentence=self._originals[line_id],
            normalized_sentence=self._normalized_sentences[line_id],
            source_text=self._sources[line_id],
            offset=self._offsets[line_id],
        )

    def normalized(self, line_id: int) -> str:
        return self._normalized_sentences[line_id]

    def __iter__(self) -> Iterator[SentenceData]:
        for line_id in range(len(self)):
            yield self[line_id]


def _without_line_terminator(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith(("\r", "\n")):
        return line[:-1]
    return line
