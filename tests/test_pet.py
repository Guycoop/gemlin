"""Offline tests for the pet's art pipeline (no window is opened)."""
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from gemlin import pet  # noqa: E402

FRAMES = [(view, body, eyes, mouth, left) for view in ("front", "side") for body in ("stand", "walk_1", "walk_2")
          for eyes in ("open", "blink") for mouth in ("closed", "talk_1") for left in (False, True)]


def look_code(settings):
    return base64.urlsafe_b64encode(json.dumps(settings).encode()).decode().rstrip("=")


@pytest.mark.parametrize("hat", pet.options("hat") + ["none"])
def test_every_hat_builds_every_frame_with_no_key_colors_left(hat):
    sprites = pet.Sprites(pet.clean({"parts": {"hat": hat}}))
    assert sprites.has_side
    for key in FRAMES:
        rows = sprites.frame(*key)
        assert len(rows) == 64 and all(len(row) == 64 for row in rows)
        assert not any(px in pet.KEY_COLORS for row in rows for px in row if px)


def test_chosen_colors_are_used():
    sprites = pet.Sprites(pet.clean({"colors": {"body": "#123456"}}))
    assert any(px == (0x12, 0x34, 0x56) for row in sprites.frame() for px in row)


def test_left_is_a_mirror_of_right():
    sprites = pet.Sprites(pet.clean({}))
    right, left = sprites.frame("side", "walk_1"), sprites.frame("side", "walk_1", left=True)
    assert left == [row[::-1] for row in right]


def test_missing_frames_fall_back():
    sprites = pet.Sprites(pet.clean({}))
    assert sprites.find("body", "walk_2").name == "walk_1.png"  # no front walk_2 yet
    assert sprites.steps("side") == ["walk_1", "walk_2"]
    assert sprites.steps("front") == ["stand", "walk_1"]


def test_png_round_trip(tmp_path):
    rows = pet.read_png(pet.ART / "body" / "gem" / "stand.png")
    (tmp_path / "copy.png").write_bytes(pet.png(rows))
    assert pet.read_png(tmp_path / "copy.png") == rows


def test_clean_keeps_only_sensible_values():
    me = pet.clean({"name": "x" * 99, "parts": {"hat": "../../etc", "body": "gem"},
                    "colors": {"body": "red", "eyes": "#ABCDEF"}, "walk": "front"})
    assert me["name"] == "x" * 24
    assert me["parts"]["hat"] == pet.DEFAULTS["parts"]["hat"]
    assert me["colors"] == {**pet.DEFAULTS["colors"], "eyes": "#abcdef"}
    assert "walk" not in me  # it always walks sideways now; old look codes still load
    assert pet.clean("not a dict") == pet.clean({})


def test_save_look(tmp_path, monkeypatch):
    monkeypatch.setattr(pet, "SETTINGS", tmp_path / "gemlin.json")
    me = pet.save_look(look_code({"name": "Zoë", "parts": {"hat": "bow"}, "colors": {"accent": "#ff8800"}}))
    assert json.loads((tmp_path / "gemlin.json").read_text(encoding="utf-8")) == me
    assert (me["name"], me["parts"]["hat"], me["colors"]["accent"]) == ("Zoë", "bow", "#ff8800")
    with pytest.raises(ValueError):
        pet.save_look("not-a-real-code!")


def test_manifest_is_up_to_date():
    committed = json.loads((pet.ART / "manifest.json").read_text(encoding="utf-8"))
    real = {slot: {name: sorted(p.stem for p in (pet.ART / slot / name).glob("*.png")) for name in pet.options(slot)}
            for slot in pet.FIRST_FRAME}
    assert committed == real, "the art changed: run python -m gemlin.pet --manifest"


def test_pages_split_long_replies():
    text = "Hello there. " * 40
    parts = pet.pages(text)
    assert len(parts) > 1 and all(len(p) <= 175 for p in parts)
    assert pet.pages("**bold** `code`") == ["bold code"]


def brain():
    b = pet.Brain(pet.clean({}), screen_w=1000, floor=800, follow=False)
    b.step()
    return b


def test_brain_says_hello_then_wanders_off():
    b = brain()
    assert b.mode == "talk" and "Gemlin" in b.bubble[0]
    start = b.x
    for _ in range(400):  # 16 seconds
        b.step()
    assert b.bubble is None and b.x != start


def test_walking_uses_the_side_view_and_faces_where_it_goes():
    b = brain()
    b.set_mode("wander")
    b.rest, b.target = 0, None
    b.step()
    b.target = b.x - 100
    b.step()
    assert b.frame[0] == "side" and b.frame[4] is True  # walking left = mirrored


