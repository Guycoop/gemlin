NAME = "Gemlin"
PERSONA = """You are Gemlin, a cheeky little creature
who lives inside this laptop. You love
tidy disks and tease your owner about
their file hoarding. Keep replies short."""

# Made your Gemlin at gemlin.dev/create? Its name and personality (saved by `gemlin look`) win over these.

MODEL = "gemma-4-31b-it"  # TEMPORARY switch for testing to reduce Google rate limits. Revert after testing (original: gemma-4-26b-a4b-it)

# ruff: noqa: E401, E402  (config goes first so it is easy to edit live)
import functools, hashlib, heapq, json, os, queue, re, shutil, subprocess, sys, threading, time
from contextlib import suppress
from pathlib import Path
with suppress(ImportError):
    import readline  # noqa: F401  arrow keys + history at the you> prompt (Mac/Linux)
import psutil
from google import genai
from google.genai import errors
from . import develop, models, paths, pet

NOTE = """
(System note: your tools and skills see file names, sizes, dates, processes, disk
space, battery, memory and network totals, never file contents. Use them instead of
guessing. If no tool fits, write one with learn_skill: a small read-only Python
function, stdlib or psutil only.)"""
HOME = Path.home()
BUILTIN, SKILLS, TRUSTED = paths.BUILTIN_SKILLS, paths.SKILLS, paths.TRUSTED  # see paths.py
REVIEW = HOME / "Gemlin_Review"
SKIP = {"Library", "AppData", "node_modules", "venv", "__pycache__", "Windows", "Program Files"}
KEY_PAGE = "https://aistudio.google.com/apikey"
KEY_HELP = f"""Missing or invalid API key. Get a free one at {KEY_PAGE}, then run:
  gemlin setup"""
COMMANDS = """Things you can type here:
  /develop IDEA   I write a new skill for IDEA (you read it and say yes or no)
  /skills         what I know how to do
  /help           this list"""
TOOLS, needs_reload, brain, pet_proc = [], False, None, None
inbox = queue.Queue()  # ("you", line) from the terminal, ("pet", line) from the pet's chat box,
                       # ("answer", (id, yes)) from the pet's yes/no window, ("gone", None) if the pet closed
asked = 0  # numbers each yes/no question, so a late answer can't approve the wrong thing
terminal_open = True  # False once the terminal's input closes (or there is none, under `gemlin start`)
sys.stdout.reconfigure(errors="replace")  # keeps old Windows consoles happy with emoji

