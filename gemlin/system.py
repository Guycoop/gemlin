"""Gemlin and your operating system: the app you can click, waking up at login, opening files,
and updates. The `gemlin` command and the pet's menus both use these."""
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from contextlib import suppress
from pathlib import Path

from . import __version__, paths

LABEL = "dev.gemlin"
SOURCE = "https://github.com/alexinslc/gemlin/archive/refs/heads/main.zip"
LATEST = "https://raw.githubusercontent.com/alexinslc/gemlin/main/gemlin/__init__.py"
ICONS = paths.PACKAGE / "icons"


def python(windowless=True):
    """This same Python (so it finds this Gemlin). On Windows, pythonw: no console window pops up."""
    exe = Path(sys.executable)
    if windowless and sys.platform == "win32" and (exe.parent / "pythonw.exe").exists():
        exe = exe.parent / "pythonw.exe"
    return str(exe)


def command(*args):
    return [python(), "-m", "gemlin", *args]


def run_in_background(*args):
    """Run a gemlin command that should keep going after whoever asked for it stops (restart, update)."""
    if sys.platform == "win32":
        detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:
        detach = {"start_new_session": True}
    paths.HOME.mkdir(parents=True, exist_ok=True)
    with paths.LOG.open("a", encoding="utf-8") as log:
        subprocess.Popen(command(*args), cwd=paths.launch_dir(), stdin=subprocess.DEVNULL, stdout=log,
                         stderr=subprocess.STDOUT, **detach)


def open_file(path):
    """Open a file the way double-clicking it would."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    elif sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 (it only exists on Windows)
    else:
        subprocess.Popen(["xdg-open", str(path)])


# ---------- waking up at login ----------

def autostart_file(home=None):
    home = home or Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    return home / ".config" / "autostart" / "gemlin.desktop"  # Linux; Windows uses the registry instead


def autostart_enabled(home=None):
    if sys.platform == "win32":
        import winreg
        with suppress(OSError), winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            winreg.QueryValueEx(key, "Gemlin")
            return True
        return False
    return autostart_file(home).exists()


def set_autostart(on, home=None):
    """Wake Gemlin up whenever you log in (or stop doing that)."""
    if sys.platform == "win32":
        import winreg
        run = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, "Gemlin", 0, winreg.REG_SZ, subprocess.list2cmdline(command("start")))
            else:
                with suppress(FileNotFoundError):
                    winreg.DeleteValue(key, "Gemlin")
        return
    path = autostart_file(home)
    if not on:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        import plistlib
        path.write_bytes(plistlib.dumps({"Label": LABEL, "ProgramArguments": command("start"), "RunAtLoad": True, "WorkingDirectory": paths.launch_dir(),
                                         "AbandonProcessGroup": True,  # Gemlin keeps running after start exits
                                         "StandardOutPath": str(paths.LOG), "StandardErrorPath": str(paths.LOG)}))
    else:
        path.write_text(desktop_entry("start"), encoding="utf-8")


# ---------- the app you can click ----------

def desktop_entry(action):
    return ("[Desktop Entry]\nType=Application\nName=Gemlin\nComment=A tiny AI creature that lives on your desktop\n"
            f"Exec={subprocess.list2cmdline(command(action))}\nPath={paths.launch_dir()}\nIcon=gemlin\nCategories=Utility;\n"
            "X-GNOME-Autostart-enabled=true\n")


def app_location(home=None):
    """Where the clickable Gemlin lives: Applications (Mac), the Start menu (Windows), the app launcher (Linux)."""
    home = home or Path.home()
    if sys.platform == "darwin":
        return home / "Applications" / "Gemlin.app"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", home)) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Gemlin.lnk"
    return home / ".local" / "share" / "applications" / "gemlin.desktop"


def install_app(home=None):
    """Add Gemlin to Applications / the Start menu / the app launcher. Opening it wakes Gemlin up
    (or, if it's already awake, opens its chat). Returns where it went."""
    home = home or Path.home()
    where = app_location(home)
    if sys.platform == "darwin":
        import plistlib
        contents = where / "Contents"
        (contents / "MacOS").mkdir(parents=True, exist_ok=True)
        (contents / "Resources").mkdir(parents=True, exist_ok=True)
        (contents / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleName": "Gemlin", "CFBundleDisplayName": "Gemlin", "CFBundleIdentifier": f"{LABEL}.app",
            "CFBundleExecutable": "Gemlin", "CFBundleIconFile": "Gemlin", "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": __version__, "LSUIElement": True,  # no Dock icon: Gemlin lives in the menu bar
        }))
        launcher = contents / "MacOS" / "Gemlin"
        launcher.write_text(f'#!/bin/sh\ncd "{paths.launch_dir()}"\nexec "{python()}" -m gemlin show\n', encoding="utf-8")
        launcher.chmod(0o755)
        shutil.copy(ICONS / "macos" / "Gemlin.icns", contents / "Resources" / "Gemlin.icns")
        register = Path("/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/"
                        "Support/lsregister")
        if register.exists():  # so Spotlight and Launchpad find it right away
            subprocess.run([str(register), "-f", str(where)], capture_output=True)
    elif sys.platform == "win32":
        where.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", shortcut_script(where)],
                       capture_output=True, text=True, check=True)
    else:
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_text(desktop_entry("show"), encoding="utf-8")
        icons = home / ".local" / "share" / "icons" / "hicolor"
        for icon in (ICONS / "linux" / "hicolor").rglob("*.*"):
            target = icons / icon.relative_to(ICONS / "linux" / "hicolor")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(icon, target)
    return where


def shortcut_script(where):
    """PowerShell that makes the Start menu shortcut. (-Command doesn't pass extra arguments to the
    script, so the paths go inside it, in single quotes, where only ' needs escaping.)"""
    def quoted(text):
        return "'" + str(text).replace("'", "''") + "'"
    return (f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({quoted(where)}); "
            f"$s.TargetPath = {quoted(python())}; $s.Arguments = '-m gemlin show'; "
            f"$s.WorkingDirectory = {quoted(paths.launch_dir())}; "
            f"$s.IconLocation = {quoted(ICONS / 'windows' / 'Gemlin.ico')}; $s.Description = 'Gemlin'; $s.Save()")


def remove_app(home=None):
    where = app_location(home)
    if where.is_dir():
        shutil.rmtree(where)
    else:
        where.unlink(missing_ok=True)


# ---------- updates ----------

def installed_from_source():
    """True if this Gemlin runs from a git checkout (pip install -e .) rather than the installer."""
    return (paths.PACKAGE.parent / ".git").exists()


def latest_version(timeout=6):
    """The version on GitHub, or None if it couldn't be checked."""
    with suppress(OSError, ValueError):
        with urllib.request.urlopen(LATEST, timeout=timeout) as page:
            found = re.search(r'__version__ = "([^"]+)"', page.read().decode("utf-8"))
            return found.group(1) if found else None
    return None


def newer(remote, local=__version__):
    def parts(version):
        return tuple(int(n) for n in re.findall(r"\d+", version))
    return parts(remote) > parts(local)


def find_uv():
    found = shutil.which("uv")
    if found:
        return found
    home = Path.home() / ".local" / "bin"
    for name in ("uv.exe", "uv") if sys.platform == "win32" else ("uv",):
        if (home / name).exists():
            return str(home / name)
    return None
