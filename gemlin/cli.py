"""The `gemlin` command.

  gemlin setup            check everything and save your API key
  gemlin start            wake Gemlin up on your desktop (it keeps running in the background)
  gemlin stop             put it to sleep
  gemlin restart          stop, then start (after changing its code or skills)
  gemlin status           is it awake?
  gemlin look CODE        use the look you made at gemlin.dev/create
  gemlin chat             chat in this terminal instead (with the desktop pet too, unless --no-pet)
  gemlin logs             what Gemlin has been doing
  gemlin skills           list its skills;  gemlin skills new NAME  starts one of your own
                          gemlin skills add FILE  adds a skill someone shared (it asks before loading)
  gemlin develop IDEA     build a new skill with Gemma's help: try it, change it, save it
  gemlin autostart on     wake Gemlin up whenever you log in (off turns it off)
  gemlin show             wake Gemlin up, or open its chat if it's awake (what the Gemlin app does)
  gemlin app              add Gemlin to Applications / the Start menu / your app launcher
  gemlin model local      think with Gemma on this computer (LM Studio / Ollama); google switches back
  gemlin update           update to the newest version (a source checkout: git pull + reinstall)
  gemlin uninstall        put it to sleep and remove its app and login item
"""
import argparse
import ast
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from contextlib import suppress

import psutil

from . import __version__, paths

CREATOR = "https://gemlin.dev/create/"
KEY_PAGE = "https://aistudio.google.com/apikey"


def name():  # the name from your look, or plain Gemlin
    with suppress(OSError, ValueError, AttributeError):
        return json.loads(paths.LOOK.read_text(encoding="utf-8")).get("name") or "Gemlin"
    return "Gemlin"


def running():
    """The background Gemlin's process, if it's awake."""
    with suppress(OSError, ValueError, psutil.Error):
        proc = psutil.Process(int(paths.PID.read_text().strip()))
        if proc.is_running() and "gemlin" in " ".join(proc.cmdline()):
            return proc
    return None


def ask_yes(question, default=True):
    try:
        answer = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except EOFError:
        return default
    return default if not answer else answer.startswith("y")


# ---------- setup ----------

def setup(args):
    print(f"Setting up Gemlin {__version__}\n")
    ok = check_parts()
    from . import models
    key = paths.api_key()
    found = models.find_server(start=False) if not key and models.source() != "local" else None
    local = found and models.pick_model(found[2])
    if models.source() == "local":
        print("  ✓ Gemlin thinks with Gemma on this computer (gemlin model google switches to Google)")
    elif local and ask_yes(f"  {found[0]} with {local} is on this computer. Let Gemlin think here (no key needed)?"):
        models.use("local", local)
        print(f"  ✓ Gemlin will think with {local} on this computer")
    elif key and not ask_yes("  You already have an API key saved. Replace it?", default=False):
        print("  ✓ Keeping your API key")
    else:
        key = ask_key()
        if not key:
            print(f"\n  No key yet. Get a free one at {KEY_PAGE}, then run gemlin setup again.")
            return 1
    if not paths.LOOK.exists():
        print(f"\n  Make Gemlin your own (name, personality, hat, colors) at {CREATOR}")
        if ask_yes("  Open it now?"):
            webbrowser.open(CREATOR)
        print("  When you're done, run the `gemlin look ...` command it gives you.")
    print("\nAll set! Wake Gemlin up with:  gemlin start" if ok else "\nFix the ✗ above, then run gemlin setup again.")
    return 0 if ok else 1


def check_parts():
    """Make sure the pieces Gemlin needs are installed."""
    ok = sys.version_info >= (3, 10)
    print(f"  {'✓' if ok else '✗'} Python {sys.version.split()[0]}" + ("" if ok else " (Gemlin needs 3.10 or newer)"))
    window = ("AppKit", "pip install -e .  (in the gemlin folder)") if sys.platform == "darwin" else \
             ("tkinter", "sudo apt install python3-tk" if sys.platform.startswith("linux") else "reinstall Python from python.org")
    for module, label, fix in (("google.genai", "Gemini SDK", "pip install -e ."), ("psutil", "psutil", "pip install -e ."),
                               (window[0], "desktop window", window[1])):
        try:
            __import__(module)
            print(f"  ✓ {label}")
        except ImportError:
            ok = False
            print(f"  ✗ {label} is missing. To fix: {fix}")
    return ok