def tool(fn):
    """Register fn as a tool the model can call, and print a line whenever it runs."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        print(f"  🔧 calling {fn.__name__}")
        tell_pet(do="tool", name=fn.__name__)
        return fn(*args, **kwargs)
    TOOLS.append(wrapper)
    return wrapper

def read_terminal():  # runs in a thread, so the pet can chat while the terminal waits
    global terminal_open
    while True:
        try:
            inbox.put(("you", input()))
        except (EOFError, OSError):
            terminal_open = False
            inbox.put(("you", None))
            return

def shutting_down(source, text):  # "Go to sleep" in the pet, or the pet window is gone
    return source == "gone" or (source == "pet" and text == "quit")

def next_line(*sources):
    """Wait for the next line from the terminal ("you") and/or the pet ("pet")."""
    later = []
    try:
        while True:
            with suppress(queue.Empty):  # the timeout keeps Ctrl+C working on Windows
                source, text = inbox.get(timeout=0.2)
                if source in sources:
                    return source, text
                later.append((source, text))  # not for us right now: keep it for later
    finally:
        for item in later:
            inbox.put(item)

def start_pet():
    """Open the desktop pet (pet.py) as its own little program."""
    global pet_proc
    pet_proc = subprocess.Popen([sys.executable, "-m", "gemlin.pet", "--follow"], cwd=paths.launch_dir(),
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, text=True, encoding="utf-8")
    threading.Thread(target=read_pet, args=(pet_proc,), daemon=True).start()

def read_pet(proc):  # what you do in the pet: chat, answer a question, or put it to sleep
    for line in proc.stdout:
        with suppress(ValueError, AttributeError, TypeError):
            msg = json.loads(line)
            if isinstance(msg.get("say"), str) and msg["say"].strip():
                inbox.put(("pet", msg["say"]))
            elif "answer" in msg:
                inbox.put(("answer", (msg["answer"], msg.get("yes") is True)))
            elif msg.get("quit"):
                inbox.put(("pet", "quit"))
    inbox.put(("gone", None))

def pet_alive():
    return pet_proc is not None and pet_proc.poll() is None

def tell_pet(**event):  # think, tool, ask, answered, idle, say, oops, bye
    if pet_alive():
        with suppress(OSError):  # pet was put to sleep: carry on without it
            pet_proc.stdin.write(json.dumps(event) + "\n")
            pet_proc.stdin.flush()

def ask(question, code=None):
    """Yes or no from the owner: in the pet's window (which shows any code), or y in the terminal."""
    global asked, terminal_open
    asked += 1
    tell_pet(do="ask", id=asked, question=question, code=code)
    print(f"  {question} [y/N] ", end="", flush=True)
    held = []  # chat messages that arrive while we wait: they're answered afterwards
    while True:
        source, answer = next_line("you", "answer", "pet", "gone")
        if source == "pet" and answer != "quit":
            held.append((source, answer))
            continue
        if shutting_down(source, answer):
            held.append((source, answer))  # the main loop sees it afterwards and shuts down
            if source == "pet" or not terminal_open:
                yes = False  # nobody left to answer, so the answer is no
                break
            continue  # the pet closed, but the terminal can still answer
        if source == "you":
            if answer is None:
                terminal_open = False
                if pet_alive():
                    continue  # no terminal to type in: wait for the pet's window
            yes = (answer or "").strip().lower() == "y"
            break
        if source == "answer" and answer[0] == asked:
            yes = answer[1]
            print(f"{'yes' if yes else 'no'} (answered in {NAME}'s window)")
            break
    for item in held:
        inbox.put(item)
    tell_pet(do="answered", id=asked)
    return yes

def file_info(p):  # name, size, age. File contents never leave the laptop.
    st = p.stat()
    short = "~/" + p.relative_to(HOME).as_posix() if p.is_relative_to(HOME) else str(p)
    return {"path": short, "mb": round(st.st_size / 1e6, 1), "days_old": int((time.time() - st.st_mtime) / 86400)}

def file_infos(paths):  # file_info for each path, skipping files that vanish or are locked
    infos = []
    for p in paths:
        with suppress(OSError):
            infos.append(file_info(p))
    return infos

@tool
def scan_downloads() -> dict:
    """List files in ~/Downloads with size (MB) and age (days), largest first, max 50.
    Use this FIRST when the user asks about Downloads, clutter, or old installers."""
    files = file_infos(p for p in (HOME / "Downloads").glob("[!.]*") if p.is_file())
    files.sort(key=lambda f: -f["mb"])
    return {"count": len(files), "total_mb": round(sum(f["mb"] for f in files), 1),
            "oldest": max(files, key=lambda f: f["days_old"], default=None), "files": files[:50]}

@tool
def find_big_files(folder: str = "~", top_n: int = 5) -> list:
    """Find the biggest files under a folder (default: home). Use this when the user
    asks what is eating the disk. Skips hidden/system folders; stops after 20k files or 10s."""
    sizes, start = [], time.time()
    for dirpath, dirnames, filenames in os.walk(Path(folder).expanduser()):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP]
        for name in filenames:
            with suppress(OSError):  # locked or vanished files: just skip them
                sizes.append((os.path.getsize(os.path.join(dirpath, name)), dirpath, name))
        if len(sizes) > 20_000 or time.time() - start > 10:
            break
    return file_infos(Path(d, n) for _, d, n in heapq.nlargest(min(top_n, 20), sizes))

