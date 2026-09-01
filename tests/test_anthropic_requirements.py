"""Tests asserting the project's dependency on the Anthropic Claude API.

Checks that the codebase imports/uses the Anthropic SDK somewhere, and that
an ANTHROPIC_API_KEY is declared in the project's environment/config
handling somewhere.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories whose contents are not part of the shipped codebase.
_EXCLUDED_DIR_NAMES = {
    ".git",
    "tests",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    "Archive",
}

# Only text-like files are worth scanning.
_TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".json",
    ".yml",
    ".yaml",
    ".sh",
}


def _project_text() -> str:
    """Concatenated contents of every text-like file in the shipped codebase
    (excluding the test suite itself, so a test can't satisfy itself)."""
    chunks: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _EXCLUDED_DIR_NAMES for part in path.relative_to(REPO_ROOT).parts):
            continue
        if path.suffix not in _TEXT_SUFFIXES:
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def test_uses_anthropic_api():
    """The project must import or call the Anthropic/Claude SDK somewhere —
    e.g. the `anthropic` Python package, `@anthropic-ai/sdk`, or a direct
    call to the Anthropic API."""
    text = _project_text().lower()

    assert "anthropic" in text or "@anthropic-ai/sdk" in text, (
        "no reference to the Anthropic SDK/API was found anywhere in the "
        "project's source or dependency files"
    )


def test_declares_anthropic_api_key():
    """The project must declare/require an ANTHROPIC_API_KEY somewhere in its
    configuration or environment-variable handling."""
    text = _project_text()

    assert "ANTHROPIC_API_KEY" in text, (
        "no ANTHROPIC_API_KEY declaration was found anywhere in the "
        "project's source, config, or env-handling files"
    )