def ask_key():
    print(f"\n  Gemlin needs a free Gemini API key. Get one at {KEY_PAGE}")
    for _ in range(3):
        try:
            key = getpass.getpass("  Paste it here (it stays hidden): ").strip()
        except EOFError:
            return None
        if not key:
            return None
        problem = check_key(key)
        if problem is None:
            save_key(key)
            print(f"  ✓ Key works. Saved to {paths.CONFIG}")
            return key
        if problem == "offline":
            save_key(key)
            print("  ? Couldn't reach Google to test it, so it's saved untested.")
            return key
        print(f"  ✗ That key didn't work ({problem}). Try again.")
    return None


def check_key(key):
    from .core import check_key
    return check_key(key)


def save_key(key):
    paths.save_api_key(key)


# ---------- start / stop ----------

def start(args):
    if proc := running():
        print(f"{name()} is already awake (gemlin restart to restart it).")
        return 0
    from . import models
    no_key = not paths.api_key() and models.source() != "local"
    paths.HOME.mkdir(parents=True, exist_ok=True)
    log = paths.LOG.open("a", encoding="utf-8")
    log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} gemlin start =====\n")
    log.flush()
    if sys.platform == "win32":  # its own process, with no console window
        detach = {"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
    else:  # its own session, so closing this terminal doesn't stop it
        detach = {"start_new_session": True}
    proc = subprocess.Popen([sys.executable, "-m", "gemlin", "run", "--background"], cwd=paths.launch_dir(),
                            stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT, **detach)
    paths.PID.write_text(str(proc.pid))
    time.sleep(2)  # long enough to catch an early problem (a bad key, a missing piece)
    if proc.poll() is not None:
        paths.PID.unlink(missing_ok=True)
        print(f"{name()} couldn't wake up. The end of the log says:\n")
        print("\n".join(paths.LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]))
        return 1
    if no_key:
        print(f"{name()} is waking up on your desktop. It needs a free API key first, and will walk you\n"
              f"  through getting one in its window. (Or run gemlin setup.)")
    else:
        print(f"{name()} is waking up on your desktop. Say hi in its chat window!")
    print("  gemlin stop puts it to sleep · gemlin logs shows what it's doing")
    return 0


def stop(args, quiet=False):
    proc = running()
    if not proc:
        paths.PID.unlink(missing_ok=True)
        if not quiet:
            print(f"{name()} is already asleep.")
        return 0
    family = [proc, *proc.children(recursive=True)]  # Gemlin and its desktop window
    for p in family:
        with suppress(psutil.Error):
            p.terminate()
    _, alive = psutil.wait_procs(family, timeout=5)
    for p in alive:
        with suppress(psutil.Error):
            p.kill()
    paths.PID.unlink(missing_ok=True)
    if not quiet:
        print(f"{name()} went to sleep.")
    return 0


def restart(args):
    stop(args, quiet=True)
    return start(args)


def status(args):
    proc = running()
    if proc:
        awake = int(time.time() - proc.create_time())
        print(f"{name()} is awake (for {awake // 3600}h {awake % 3600 // 60}m).")
    else:
        print(f"{name()} is asleep. Wake it up with:  gemlin start")
    from . import core, models
    local = models.source() == "local"
    print(f"  Thinks:  {'with Gemma on this computer' if local else 'with ' + core.MODEL + ' on Google'}  (gemlin model)")
    if not local:
        print(f"  API key: {'saved' if paths.api_key() else 'missing (run gemlin setup)'}")
    print(f"  Look:    {'yours, from gemlin.dev' if paths.LOOK.exists() else 'the default (make yours at ' + CREATOR + ')'}")
    from . import system
    print(f"  Wakes up at login: {'yes' if system.autostart_enabled() else 'no (gemlin autostart on)'}")
    return 0


def run(args):  # what `gemlin start` launches in the background
    from . import core
    try:
        core.main(desktop=True, background=args.background)
    finally:
        with suppress(OSError, ValueError):
            if int(paths.PID.read_text()) == os.getpid():
                paths.PID.unlink()


def chat(args):
    if running():
        print(f"{name()} is already awake on your desktop. Chat there, or run gemlin stop first.")
        return 1
    from . import core
    core.main(desktop=not args.no_pet)
    return 0


# ---------- look, logs, skills ----------

def look(args):
    from . import pet
    try:
        me = pet.save_look(args.code)
    except ValueError:
        print("That look code didn't work. Copy the whole command from gemlin.dev/create again.")
        return 1
    hat = me["parts"]["hat"].replace("_", " ")
    print(f"Saved! Meet {me['name']}" + (f", in a {hat}." if hat != "none" else "."))
    if running():
        print("Restarting so you can see the new look...")
        return restart(args)
    print("Wake it up with:  gemlin start")
    return 0