def test_click_opens_chat_and_drag_does_not():
    b = brain()
    b.pick_up(10, 10)
    b.drop()
    assert b.chatting
    b.chatting = False
    b.pick_up(10, 10)
    b.drag(60, 10)
    b.drop()
    assert not b.chatting


def test_typed_chat_goes_to_gemlin(capsys):
    b = brain()
    b.follow, b.chatting = True, True
    b.heard("  hello there  ")
    assert json.loads(capsys.readouterr().out) == {"say": "hello there"}
    assert b.chatting and b.mode == "think"  # the chat box stays open for the next message


def test_long_replies_page_with_a_footer():
    b = brain()
    b.handle({"do": "say", "text": "This is a sentence that goes on. " * 20})
    text, footer = b.bubble
    assert footer.startswith("1/") and len(text) <= 175
    b.bubble_clicked()
    assert b.bubble[1].startswith("2/")


def test_bye_closes_after_a_moment():
    b = brain()
    b.handle({"do": "bye"})
    assert b.bubble == ("bye!", "") and not b.done
    for _ in range(60):
        b.step()
    assert b.done


def test_questions_show_in_the_pet_and_answers_go_back(capsys):
    b = brain()
    b.follow = True
    b.handle({"do": "ask", "id": 7, "question": "Install it?", "code": "def x(): pass"})
    assert b.asking == {"id": 7, "question": "Install it?", "code": "def x(): pass"} and b.mode == "ask"
    b.answer(True)
    assert json.loads(capsys.readouterr().out) == {"answer": 7, "yes": True}
    assert b.asking is None


def test_answering_in_the_terminal_closes_the_question():
    b = brain()
    b.handle({"do": "ask", "id": 2, "question": "Move it?"})
    b.handle({"do": "answered", "id": 1})  # some other question
    assert b.asking
    b.handle({"do": "answered", "id": 2})
    assert b.asking is None


def test_going_to_sleep_tells_gemlin(capsys):
    b = brain()
    b.follow = True
    b.quit()
    assert json.loads(capsys.readouterr().out) == {"quit": True} and b.done


@pytest.fixture
def fake_system(monkeypatch):
    """Stand-ins for the OS bits, so menu tests don't touch your login items or start anything."""
    from gemlin import system
    calls = {"autostart": False, "background": [], "opened": []}
    monkeypatch.setattr(system, "autostart_enabled", lambda home=None: calls["autostart"])
    monkeypatch.setattr(system, "set_autostart", lambda on, home=None: calls.update(autostart=on))
    monkeypatch.setattr(system, "run_in_background", lambda *args: calls["background"].append(args))
    monkeypatch.setattr(system, "open_file", lambda path: calls["opened"].append(path))
    return calls


def test_the_menu_has_everything(fake_system):
    actions = [entry[1] for entry in brain().menu() if entry]
    assert actions == ["chat", "customize", "wander", "autostart", "local", "log", "update", "restart", "sleep"]


def test_menu_actions(fake_system, tmp_path, monkeypatch):
    b = brain()
    b.menu_action("chat")
    assert b.chatting and b.attention == 1
    assert b.menu_action("customize") == pet.CREATOR
    b.menu_action("wander")
    assert not b.wander
    b.menu_action("autostart")
    assert fake_system["autostart"] is True and dict(b.menu()[4:5] and [(e[1], e[2]) for e in b.menu() if e])["autostart"]
    monkeypatch.setattr(pet.paths, "LOG", tmp_path / "gemlin.log")
    b.menu_action("log")  # no log yet: says so instead of opening nothing
    assert not fake_system["opened"] and "Nothing to show" in b.bubble[0]
    (tmp_path / "gemlin.log").write_text("hi")
    b.menu_action("log")
    assert fake_system["opened"] == [tmp_path / "gemlin.log"]
    b.menu_action("restart")
    assert fake_system["background"] == [("restart",)] and b.leaving


@pytest.mark.parametrize("source, latest, says, updates", [
    (True, "9.9.9", "Pulling the newest code", True),
    (False, None, "couldn't reach", False),
    (False, "0.0.1", "up to date", False),
    (False, "99.0.0", "Updating to version 99.0.0", True),
])
def test_check_for_updates(fake_system, monkeypatch, source, latest, says, updates):
    from gemlin import system
    monkeypatch.setattr(system, "installed_from_source", lambda: source)
    monkeypatch.setattr(system, "latest_version", lambda timeout=6: latest)
    b = brain()
    b.check_for_updates()
    assert says in b.events.get()["text"]
    assert (("update",) in fake_system["background"]) == updates


def test_opening_the_app_while_awake_brings_up_the_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(pet.paths, "SHOW", tmp_path / "show")
    b = brain()
    (tmp_path / "show").touch()
    for _ in range(12):
        b.step()
    assert b.chatting and b.attention == 1 and not (tmp_path / "show").exists()
