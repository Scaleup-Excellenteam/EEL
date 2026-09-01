"""Additional tests for src/cli.py: explicit coverage of the two exceptions
`run()` treats as "end of input", which the existing test suite only ever
exercises indirectly (by draining an iterator that then raises StopIteration
of its own accord)."""

from src import cli


def test_eof_error_on_first_read_ends_the_loop_gracefully():
    output: list[str] = []

    def read() -> str:
        raise EOFError

    class UnusedEngine:
        def get_best_k_completions(self, prefix: str):
            raise AssertionError("engine should not be queried before any input")

    cli.run(UnusedEngine(), read=read, write=output.append)

    assert output == [cli.BANNER]


def test_stop_iteration_on_first_read_ends_the_loop_gracefully():
    output: list[str] = []

    def read() -> str:
        raise StopIteration

    class UnusedEngine:
        def get_best_k_completions(self, prefix: str):
            raise AssertionError("engine should not be queried before any input")

    cli.run(UnusedEngine(), read=read, write=output.append)

    assert output == [cli.BANNER]