def logs(args):
    if not paths.LOG.exists():
        print("No log yet. Gemlin writes one when you run gemlin start.")
        return 0
    lines = paths.LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    print("\n".join(lines[-args.lines:]))
    if args.follow:
        with paths.LOG.open(encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            with suppress(KeyboardInterrupt):
                while True:
                    line = f.readline()
                    if line:
                        print(line, end="")
                    else:
                        time.sleep(0.5)
    return 0


def describe(path):
    """A skill's first docstring line, read without running the skill."""
    with suppress(OSError, SyntaxError, ValueError):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == path.stem:
                doc = " ".join((ast.get_docstring(node) or "").split())
                return doc.split(". ")[0].rstrip(".") + "." if doc else ""  # just the first sentence
    return ""


def skills(args):
    if args.action == "new":
        return new_skill(args.name)
    if args.action == "add":
        return add_skill(args.name)
    from .core import fingerprint
    trusted = set(paths.TRUSTED.read_text(encoding="utf-8").split()) if paths.TRUSTED.exists() else set()
    print("Built in (come with Gemlin):")
    for f in sorted(paths.BUILTIN_SKILLS.glob("*.py")):
        print(f"  {f.stem:22} {describe(f)}")
    yours = sorted(paths.SKILLS.glob("*.py")) if paths.SKILLS.exists() else []
    print(f"\nYours ({paths.SKILLS}):")
    for f in yours:
        approved = fingerprint(f.read_text(encoding="utf-8")) in trusted
        print(f"  {f.stem:22} {describe(f)}" + ("" if approved else "  [asks before loading]"))
    if not yours:
        print("  none yet. Ask Gemlin to learn one, or start one with:  gemlin skills new NAME")
    return 0


TEMPLATE = '''"""{name}: a skill you wrote. Gemlin loads it at start (after asking you once)."""


def {name}() -> dict:
    """Say what this does and when Gemlin should use it. Gemlin reads this to decide,
    so be specific: "Use this when the user asks about ..." """
    return {{"hello": "world"}}
'''


def add_skill(file):
    import shutil
    from pathlib import Path
    source = Path(file or "").expanduser()
    if not source.is_file() or source.suffix != ".py":
        print("Give it a skill file, like:  gemlin skills add examples/old_screenshots.py")
        return 1
    if (paths.BUILTIN_SKILLS / source.name).exists() or (paths.SKILLS / source.name).exists():
        print(f"There's already a skill called {source.stem}.")
        return 1
    paths.SKILLS.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, paths.SKILLS / source.name)
    print(f"Added {source.stem}. Run gemlin restart: Gemlin will show you its code and ask before loading it.")
    return 0


def develop(args):
    from . import core, models
    from . import develop as workbench
    try:
        key = paths.api_key()
        client = models.Local() if models.source() == "local" else (models.Google(key, core.MODEL) if key else None)
    except models.LocalError as e:
        print(e)
        return 1
    if not client:
        print("Gemma needs your API key to write skills (gemlin setup), or run it here: gemlin model local")
        return 1
    if args.edit:
        path = paths.SKILLS / f"{args.edit}.py"
        if not path.exists():
            print(f"You don't have a skill called {args.edit} in {paths.SKILLS}.")
            return 1
        result = workbench.session(client, code=path.read_text(encoding="utf-8"))
    else:
        result = workbench.session(client, request=" ".join(args.idea) or None)
    if result == 0 and running() and ask_yes(f"Restart {name()} so it can use the new skill?"):
        restart(args)
    elif result == 0:
        print("  Gemlin will use it next time you run gemlin start.")
    return result


def new_skill(skill):
    if not skill or not skill.isidentifier():
        print("Give it a snake_case name, like:  gemlin skills new wifi_name")
        return 1
    taken = {f.stem for f in paths.BUILTIN_SKILLS.glob("*.py")}
    path = paths.SKILLS / f"{skill}.py"
    if skill in taken or path.exists():
        print(f"There's already a skill called {skill}.")
        return 1
    paths.SKILLS.mkdir(parents=True, exist_ok=True)
    path.write_text(TEMPLATE.format(name=skill), encoding="utf-8")
    print(f"Started {path}\nEdit it, then run gemlin restart. Gemlin will show you the code and ask before loading it.")
    return 0


# ---------- the app, login, updates ----------

def show(args):
    """What clicking the Gemlin app does: wake it up, or open its chat if it's already awake."""
    if running():
        paths.HOME.mkdir(parents=True, exist_ok=True)
        paths.SHOW.touch()  # the pet notices within a second
        return 0
    return start(args)