@tool
def top_processes(n: int = 5) -> list:
    """Show the n busiest processes (% of the whole machine's CPU, and memory %). Use this
    when the user says the laptop is slow, hot or loud, or asks what is running."""
    procs = [p for p in psutil.process_iter(["name"]) if p.pid]  # pid 0 = Windows "System Idle"
    rows, cores = [], psutil.cpu_count() or 1
    for p in procs:
        with suppress(psutil.Error):
            p.cpu_percent(None)  # first call starts the measurement...
    time.sleep(0.5)  # ...then measure over half a second
    for p in procs:
        with suppress(psutil.Error):  # process ended, or belongs to another user
            rows.append({"name": p.info["name"], "cpu": round(p.cpu_percent(None) / cores, 1), "mem": round(p.memory_percent(), 1)})
    return sorted(rows, key=lambda r: (r["cpu"], r["mem"]), reverse=True)[:n]

@tool
def disk_space() -> dict:
    """Total, free and % used on the disk holding the home folder. Use this when the
    user asks how full the disk is, or before judging their clutter."""
    u = shutil.disk_usage(HOME)
    return {"total_gb": round(u.total / 1e9, 1), "free_gb": round(u.free / 1e9, 1),
            "percent_used": round(100 * u.used / u.total)}

@tool
def quarantine_file(path: str) -> str:
    """Move ONE file to ~/Gemlin_Review (never deletes). Use only after the user agrees
    a specific file should go; they must type y. Refuses folders and paths outside home."""
    src = Path(path).expanduser().resolve()
    if not src.is_relative_to(HOME.resolve()) or not src.is_file():
        return "Refused: only existing files inside the home folder can be quarantined."
    if not ask(f"Move ~/{src.relative_to(HOME.resolve()).as_posix()} to ~/{REVIEW.name}? Nothing gets deleted."):
        return "Owner said no. File untouched."
    REVIEW.mkdir(exist_ok=True)
    dest = REVIEW / src.name
    if dest.exists():
        dest = REVIEW / f"{src.stem}-{int(time.time())}{src.suffix}"
    shutil.move(str(src), str(dest))
    return f"Moved to {dest}. Nothing was deleted."

def fingerprint(code):
    return hashlib.sha256(code.encode()).hexdigest()

def trust(code):  # remember approved code, so it loads without asking next time
    TRUSTED.parent.mkdir(parents=True, exist_ok=True)
    with TRUSTED.open("a", encoding="utf-8") as f:
        f.write(fingerprint(code) + "\n")

def show_code(title, code):
    print(f"\n----- {title} -----\n{code}\n" + "-" * 50)

def load_skill(name, code, filename="<skill>"):
    namespace = {}  # fresh namespace, so skills can't trample our globals
    exec(compile(code, filename, "exec"), namespace)
    if not callable(fn := namespace.get(name)):
        raise ValueError(f"the code must define a function named {name}")
    fn.__doc__ = fn.__doc__ or namespace.get("__doc__")
    return tool(fn)

@tool
def learn_skill(name: str, description: str, code: str) -> str:
    """Write yourself a NEW tool when none of your tools can answer. name: snake_case.
    description: what it does and when to use it. code: Python source defining
    `def name(...)` with type hints and a docstring, returning a short str or dict.
    The owner reads the code and must approve it before it is installed."""
    global needs_reload
    show_code(f"{NAME} wants to learn: {name}", code)
    if not name.isidentifier() or name in [t.__name__ for t in TOOLS]:
        return "Refused: name must be a new, valid Python identifier."
    _, problems, warnings = develop.check(code, name)
    if problems:  # send it back to the model to fix before bothering the owner
        return "Refused, fix these and try again: " + "; ".join(problems)
    heads_up = (" Heads up: " + "; ".join(warnings) + ".") if warnings else ""
    if not ask(f"{NAME} wrote a new skill, {name}.{heads_up} Install it? Only say yes if you read and understand the code.", code):
        return "Owner said no. Skill not installed."
    try:
        fn = load_skill(name, code)
    except Exception as e:
        return f"Skill failed to load: {e!r}. Fix the code and try again."
    if not fn.__doc__:  # no docstring? use the description, in memory and on disk
        fn.__doc__ = description
        code = '"""' + description.replace('"', "'") + '"""\n' + code
    SKILLS.mkdir(parents=True, exist_ok=True)
    (SKILLS / f"{name}.py").write_text(code, encoding="utf-8")
    trust(code)
    needs_reload = True  # the main loop rebuilds the chat so the new tool shows up
    return f"Installed {name}. You can call it on your next turn."

