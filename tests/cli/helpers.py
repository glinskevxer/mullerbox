from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner, Result

from mullerbox.cli.main import main


def run(*args: str, book: Path | str | None = None) -> Result:
    """Invoke the CLI against a book, returning the click result."""
    runner = CliRunner()
    prefix = [] if book is None else ["--book", str(book)]
    return runner.invoke(main, [*prefix, *args])


def initialised(tmp_path: Path) -> Path:
    """A book that exists and is migrated."""
    target = tmp_path / "shop.sqlite3"
    result = run("init", book=target)
    assert result.exit_code == 0, result.output
    return target