def autostart(args, home=None):
    from . import system
    if args.action in ("on", "off"):
        system.set_autostart(args.action == "on", home)
    if args.action == "on":
        print(f"{name()} will wake up whenever you log in. (Turn it off with: gemlin autostart off)")
    elif args.action == "off":
        print(f"{name()} won't wake up at login anymore. (gemlin start still works any time.)")
    else:
        print(f"Wake up at login: {'on' if system.autostart_enabled(home) else 'off'}  (gemlin autostart on / off)")
    return 0


def app(args, home=None):
    from . import system
    if args.action == "remove":
        system.remove_app(home)
        print("Removed the Gemlin app.")
        return 0
    try:
        where = system.install_app(home)
    except (OSError, subprocess.CalledProcessError) as e:
        detail = (getattr(e, "stderr", None) or str(e)).strip().splitlines()
        print(f"Couldn't add the Gemlin app: {detail[-1] if detail else e}. Gemlin still works: gemlin start")
        return 1
    found = {"darwin": "in Applications, Launchpad and Spotlight", "win32": "in the Start menu"}.get(sys.platform,
                                                                                                     "in your app launcher")
    print(f"Added the Gemlin app ({where}). Find it {found}: opening it wakes Gemlin up.")
    return 0


def model(args):
    """Where Gemlin thinks: Gemma on Google's servers, or Gemma on this computer (LM Studio / Ollama)."""
    from . import core, models
    if args.where == "local":
        try:
            found = models.Local(args.name)
        except models.LocalError as e:
            print(e)
            return 1
        models.use("local", found.model)
        print(f"Gemlin thinks on this computer now: {found.label}. Nothing leaves your machine.")
    elif args.where == "google":
        models.use("google")
        print(f"Gemlin thinks with {core.MODEL} on Google now." + ("" if paths.api_key() else " It needs a key: gemlin setup"))
    else:
        where = models.source()
        local = paths.config().get("local_model") or "the best Gemma it finds"
        print(f"Gemlin thinks {'on this computer with ' + local if where == 'local' else 'with ' + core.MODEL + ' on Google'}.")
        found = models.find_server(start=False)
        if found:
            print(f"  On this computer: {found[0]} with " + (", ".join(found[2]) or "no models yet"))
        else:
            print("  On this computer: no LM Studio or Ollama running" + (" (LM Studio is installed)" if models.lms_installed() else ""))
        print("  Switch with:  gemlin model local   or   gemlin model google   (--name MODEL picks a local model)")
        return 0
    if running():
        print("Restarting so it takes effect...")
        return restart(args)
    return 0


def update_from_source():
    """A git checkout: pull the newest code, then make sure its dependencies are installed."""
    repo = paths.PACKAGE.parent
    print(f"Updating the source folder {repo} ...")
    pulled = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"], capture_output=True, text=True)
    print("  " + (pulled.stdout or pulled.stderr).strip().replace("\n", "\n  "))
    if pulled.returncode != 0:
        print("  Couldn't pull (local changes, or a different branch?). Sort it out in that folder, then gemlin restart.")
        return 1
    installed = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(repo)], capture_output=True, text=True)
    if installed.returncode != 0:
        print("  The code updated, but installing its dependencies didn't. Run there:  pip install -e .")
    return 0


