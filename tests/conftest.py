"""Every test gets its own Gemlin home, so nothing a test does (or starts) touches your ~/.gemlin.

The first line runs before any test file imports gemlin, because gemlin.paths decides where
~/.gemlin is when it's first imported."""
import os
import tempfile

os.environ["GEMLIN_HOME"] = tempfile.mkdtemp(prefix="gemlin-tests-")

import pytest  # noqa: E402

from gemlin import paths  # noqa: E402

assert paths.HOME == __import__("pathlib").Path(os.environ["GEMLIN_HOME"]), "tests must never use the real ~/.gemlin"


@pytest.fixture(autouse=True)
def gemlin_home(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMLIN_HOME", str(tmp_path / "gemlin-home"))