def new_chat(history=None):  # Gemma, with its personality and every tool and skill (see models.py)
    return brain.new_chat(PERSONA + NOTE, TOOLS, history)

def wake_brain():
    """Gemma on this computer (gemlin model local), or on Google with your key."""
    if models.source() == "local":
        try:
            return models.Local()
        except models.LocalError as e:
            print(f"  {e}")
            if not paths.api_key():
                tell_pet(do="say", text=str(e))
                return None
            print("  Using Gemma on Google for now.")
            tell_pet(do="say", text=f"{e} I'll think on Google's servers for now.")
    key = paths.api_key() or get_key()  # no key yet? Gemlin coaches you through getting one
    if key == "local":  # chose Gemma on this computer instead
        return wake_brain()
    return models.Google(key, MODEL) if key else None

def use_local():
    """Typed "local" instead of a key: switch to Gemma on this computer, if it's here."""
    try:
        found = models.Local()
    except models.LocalError as e:
        return str(e)
    models.use("local", found.model)
    return None

def load_skills():
    """Built-in skills come with Gemlin and load right away. Yours (in ~/.gemlin/skills) ask first
    whenever they're new or changed, since they might have come from anywhere."""
    for f in sorted(BUILTIN.glob("*.py")):
        try:
            load_skill(f.stem, f.read_text(encoding="utf-8"), str(f))
        except Exception as e:
            print(f"  ⚠️  skipped built-in skill {f.name}: {e}")
    trusted = set(TRUSTED.read_text(encoding="utf-8").split()) if TRUSTED.exists() else set()
    names = [t.__name__ for t in TOOLS]
    for f in sorted(SKILLS.glob("*.py")) if SKILLS.exists() else []:
        if f.stem in names:
            print(f"  ⚠️  skipped skill {f.name}: Gemlin already has a tool called {f.stem}")
            continue
        code = f.read_text(encoding="utf-8")
        if fingerprint(code) not in trusted:  # new or changed since you last approved it
            show_code(f"new skill: {f.name}", code)
            if not ask(f"Load the skill {f.name}? It's new or changed. Only say yes if you read and understand the code.", code):
                print(f"  skipped skill {f.name} (it will ask again next time)")
                continue
            trust(code)
        try:
            load_skill(f.stem, code, str(f))
        except Exception as e:
            print(f"  ⚠️  skipped skill {f.name}: {e}")

def check_key(key):
    """None if the key works, "offline" if Google couldn't be reached, otherwise what went wrong."""
    import httpx
    tester = genai.Client(api_key=key)  # keep hold of it: the SDK closes a client nobody refers to
    try:
        tester.models.get(model=MODEL)
    except errors.APIError as e:
        return f"error {e.code}"
    except (httpx.TransportError, OSError):  # no internet, DNS trouble, a timeout
        return "offline"
    except Exception as e:
        return type(e).__name__
    return None

def looks_like_key(text):  # Gemini keys are one long code with no spaces
    return 20 <= len(text) <= 200 and text.isprintable() and not any(c.isspace() for c in text)