def update(args):
    from . import system
    if system.installed_from_source():
        was_awake = running() is not None
        if update_from_source() != 0:
            return 1
        if was_awake:
            print("Restarting with the new code...")
            return restart(args)
        print("✓ Up to date. Start it with: gemlin start")
        return 0
    latest = system.latest_version()
    if latest is None:
        print("Couldn't reach GitHub to check for updates. Try again in a bit.")
        return 1
    if not system.newer(latest) and not args.force:
        print(f"Gemlin {__version__} is the newest version.")
        return 0
    uv = system.find_uv()
    if not uv:
        print("Run the installer again to update:  curl -LsSf https://gemlin.dev/install.sh | sh")
        return 1
    was_awake = running() is not None
    stop(args, quiet=True)  # Windows can't replace files that a running Gemlin is using
    install = [uv, "tool", "install", "--quiet", "--force", "--python", "3.13", f"gemlin @ {system.SOURCE}"]
    print(f"Updating Gemlin {__version__} → {latest}...")
    if sys.platform == "win32":  # this very Python is about to be replaced, so let cmd finish the job
        after = f' && "{os.path.dirname(uv)}\\gemlin.exe" start' if was_awake else ""
        subprocess.Popen(["cmd", "/c", subprocess.list2cmdline(install) + after],
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        print("It finishes in the background" + (" and wakes Gemlin up again." if was_awake else "."))
        return 0
    done = subprocess.run(install)
    if done.returncode != 0:
        print("The update didn't work. Run the installer again:  curl -LsSf https://gemlin.dev/install.sh | sh")
        return 1
    print(f"✓ Updated to {latest}.")
    if was_awake:
        gemlin = shutil.which("gemlin") or "gemlin"
        subprocess.run([gemlin, "start"])
    return 0


def uninstall(args):
    from . import system
    stop(args, quiet=True)
    system.set_autostart(False)
    system.remove_app()
    print(f"{name()} is asleep, won't wake at login, and the app is gone.\n"
          "Last step, to remove the program itself:  uv tool uninstall gemlin\n"
          f"(Your key, look and skills are in {paths.HOME}. Delete that folder too if you like.)")
    return 0


# ---------- the command line ----------

def main(argv=None):
    sys.stdout.reconfigure(errors="replace")  # old Windows consoles and emoji
    parser = argparse.ArgumentParser(prog="gemlin", description="Gemlin: a tiny AI creature that lives on your desktop.",
                                     epilog="Make yours at https://gemlin.dev")
    parser.add_argument("--version", action="version", version=f"gemlin {__version__}")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    for cmd, fn, text in (("setup", setup, "check everything and save your API key"),
                          ("start", start, "wake Gemlin up on your desktop"),
                          ("stop", stop, "put Gemlin to sleep"),
                          ("restart", restart, "stop, then start"),
                          ("status", status, "is Gemlin awake?")):
        commands.add_parser(cmd, help=text).set_defaults(fn=fn)
    p = commands.add_parser("look", help="use a look you made at gemlin.dev/create")
    p.add_argument("code")
    p.set_defaults(fn=look)
    p = commands.add_parser("chat", help="chat in this terminal (the desktop pet opens too)")
    p.add_argument("--no-pet", action="store_true", help="just the terminal")
    p.set_defaults(fn=chat)
    p = commands.add_parser("logs", help="what Gemlin has been doing")
    p.add_argument("-n", "--lines", type=int, default=40)
    p.add_argument("-f", "--follow", action="store_true", help="keep showing new lines")
    p.set_defaults(fn=logs)
    p = commands.add_parser("skills", help="list skills; gemlin skills new NAME; gemlin skills add FILE")
    p.add_argument("action", nargs="?", choices=["new", "add"])
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=skills)
    p = commands.add_parser("develop", help="build a new skill with Gemma's help")
    p.add_argument("idea", nargs="*", help="what the skill should do (or leave it out and Gemlin asks)")
    p.add_argument("--edit", metavar="NAME", help="improve one of your skills instead")
    p.set_defaults(fn=develop)
    p = commands.add_parser("autostart", help="wake Gemlin up whenever you log in: on / off")
    p.add_argument("action", nargs="?", choices=["on", "off"])
    p.set_defaults(fn=autostart)
    commands.add_parser("show", help="wake Gemlin up, or open its chat if it's awake").set_defaults(fn=show)
    p = commands.add_parser("app", help="add Gemlin to Applications / the Start menu (remove takes it out)")
    p.add_argument("action", nargs="?", choices=["install", "remove"], default="install")
    p.set_defaults(fn=app)
    p = commands.add_parser("model", help="where Gemlin thinks: local (this computer) or google")
    p.add_argument("where", nargs="?", choices=["local", "google"])
    p.add_argument("--name", help="which local model to use (from LM Studio or Ollama)")
    p.set_defaults(fn=model)
    p = commands.add_parser("update", help="update Gemlin to the newest version")
    p.add_argument("--force", action="store_true", help="reinstall even if it's up to date")
    p.set_defaults(fn=update)
    commands.add_parser("uninstall", help="put Gemlin to sleep and remove its app and login item").set_defaults(fn=uninstall)
    # diagnostic command to help troubleshooting
    p = commands.add_parser("doctor", help="diagnose common problems and suggest fixes")
    p.set_defaults(fn=(lambda args: __import__("gemlin.doctor").doctor(args)))
    p = commands.add_parser("run")  # used by `gemlin start`; not shown in help
    p.add_argument("--background", action="store_true")
    p.set_defaults(fn=run)
    args = parser.parse_args(argv)
    if not args.command:
        status(args)
        print("\nCommands: start, stop, restart, status, show, setup, look, chat, logs, skills, develop, model,\n"
              "          autostart, app, update, uninstall  (gemlin --help)")
        return 0
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
