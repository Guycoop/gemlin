"""`gemlin develop`: teach Gemlin something new, with Gemma doing the typing.

Describe the skill you want. Gemma writes it, Gemlin checks it against the skill rules,
and you can try it, ask for changes in plain words, and save it when it's right. Saved
skills go in ~/.gemlin/skills, like any skill you write yourself.

The same rules and checks are used when Gemlin writes a skill during a chat (learn_skill
or /develop), so a skill is held to the same standard however it was made.
"""
import ast
import re
import subprocess
import sys
import textwrap

from . import paths

RULES = """A Gemlin skill is ONE Python file with ONE main function. Rules:
- The function name is snake_case and says what it does. Arguments are optional, with
  simple types (int, str, bool) and defaults, so Gemlin can call it with no arguments.
- Its docstring says what it returns, and ends with "Use this when the user asks ..."
  so Gemlin knows when to call it.
- It returns a small dict or list (under about 40 items) that reads well as JSON.
- It only LOOKS. It never deletes, moves, renames or writes files, never changes
  settings, and never reads what's inside the user's files. Names, sizes, dates and
  system information are fine.
- Imports: the Python standard library and psutil only. It should work on macOS,
  Windows and Linux; where something isn't supported, return a dict that says so.
- It handles problems (a missing folder, no permission) by skipping them or returning a
  short message, never by crashing.
- It's short and readable: someone new to Python should be able to follow it."""

ALLOWED = set(sys.stdlib_module_names) | {"psutil"}
CHANGES_THINGS = {"remove", "unlink", "rmtree", "rmdir", "rename", "replace", "move", "write_text", "write_bytes",
                  "chmod", "chown", "kill", "terminate", "truncate", "mkdir", "makedirs", "copy", "copyfile", "copytree"}
INTERNET = {"urllib", "http", "socket", "ssl", "ftplib", "smtplib", "imaplib", "poplib", "telnetlib", "xmlrpc"}
TRY_IT = """import json, sys
namespace = {}
exec(compile(sys.stdin.read(), "skill", "exec"), namespace)
print(json.dumps(namespace[sys.argv[1]](), default=str, indent=1))"""


def main_function(tree):
    """The skill's main function: the one whose docstring says when to use it, else the first public one."""
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    for fn in functions:
        if "use this" in (ast.get_docstring(fn) or "").lower():
            return fn
    return functions[0] if functions else None


