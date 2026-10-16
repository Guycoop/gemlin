# Gemlin: an AI creature that lives on your desktop and teaches itself new tricks

![Gemlin](assets/banner.png)

A tiny AI creature that lives on your desktop, powered by **Gemma 4 via the Gemini API**. It walks along the bottom of your screen, chats with you in its own little window, uses skills to sense your machine (Downloads, big files, busy processes, battery, memory, git projects…), and can **write new skills for itself** when you ask for something it can't do yet. You approve every change.

The default creature is **Gemlin**, a cheeky little gem-flavored creature (a play on Gemma) that loves tidy disks and teases you about your file hoarding. **Design your own** (name, personality, hat, colors) at **[gemlin.dev/create](https://gemlin.dev/create/)**.

Built for the **Gemlin** workshop at Hacktoberfest Hack Day Draper x AMH (Oct 16, 2026). Theme: *AI belongs to everyone.*

## Install

All you need is a Google account. Paste one line into a terminal:

```bash
# Mac / Linux (on a Mac, open Terminal: press ⌘ Space and type Terminal)
curl -LsSf https://gemlin.dev/install.sh | sh
```
```powershell
# Windows (open PowerShell from the Start menu)
powershell -ExecutionPolicy ByPass -c "irm https://gemlin.dev/install.ps1 | iex"
```

The installer ([install.sh](site/install.sh), [install.ps1](site/install.ps1)) uses [uv](https://docs.astral.sh/uv/) to install Gemlin with its own copy of Python, so nothing else on your computer changes and you don't need Python or git yourself. It adds the **Gemlin app** (Applications, Launchpad and Spotlight on a Mac; the Start menu on Windows; your app launcher on Linux), asks whether Gemlin should wake up whenever you log in, then wakes it up. After that you can close the terminal for good.

Then:

1. **Get a key, in Gemlin's window.** The first time, Gemlin walks you through getting a free Gemini API key: click **Get a free key** (Google AI Studio opens), create one, and paste it into Gemlin's chat box. The box hides what you paste. (`gemlin setup` does the same from the terminal.)
2. **Make it yours.** Click **Customize me** under its chat box (or go to [gemlin.dev/create](https://gemlin.dev/create/)), pick a name, personality, hat and colors, click Copy, and paste the code into Gemlin's chat window.

To update: *Check for updates…* in Gemlin's menu, `gemlin update`, or run the install line again. To remove Gemlin: `gemlin uninstall`, then `uv tool uninstall gemlin`. Your settings and skills are in `~/.gemlin` if you want to delete those too.

### Install from source (to change Gemlin's code)

You need **Python 3.10+** and git. In a virtual environment (Homebrew Python refuses a plain `pip install`):

```bash
git clone https://github.com/alexinslc/gemlin && cd gemlin
python3 -m venv .venv && source .venv/bin/activate     # Windows: python -m venv .venv  then  .venv\Scripts\activate
pip install -e .
gemlin start
```

Your edits take effect after `gemlin restart`. In a new terminal, run the activate line first.

## No terminal needed

- **The Gemlin app**: open it from Launchpad, Spotlight or Applications (Mac) or the Start menu (Windows). It wakes Gemlin up, or brings up its chat if it's already awake.
- **Menu bar / system tray**: Gemlin stays out of the Dock and lives in the Mac menu bar (or the Windows system tray, or a Linux panel that supports tray icons) with its whole menu.
- **Right-click Gemlin** for the same menu:

| Menu | What it does |
| --- | --- |
| Chat | Opens the chat box and brings it to the front |
| Customize me… | Opens gemlin.dev/create; paste the code back into the chat |
| Walk around ✓ | Untick to make Gemlin stay put |
| Wake up at login ✓ | Gemlin starts by itself when you log in |
| What I've been doing… | Opens Gemlin's log |
| Check for updates… | Updates Gemlin if there's a newer version, then it comes right back |
| Restart | Starts Gemlin fresh (after you add a skill, for example) |
| Go to sleep | Quits Gemlin. Open the app to wake it again |

## Gemma on your own computer

Gemlin can think with Gemma running **on your computer** instead of Google's servers: no API key, nothing leaves your machine, and it keeps working when Google's API is having a bad day.

1. Install [LM Studio](https://lmstudio.ai) (or [Ollama](https://ollama.com)) and download a Gemma 4 model in it. `google/gemma-4-e4b` is small and quick; `google/gemma-4-12b` is smarter if you have the memory (16 GB+).
2. Switch Gemlin over, any one of these ways:
   - right-click Gemlin (or its menu bar / tray icon) → **Think on this computer**
   - `gemlin model local` (add `--name google/gemma-4-12b` to pick a model)
   - type `local` when Gemlin asks for a key

Gemlin starts LM Studio's server for you if it's installed. The first answer takes a little longer while the model loads. `gemlin model` shows where Gemlin thinks and which local models it found; `gemlin model google` switches back.

## The `gemlin` command

| Command | What it does |
| --- | --- |
| `gemlin setup` | Checks Python and the pieces Gemlin needs, and saves your API key |
| `gemlin start` | Wakes Gemlin up on your desktop. It keeps running after you close the terminal |
| `gemlin stop` | Puts it to sleep (so does right-click → *Go to sleep*) |
| `gemlin restart` | Stop, then start. Use it after changing Gemlin's code or skills |
| `gemlin status` | Is it awake? Is your key saved? |
| `gemlin look CODE` | Uses the look you made at gemlin.dev/create (restarts Gemlin if it's awake) |
| `gemlin chat` | Chat in the terminal instead (the desktop pet opens too; `--no-pet` for just the terminal) |
| `gemlin logs` | What Gemlin has been doing (`-f` to keep watching) |
| `gemlin skills` | Lists its skills. `gemlin skills new NAME` starts one; `gemlin skills add FILE` adds one someone shared |
| `gemlin autostart on` | Wakes Gemlin up whenever you log in (`off` turns it off) |
| `gemlin show` | Wakes Gemlin up, or opens its chat if it's awake (what the app does) |
| `gemlin app` | Adds the Gemlin app to Applications / the Start menu / your launcher (`gemlin app remove` takes it out) |
| `gemlin model local` | Thinks with Gemma on this computer (LM Studio / Ollama); `gemlin model google` switches back |
| `gemlin update` | Updates to the newest version (from a source checkout: `git pull` and reinstall, then restart) |
| `gemlin uninstall` | Puts Gemlin to sleep and removes its app and login item |
| `gemlin develop IDEA` | Builds a new skill with Gemma's help: try it, change it, save it (see [Extending Gemlin](#extending-gemlin)) |

## Make your own Gemlin

1. Click **Customize me** under Gemlin's chat box, or open **[gemlin.dev/create](https://gemlin.dev/create/)**.
2. Pick a name, a personality, a hat and colors. Your Gemlin walks around a pretend desktop so you can see it.
3. Click **Copy** and paste it into Gemlin's chat window. It changes right away. (Gemlin not running? Paste it into a terminal instead: it's a `gemlin look ...` command.)

Do it again any time to change your look. Your Gemlin's name and personality win over `NAME` and `PERSONA` at the top of `gemlin/core.py`; delete `~/.gemlin/look.json` to go back.

## The desktop pet

- It **walks** back and forth along the bottom of your screen, sideways, and turns to face you when it talks.
- **Its chat window looks like part of your computer**: a translucent popover that follows light and dark mode on a Mac, and your light/dark theme and accent color on Windows. Type `/help` there for shortcuts like `/develop` and `/skills`.
- **Its chat window opens when it wakes up.** Type, press Enter, and the answer appears in a speech bubble. The window stays open for your next message; Esc closes it and clicking Gemlin brings it back.
- **Long replies come in pages**: click the bubble for the next one.
- **Drag it** to move it; let go and it drops back down.
- **Right-click** for *Chat*, *Stay here* (stop walking) and *Go to sleep* (quits Gemlin).
- **When Gemlin needs your OK** (moving a file, a new skill), it hops and opens a window with **Yes / No**. For a skill, the window shows the whole code, centered on screen so you can read it. Yes always needs a click; Esc means No.

## Things to try

Type these into Gemlin's chat window:

```
how bad is my Downloads folder?
what's eating my disk?
why is my laptop so loud right now?
do I have any duplicate downloads?
which of my projects have unsaved git changes?
move that old installer out of the way
learn a skill that counts my Downloads files by extension
```

While Gemlin uses a skill its bubble says so (`using scan downloads...`), and `gemlin logs` shows `🔧 calling scan_downloads`.

## Skills

A skill is a small Python file with one function. The function's name matches the file name, and its docstring tells Gemlin *when* to use it.

- **Built-in skills** come with Gemlin in `gemlin/skills/` and load without asking: `battery_status`, `biggest_folders`, `current_time`, `dirty_git_repos`, `duplicate_downloads`, `memory_usage`, `network_usage`, `recent_files`, `system_info`. They're good examples to read.
- **Your skills** live in `~/.gemlin/skills/`. Gemlin saves skills it writes there (with `learn_skill`, after you say yes), and you can write your own: `gemlin skills new wifi_name` starts one from a template. Because a skill there might have come from anywhere (a friend, the internet, Gemlin itself), any skill that is **new or changed since you last approved it** shows you its code and asks before it loads.
- Changed a skill? `gemlin restart` picks it up.

## Extending Gemlin

You can teach Gemlin new skills without writing much code yourself: **Gemma writes them, you stay in charge.**

```bash
gemlin develop a skill that finds screenshots on my Desktop older than a week
```

Gemma writes the skill. Gemlin checks it against the skill rules and warns you about anything that would delete, write, use the internet or run other programs. Then you choose:

- **[t] try it**: runs it (after you've read it) and shows what it returns.
- **[c] change it**: say what to change in plain words, or press Enter to fix whatever went wrong.
- **[s] save it**: saves it to `~/.gemlin/skills` and offers to restart Gemlin so it can use it.

`gemlin develop --edit NAME` improves one of your skills. In the chat window, `/develop IDEA` does the quick version: Gemlin writes the skill and shows it to you in its Yes/No window.

**Examples:** [`examples/`](examples/) has three finished skills to read and try (`gemlin skills add examples/old_screenshots.py`) and a list of ideas to build.

## How it works

- **`gemlin/core.py`** is the creature: its name, personality and model at the top, its core senses (`scan_downloads`, `find_big_files`, `top_processes`, `disk_space`), its one action (`quarantine_file`), and `learn_skill`. The SDK's **automatic function calling** does the plumbing: you pass Python functions as `tools=[...]`, and the SDK runs them when the model asks and sends the results back.
- **`gemlin/develop.py`** is the skill workbench behind `gemlin develop` and `/develop`, and the skill rules and checks every new skill has to pass.
- **`gemlin/cli.py`** is the `gemlin` command. `gemlin start` runs Gemlin in the background; the desktop pet is its only window.
- **`gemlin/pet.py`** builds the pet's sprites from the layered art in `gemlin/art/`, recolored with your look, and decides what the pet does. `pet_mac.py` draws it on a Mac (Cocoa) and `pet_tk.py` on Windows and Linux (tkinter). Gemlin and the pet talk over a pipe, one JSON line per message.
- **`gemlin/system.py`** handles the operating system: the Gemlin app, waking at login, opening files and updates. **`gemlin/icons/`** has the app, menu bar and tray icons for each OS.
- **`gemlin/paths.py`** says where things live. Everything that's yours is in `~/.gemlin/`: your key (`config.json`), your look, your skills and approvals, and the log.

## Model

- **Gemma 4** (`gemma-4-26b-a4b-it`) through the Gemini API, with a free API key from Google AI Studio.
- If you hit rate limits, change one line in `gemlin/core.py`: `MODEL = "gemma-4-31b-it"`, then `gemlin restart`.
- Gemma on the Gemini API: https://ai.google.dev/gemma/docs/core/gemma_on_gemini_api · Gemma terms: https://ai.google.dev/gemma/terms

Key dependencies: the official [`google-genai`](https://googleapis.github.io/python-genai/) SDK and [`psutil`](https://pypi.org/project/psutil/). On a Mac, [`pyobjc-framework-Cocoa`](https://pypi.org/project/pyobjc-framework-Cocoa/) draws the pet's see-through window (installed on Macs only).

## Safety notes

- **Gemlin only looks.** Its senses and built-in skills report names, sizes, dates and totals. They never open your files or send what's inside them to the model.
- **Quarantine never deletes.** It only moves a single file into `~/Gemlin_Review` after you say yes. It refuses folders and anything outside your home folder. Empty that folder yourself when you're sure.
- **Never approve code you didn't read.** Skills run on your machine with your permissions. If you don't understand one, say No. Delete a bad skill by removing its file from `~/.gemlin/skills/`.
- **Your key stays on your machine**, in `~/.gemlin/config.json`, readable only by you. A `GEMINI_API_KEY` environment variable wins over it.
- **Free-tier data use:** on the Gemini API free tier, your prompts and responses may be used to improve Google products. Don't type secrets or anything private into the chat. See https://ai.google.dev/gemini-api/terms.

## Troubleshooting

- **`gemlin: command not found`**: open a new terminal after installing. Installed from source? Activate the virtual environment first (`source .venv/bin/activate`, or `.venv\Scripts\activate` on Windows), in the gemlin folder.
- **"rate limited" or Google errors**: wait about 30 seconds, or switch `MODEL` to `gemma-4-31b-it`, or skip Google entirely: `gemlin model local` (see [Gemma on your own computer](#gemma-on-your-own-computer)). Each skill Gemlin uses counts as an extra request.
- **"Missing or invalid API key"**: run `gemlin setup` again.
- **Gemlin didn't appear**: `gemlin logs` shows why. `gemlin status` says whether it's awake. `gemlin setup` checks for the desktop window pieces: on a Mac, `pip install -e .` installs them; on Linux, `sudo apt install python3-tk`.
- **API error 400 mentioning thinking**: comment out the `thinking_config=` line in `new_chat()` in `gemlin/core.py`.
- **The pet has a square background on Linux**: Tk can't make see-through windows there. Mac and Windows get a see-through pet.
- **macOS asks for "access to files in your Documents/Desktop/Downloads folder"**: that's Gemlin looking at file sizes and dates. Click Allow, or Don't Allow and it will skip those folders.

## Running the tests

```bash
pip install pytest
python -m pytest
```

The tests run offline (no API key needed) and use a temporary home folder, so they never touch your files or `~/.gemlin`.

## The website (gemlin.dev)

`site/` is the whole website, as plain static files with no build step: the home page (`site/index.html`), the creator (`site/create/`) and `site/sprites.js`, which builds sprites the same way `gemlin/pet.py` does. `site/art` is a link to `gemlin/art`, so the website and the pet share one copy of the art. Preview it with `python -m http.server -d site 8000`.

It's deployed to Cloudflare as a Worker with static assets (see `wrangler.jsonc`):

```bash
npx wrangler deploy
```

If you add or change art in `gemlin/art/`, run `python -m gemlin.pet --manifest` first so the website knows about it (a test checks this).

## Hack ideas

- Give your Gemlin a new name and personality at [gemlin.dev/create](https://gemlin.dev/create/) (a dragon that hoards GPU memory? an anxious librarian?).
- Build a skill with Gemma: `gemlin develop` and an idea from [`examples/README.md`](examples/README.md).
- Write a skill by hand: `gemlin skills new wifi_name`, fill it in, `gemlin restart`, and ask Gemlin about it.
- Ask Gemlin to write a skill for you, then read it carefully before saying Yes.
- Draw a new hat: add a folder to `gemlin/art/hat/` with `still.png` and `side_still.png` (64 × 64, the art's key colors), then run `python -m gemlin.pet --manifest`.

## License

MIT for the code in this repo, Copyright (c) 2026 Alex Lutz (see `LICENSE`). The Gemma model is covered by its own terms (linked above).
