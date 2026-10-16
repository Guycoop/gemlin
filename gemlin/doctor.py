"""Diagnostic checks for Gemlin — a `gemlin doctor` command.

Prints clear, actionable checks and suggestions to help troubleshooting.
"""
from __future__ import annotations

import os
import sys
import textwrap
from contextlib import suppress

from . import paths

CHECKS = []


def _ok(msg):
    return f"  ✓ {msg}"


def _fail(msg):
    return f"  ✗ {msg}"


def _short(path):
    try:
        return os.path.relpath(path, start=os.path.expanduser("~"))
    except Exception:
        return str(path)


def doctor(args=None) -> int:
    """Run checks and print a summary. Return 0 when everything looks good, 1 otherwise."""
    problems = []
    print("Gemlin diagnostic checks\n")

    # Python version
    ok = sys.version_info >= (3, 10)
    print(_ok(f"Python {sys.version.split()[0]}") if ok else _fail(f"Python {sys.version.split()[0]} — Gemlin needs 3.10+"))
    if not ok:
        problems.append("upgrade_python")

    # Virtual environment (warn only)
    in_venv = (hasattr(sys, "real_prefix") or sys.prefix != getattr(sys, "base_prefix", sys.prefix))
    if in_venv:
        print(_ok("Running in a virtual environment"))
    else:
        print("  ? Not running inside a virtual environment — using one avoids system package issues.\n    Try: python3 -m venv .venv && source .venv/bin/activate")

    # Required Python packages
    def check_import(module, label, fix):
        try:
            __import__(module)
            print(_ok(label))
            return True
        except Exception:
            print(_fail(f"{label} is missing — {fix}"))
            problems.append(label)
            return False

    check_import("psutil", "psutil", "pip install -e . or pip install psutil")
    check_import("google.genai", "Gemini SDK (google-genai)", "pip install -e . or pip install google-genai")

    if sys.platform == "darwin":
        check_import("objc", "pyobjc (AppKit) for the see-through window on macOS",
                     "pip install -e . (mac only) or pip install pyobjc-framework-Cocoa")
    elif sys.platform == "win32":
        check_import("pystray", "pystray (Windows system tray)", "pip install pystray")
    else:
        # Linux: tkinter for the pet window
        try:
            import tkinter  # type: ignore
            print(_ok("tkinter (desktop window)"))
        except Exception:
            print(_fail("tkinter not available — sudo apt install python3-tk (Linux)"))
            problems.append("tkinter")

    # ~/.gemlin and config
    home = paths.HOME
    if home.exists():
        try:
            perms = oct(home.stat().st_mode & 0o777)
        except Exception:
            perms = "?"
        print(_ok(f"Gemlin home: ~/{_short(home)} ({perms})"))
    else:
        print(_fail(f"Gemlin home missing: ~/{_short(home)} — run gemlin setup or create it"))
        problems.append("home_missing")

    # API key
    try:
        key = paths.api_key()
    except Exception:
        key = None
    if key:
        print(_ok(f"API key saved in {paths.CONFIG} (hidden)"))
    else:
        print("  ? No API key saved. Run: gemlin setup  (or paste a key when asked)")

    # Local model server
    try:
        from . import models

        lms = models.lms_installed()
        server = models.find_server(start=False)
        if server:
            print(_ok(f"Local model server running: {server[0]} with {', '.join(server[2]) or 'no models yet'}"))
        else:
            if lms:
                print("  ? LM Studio / Ollama installed but no server running. Start it to use local models.")
            else:
                print("  ? No LM Studio or Ollama detected on this machine. Install LM Studio or Ollama to run models locally.")
    except Exception:
        print("  ? Could not check local model server (models module missing or errored).")

    # PID / running
    try:
        from . import cli
        proc = cli.running()
        if proc:
            print(_ok(f"Gemlin process running (PID {proc.pid})"))
        else:
            # stale PID file?
            if paths.PID.exists():
                print(_fail(f"Stale PID file {paths.PID}; Gemlin not running. Remove the file and try gemlin start"))
                problems.append("stale_pid")
            else:
                print(_ok("Gemlin not running (that's fine unless you expected it to be)"))
    except Exception:
        print("  ? Couldn't determine Gemlin running status")

    # Last log lines if log exists
    if paths.LOG.exists():
        try:
            lines = paths.LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            print("\nLast log lines:")
            for line in lines[-8:]:
                print("  " + line)
        except Exception:
            print("  ? Couldn't read the log file")

    # Summary
    print("\nSummary:")
    if problems:
        print(_fail(f"{len(problems)} problem(s) found — see above for fixes"))
        print(textwrap.dedent("""
            Suggested next steps:
              - Run: gemlin doctor  (this command) to see details
              - Run: gemlin setup   to check parts and save an API key
              - If Python packages are missing, run from the project folder:
                  python3 -m venv .venv && source .venv/bin/activate
                  pip install -e .
            """))
        return 1
    print(_ok("No obvious problems detected."))
    return 0