def check(code, name=None):
    """Check a skill against the rules. Returns (its name, problems that block it, things to watch out for)."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return None, [f"it isn't valid Python (line {e.lineno}: {e.msg})"], []
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name), None) if name \
        else main_function(tree)
    problems, warnings = [], []
    if fn is None:
        return None, [f"it needs a function called {name}" if name else "it doesn't define a function"], []
    if not re.fullmatch(r"[a-z][a-z0-9_]*", fn.name):
        problems.append(f"the function name {fn.name} should be snake_case")
    doc = ast.get_docstring(fn) or ""
    if not doc:
        problems.append("the function needs a docstring (Gemlin reads it to know when to use the skill)")
    elif "use this" not in doc.lower():
        problems.append('the docstring should say when to use it ("Use this when the user asks ...")')
    required = len(fn.args.args) - len(fn.args.defaults)
    if required:
        problems.append("every argument needs a default value, so Gemlin can call it with none")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                top = module.split(".")[0]
                if top not in ALLOWED:
                    problems.append(f"it imports {top}, but skills can only use the standard library and psutil")
                elif top in INTERNET:
                    warnings.append(f"it uses the internet ({top})")
                elif top == "subprocess":
                    warnings.append("it runs other programs (subprocess): check what it runs")
        elif isinstance(node, ast.Call):
            called = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if called in CHANGES_THINGS:
                warnings.append(f"it may change things on your computer ({called})")
            if called == "open" and any(isinstance(a, ast.Constant) and isinstance(a.value, str) and set(a.value) & set("wax+")
                                        for a in node.args[1:2] + [k.value for k in node.keywords if k.arg == "mode"]):
                warnings.append("it writes to a file (open for writing)")
    return fn.name, list(dict.fromkeys(problems)), list(dict.fromkeys(warnings))


def try_it(code, name, timeout=30):
    """Run the skill in a separate Python, the way Gemlin would call it. Returns (worked, what it printed)."""
    try:
        done = subprocess.run([sys.executable, "-c", TRY_IT, name], input=code, capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"it was still running after {timeout} seconds"
    out = (done.stdout if done.returncode == 0 else done.stderr).strip()
    if done.returncode != 0:
        out = out.splitlines()[-1] if out else "it crashed"  # the last line says what went wrong
    return done.returncode == 0, out[:3000]


def examples():
    """Two built-in skills, so Gemma can see what a good one looks like."""
    return "\n\n".join(f"Example ({p.name}):\n```python\n{p.read_text(encoding='utf-8')}```"
                       for p in (paths.BUILTIN_SKILLS / "battery_status.py", paths.BUILTIN_SKILLS / "duplicate_downloads.py"))


def write(brain, request, code=None, ran=None):
    """Ask Gemma (on Google or this computer, see models.py) for a skill, or a change to one."""
    if code is None:
        prompt = f"Write a Gemlin skill that does this: {request}"
    else:
        prompt = (f"Here is a Gemlin skill:\n```python\n{code}```\n"
                  + (f"When I tried it, this happened:\n{ran}\n" if ran else "")
                  + f"Change it like this: {request}\nReply with the whole updated file.")
    system = f"You write skills for Gemlin, a friendly AI creature that lives on someone's desktop.\n{RULES}\n\n" \
             f"{examples()}\n\nReply with only the complete file in one ```python code block."
    text = brain.ask(prompt, system)
    found = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return textwrap.dedent(found.group(1) if found else text).strip() + "\n"


def show(code, name, problems, warnings):
    print("\n" + "─" * 64)
    for number, line in enumerate(code.splitlines(), 1):
        print(f"{number:3} │ {line}")
    print("─" * 64)
    if problems:
        for problem in problems:
            print(f"  ✗ {problem}")
    else:
        print(f"  ✓ follows the skill rules ({name})")
    for warning in warnings:
        print(f"  ! heads up: {warning}")


def session(brain, request=None, code=None):
    """The workbench loop: write, check, try, change, save."""
    if code is None:
        print("Let's teach Gemlin something new. Describe the skill, for example:\n"
              "  a skill that finds screenshots on my Desktop older than a week")
        try:
            request = request or input("\nWhat should it do? ").strip()
        except EOFError:
            return 1
        if not request:
            return 1
        print("\nGemma is writing it...")
        code = write(brain, request)
    ran = None
    while True:
        name, problems, warnings = check(code)
        show(code, name, problems, warnings)
        try:
            choice = input("\n[t] try it   [c] change it   [s] save it   [q] quit > ").strip().lower()[:1]
        except EOFError:
            return 1
        if choice == "t":
            if problems and not name:
                print("  It can't run yet. Choose [c] and Gemma will fix it.")
                continue
            print("  This runs the code on your computer, with your permissions. Read it first!")
            if input("  Run it? [y/N] ").strip().lower() != "y":
                continue
            worked, ran = try_it(code, name)
            if worked:
                print("  ✓ It returned:\n" + textwrap.indent(ran, "    "))
            else:
                print(f"  ✗ It didn't work: {ran}")
        elif choice == "c":
            hint = "Fix the problems above" if problems else ("Fix the error" if ran and "Error" in ran else "")
            change = input(f"  What should change?{' (Enter: ' + hint.lower() + ')' if hint else ''} ").strip() or hint
            if not change:
                continue
            if problems and change == hint:
                change += ": " + "; ".join(problems)
            print("  Gemma is changing it...")
            code, ran = write(brain, change, code, ran), None
        elif choice == "s":
            if problems:
                print("  Fix the problems first: choose [c] and press Enter.")
                continue
            return save(code, name)
        elif choice == "q":
            print("  Nothing saved.")
            return 0


def save(code, name):
    from .core import trust
    path = paths.SKILLS / f"{name}.py"
    if (paths.BUILTIN_SKILLS / f"{name}.py").exists():
        print(f"  Gemlin already has a built-in skill called {name}. Ask Gemma to rename it ([c]).")
        return 1
    if path.exists() and input(f"  {path} already exists. Replace it? [y/N] ").strip().lower() != "y":
        return 1
    paths.SKILLS.mkdir(parents=True, exist_ok=True)
    path.write_text(code, encoding="utf-8")
    trust(code)  # you read it, tried it and saved it, so it loads without asking again
    print(f"  ✓ Saved {path}")
    return 0

