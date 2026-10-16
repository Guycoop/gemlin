"""gemlin develop: the skill checks, trying a skill, and the workbench loop (with a fake Gemma)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemlin import core, develop, paths  # noqa: E402

GOOD = '''import os


def home_files(limit: int = 5) -> list:
    """List a few files in the home folder. Use this when the user asks what's in their home folder."""
    return sorted(os.listdir(os.path.expanduser("~")))[:limit]
'''


def skill(body, imports=""):
    return f'{imports}def look():\n    """Counts things. Use this when asked."""\n    {body}\n    return {{}}\n'


def test_a_good_skill_passes():
    assert develop.check(GOOD) == ("home_files", [], [])


@pytest.mark.parametrize("code, problem", [
    ("def x(:\n  pass", "valid Python"),
    ("def look():\n    return 1\n", "docstring"),
    ('def look():\n    """Counts things."""\n    return 1\n', "when to use it"),
    ('def look(path):\n    """Use this when asked."""\n    return 1\n', "default value"),
    (skill("pass", "import requests\n\n"), "standard library"),
    ("x = 1\n", "doesn't define a function"),
])
def test_rule_breaking_skills_are_caught(code, problem):
    _, problems, _ = develop.check(code)
    assert any(problem in p for p in problems), problems


@pytest.mark.parametrize("code, warning", [
    (skill("os.remove('x')", "import os\n\n"), "change things"),
    (skill("open('x', 'w')"), "writes to a file"),
    (skill("subprocess.run(['ls'])", "import subprocess\n\n"), "runs other programs"),
    (skill("urllib.request.urlopen('https://example.com')", "import urllib.request\n\n"), "internet"),
])
def test_risky_skills_get_a_heads_up(code, warning):
    _, problems, warnings = develop.check(code)
    assert not problems and any(warning in w for w in warnings), warnings


def test_trying_a_skill_runs_it_separately():
    worked, out = develop.try_it(GOOD, "home_files")
    assert worked and out.startswith("[")
    worked, out = develop.try_it('def boom():\n    """Use this when asked."""\n    return 1 / 0\n', "boom")
    assert not worked and "ZeroDivisionError" in out


def test_the_workbench_writes_fixes_and_saves(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "SKILLS", tmp_path / "skills")
    monkeypatch.setattr(core, "TRUSTED", tmp_path / "trusted")
    drafts = iter(["def nope():\n    return 1\n", GOOD])  # Gemma's first try breaks the rules, then it's fixed
    asked = []
    monkeypatch.setattr(develop, "write", lambda client, request, code=None, ran=None: asked.append(request) or next(drafts))
    typed = iter(["s", "c", "", "s"])  # save (refused: problems), change (Enter = fix them), save
    monkeypatch.setattr("builtins.input", lambda prompt="": next(typed))
    assert develop.session(brain=None, request="list my home files") == 0
    assert asked[1].startswith("Fix the problems above") and "docstring" in asked[1]
    assert (tmp_path / "skills" / "home_files.py").read_text() == GOOD
    assert core.fingerprint(GOOD) in (tmp_path / "trusted").read_text()  # you saved it, so it won't ask again
