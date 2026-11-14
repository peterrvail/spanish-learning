"""Slow end-to-end check, off by default:

    RUN_PLAYTHROUGH=1 python -m pytest tests/test_playthrough.py -q

Opens every menu command, then plays every drill to the end with a mix of
right, wrong, accent-only, hinted and "No sé" answers, stepping out to Pausa
and Resumen and back on the way. It fails on any exception or a drill that
never finishes. Takes several minutes; set PLAYTHROUGH_SEED to vary the mix."""
import os
import random
import sys

import pytest

APP = os.path.join(os.path.dirname(__file__), "..", "app", "spanish_drill.py")
sys.path.insert(0, os.path.dirname(APP))

pytestmark = pytest.mark.skipif(not os.environ.get("RUN_PLAYTHROUGH"), reason="slow; set RUN_PLAYTHROUGH=1")


def _new():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def _button(at, text):
    return next((b for b in at.button if text in b.label), None)


def _check(at, where, problems):
    if at.exception:
        problems.append((where, at.exception[0].value))
        return False
    return True


@pytest.fixture
def sd(tmp_path, monkeypatch):
    monkeypatch.setenv("SPANISH_PROGRESS_DB", str(tmp_path / "playthrough.db"))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    import spanish_drill
    return spanish_drill


def test_every_menu_command_opens(sd):
    problems = []
    commands = [cmd for group in sd.DRILL_CATEGORIES.values() for _, cmd in group]
    extra = ["!progreso", "!resumen", "!pausa", "!repasar fallos", "!lt", "!hablar", "!rol", "!rol zzz",
             "!drill correcciones", "!drill nonsense", "!nonsense"]
    at = _new()
    for cmd in commands + extra:
        at.session_state["active_command"] = cmd
        at.session_state["drill_active"] = False
        at.run()
        _check(at, cmd, problems)
        if cmd.startswith("!drill "):
            module = cmd.split()[1]
            at.session_state["active_command"] = f"!repasar {module}"
            at.run()
            _check(at, f"!repasar {module}", problems)
            if _button(at, "Siguiente"):
                _button(at, "Siguiente").click().run()
                _check(at, f"!repasar {module} siguiente", problems)
    assert problems == []


def test_every_drill_plays_to_the_end(sd):
    rng = random.Random(int(os.environ.get("PLAYTHROUGH_SEED", "1")))
    problems = []
    drills = [cmd for group in sd.DRILL_CATEGORIES.values() for _, cmd in group if cmd.startswith("!drill ")]
    for cmd in drills + ["!drill fallos"]:
        at = _new()
        at.session_state["active_command"] = cmd
        at.run()
        if not _check(at, cmd, problems):
            continue
        for _ in range(80):
            if _button(at, "Start New Drill") or not at.session_state["drill_active"]:
                break
            if _button(at, "Continuar"):
                _button(at, "Continuar").click().run()
                _check(at, f"{cmd} continuar", problems)
                continue
            index, items = at.session_state["current_item_index"], at.session_state["drill_items"]
            if index >= len(items):
                at.run()
                continue
            item, roll = items[index], rng.random()
            where = f"{cmd} q{index} ({item.get('exercise_type')})"
            if roll < 0.14:                                  # step out and come back
                _button(at, "Pausa" if roll < 0.08 else "Resumen").click().run()
                _check(at, where + " side screen", problems)
                back = _button(at, "Volver")
                if back is None:
                    problems.append((where, "no way back from the side screen"))
                    break
                back.click().run()
                _check(at, where + " back", problems)
                continue
            if roll < 0.22:
                _button(at, "No sé").click().run()
                _check(at, where + " no sé", problems)
                continue
            try:
                if item.get("choices"):
                    choice = item["target_form"] if roll < 0.6 else rng.choice(item["choices"])
                    at.radio(key=f"choice_{item['id']}").set_value(choice)
                else:
                    hint = _button(at, "Pista")
                    if roll < 0.3 and hint and not hint.disabled:
                        hint.click().run()
                        _check(at, where + " hint", problems)
                    answer = (item["target_form"] if roll < 0.6
                              else sd._normalize_for_grading(item["target_form"]) if roll < 0.75 else "xyz")
                    at.text_input(key=f"answer_{item['id']}").set_value(answer)
            except KeyError:
                problems.append((where, "the question has no answer box"))
                break
            _button(at, "Submit").click().run()
            _check(at, where + " submit", problems)
        else:
            problems.append((cmd, "did not finish in 80 steps"))
        review = _button(at, "Repasar lo que fallé")
        if review is not None and not review.disabled:
            review.click().run()
            _check(at, cmd + " repasar lo que fallé", problems)
    assert problems == []