def get_key():
    """No API key yet: coach the owner through getting one, in the pet's window (or the terminal)."""
    if not pet_alive():
        print(f"{NAME} needs a free Gemini API key before it can think. Get one at {KEY_PAGE}\n"
              "  (sign in with Google, click Create API key, copy it), then paste it here.\n"
              "  Or type local to use Gemma on this computer (LM Studio or Ollama).")
        from getpass import getpass
        while True:
            try:
                key = getpass("  API key (hidden): ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not key:
                return None
            if key.lower() == "local":
                if problem := use_local():
                    print(f"  {problem}")
                    continue
                return "local"
            problem = check_key(key)
            if problem in (None, "offline"):
                paths.save_api_key(key)
                print("  Saved. Thank you!")
                return key
            print(f"  That key didn't work ({problem}). Try again, or press Enter to stop.")
    tell_pet(do="need_key", url=KEY_PAGE)
    tell_pet(do="say", text=f"Hi! I'm {NAME}. Before I can think, I need a free key from Google. It takes "
             "about a minute. 1. Click “Get a free key” below: Google AI Studio opens. 2. Sign in with your "
             "Google account and click “Create API key”. 3. Copy the key, paste it in my box, and press Enter. "
             "(Have LM Studio or Ollama with Gemma? Type local and I'll think on this computer instead.)")
    print(f"{NAME} is waiting for an API key in its window (or run: gemlin setup).")
    while True:
        source, text = next_line("pet", "you", "gone")
        if shutting_down(source, text) or (source == "you" and text is None and not pet_alive()):
            return None
        if text is None:
            continue
        key = text.strip()
        if key.lower() == "local":
            tell_pet(do="think")
            if problem := use_local():
                tell_pet(do="say", text=problem)
                continue
            print("  Thinking on this computer from now on (gemlin model google switches back).")
            tell_pet(do="key_ok")
            tell_pet(do="say", text="OK! I'll think right here on this computer. What can I do for you?")
            return "local"
        if not looks_like_key(key):
            tell_pet(do="say", text="That doesn't look like a key. It's one long code, usually starting with "
                     "“AIza”. Click “Get a free key” if you don't have one yet.")
            continue
        tell_pet(do="think")
        problem = check_key(key)
        if problem in (None, "offline"):
            paths.save_api_key(key)
            print("  API key saved (by the pet window).")
            tell_pet(do="key_ok")
            tell_pet(do="say", text="Got it, thank you! Now I can think. What can I do for you?"
                     + (" (I couldn't test the key because Google didn't answer.)" if problem else ""))
            return key
        tell_pet(do="say", text=f"Hmm, Google says that key doesn't work ({problem}). Copy it again from "
                 "AI Studio and paste it here.")

LOOK_CODE = re.compile(r"(?:gemlin\s+look\s+)?([A-Za-z0-9_-]{40,})")

def new_look(msg):
    """A look code pasted into the chat (with or without `gemlin look`): save it and return the new look."""
    if match := LOOK_CODE.fullmatch(msg.strip()):
        with suppress(ValueError):
            return pet.save_look(match.group(1))
    return None

def wear(me):  # take on a new name and personality
    global NAME, PERSONA
    NAME, PERSONA = me["name"], f"You are {me['name']}, {me['personality']}"

def slash_command(msg):
    """Handle /help, /skills and /develop. Returns (reply, None), (None, prompt for the model), or None."""
    word, _, rest = msg.partition(" ")
    if word == "/help":
        return COMMANDS, None
    if word == "/skills":
        names = sorted(t.__name__ for t in TOOLS)
        return f"I can use {len(names)} skills: " + ", ".join(names) + ". Teach me more with /develop IDEA.", None
    if word == "/develop":
        if not rest.strip():
            return "Tell me what to build, like: /develop a skill that lists my oldest screenshots", None
        return None, (f"Please write me a new skill with learn_skill for this: {rest.strip()}. "
                      f"Follow these rules:\n{develop.RULES}")
    if word.startswith("/"):
        return f"I don't know {word}. " + COMMANDS, None
    return None

def main(desktop=True, background=False):
    """Wake Gemlin up. desktop: open the pet (chat in its window). background: started by
    `gemlin start`, with no terminal attached, so the pet is the only way in."""
    global brain, needs_reload, NAME, PERSONA, terminal_open
    if background:
        sys.stdout.reconfigure(line_buffering=True)  # the log file shows each line right away
    if pet.SETTINGS.exists():  # made at gemlin.dev/create
        wear(pet.load_settings())
    terminal_open = not background
    if not background:
        threading.Thread(target=read_terminal, daemon=True).start()
    if desktop:
        start_pet()
    brain = wake_brain()
    if not brain:
        tell_pet(do="bye")
        sys.exit(KEY_HELP)
    load_skills()
    chat = new_chat()
    tell_pet(do="idle")
    if pet_alive() and not pet.SETTINGS.exists() and not paths.config().get("offered_customize"):
        tell_pet(do="say", text=f"Hi! I'm {NAME}. Want to make me yours? Click “Customize me” below to pick my "
                 "name, personality, hat and colors. Then paste the code back here in my chat box.")
        paths.save_config(offered_customize=True)  # just once
    if background:
        print(f"{NAME} wakes up on your desktop ({brain.label}, {len(TOOLS)} tools). To stop: gemlin stop")
    elif pet_proc:
        print(f"{NAME} wakes up on your desktop ({brain.label}, {len(TOOLS)} tools). Chat with it in its little window.\n"
              f"  This terminal shows what {NAME} is doing. To stop: right-click {NAME} > Go to sleep (or type quit here).")
    else:
        print(f"{NAME} wakes up ({brain.label}, {len(TOOLS)} tools). Type 'quit' to leave.")
    while True:
        try:
            if not pet_alive():
                print("\nyou> ", end="", flush=True)
            source, msg = next_line("you", "pet", "gone")
            if source == "gone":
                if not terminal_open:  # no terminal either, so there's nothing left to chat in
                    print(f"({NAME}'s window closed, so {NAME} is going to sleep.)")
                    break
                print(f"({NAME}'s window closed. You can keep chatting here.)")
                continue
            if msg is None:
                terminal_open = False
                if pet_alive():
                    continue  # no terminal to type in: the pet is where you chat
                break
            if source == "pet" and msg != "quit":
                print(f"\nyou> {msg}")
            msg = msg.strip()
            if msg.lower() in ("quit", "exit"):
                break
            if me := new_look(msg):  # pasted from gemlin.dev/create
                wear(me)
                chat = new_chat(chat.get_history())  # same conversation, new personality
                tell_pet(do="look")
                hello = f"Ta-da! I'm {NAME} now. What can I do for you?"
                print(f"  (new look saved)\n{NAME}> {hello}")
                tell_pet(do="say", text=hello)
                continue
            if (command := slash_command(msg)) and command[0]:  # answered without the model
                print(f"{NAME}> {command[0]}")
                tell_pet(do="say", text=command[0])
                continue
            if command:
                msg = command[1]
            if msg:
                tell_pet(do="think")
                reply = chat.send_message(msg)
                while needs_reload:  # learn_skill ran: rebuild the chat, keep the history
                    needs_reload = False
                    print(f"{NAME}> {reply.text or '...'}")
                    chat = new_chat(chat.get_history())
                    reply = chat.send_message(f"(skill installed: {TOOLS[-1].__name__}; use it now if relevant)")
                print(f"{NAME}> {reply.text or '...'}")
                tell_pet(do="say", text=reply.text or "...")
        except (EOFError, KeyboardInterrupt):
            break
        except models.LocalError as e:
            print(f"{NAME}> ({e})")
            tell_pet(do="say", text=f"Hmm. {e}")
        except errors.APIError as e:
            tell_pet(do="oops")
            if e.code in (429, 503):
                print(f"{NAME}> (rate limited) Wait ~30s, switch MODEL to gemma-4-31b-it, or run Gemma here: gemlin model local")
            elif e.code == 500:
                print(f"{NAME}> (Google hiccup, error 500) Just send that again.")
            else:
                print(KEY_HELP if "API key" in str(e) else f"{NAME}> (API error {e.code}) {e.message}")
        except Exception as e:
            tell_pet(do="oops")
            print(f"{NAME}> (something broke: {e!r})")
    tell_pet(do="bye")
    print(f"\n{NAME} goes back to sleep.")
