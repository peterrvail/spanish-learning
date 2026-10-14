import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import progress  # noqa: E402
import spanish_drill as sd  # noqa: E402


def item(target, **kw):
    return {"prompt": "p", "target_form": target, "exercise_type": "t", **kw}


@pytest.mark.parametrize("answer,target,ok,accent_fix", [
    ("hablé", "hablé", True, False),
    ("hable", "hablé", True, True),
    ("HABLÉ ", "hablé", True, False),
    ("hablo", "hablé", False, False),
    ("", "hablé", False, False),
    ("yo hable", "Yo hablé.", True, True),
    ("hablé", "Yo hablé.", True, False),                 # subject pronoun optional
    ("¿Tiene suelto?", "¿Tiene cambio/suelto?", True, False),
    ("tiene cambio", "¿Tiene cambio/suelto?", True, False),  # missing ¿? is fine
    ("Para ser honesta", "Para ser honesto/a.", True, False),
    ("Para ser honesto", "Para ser honesto/a.", True, False),
])
def test_check_answer(answer, target, ok, accent_fix):
    got_ok, _, got_fix = sd.check_answer(answer, item(target))
    assert (got_ok, got_fix) == (ok, accent_fix)


def test_explicit_accepted_forms_win():
    it = item("aquí", accepted_forms=["aquí", "acá"])
    assert sd.check_answer("aca", it)[:2] == (True, "acá")


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("SPANISH_PROGRESS_DB", str(tmp_path / "p.db"))


def test_leitner_flow(db):
    t0 = datetime(2026, 1, 1, 12)
    it = item("fui")
    progress.record_attempt(it, False, module="preterito", now=t0)
    assert [i["target_form"] for i in progress.due_items(now=t0)] == ["fui"]
    progress.record_attempt(it, True, module="preterito", now=t0)         # box 1 -> +1 day
    assert progress.due_items(now=t0 + timedelta(hours=1)) == []
    assert progress.due_count(now=t0 + timedelta(days=1)) == 1
    t1 = t0 + timedelta(days=1)
    progress.record_attempt(it, True, module="preterito", now=t1)         # box 2 -> +7 days
    assert progress.due_count(now=t1 + timedelta(days=6)) == 0
    assert progress.due_count(now=t1 + timedelta(days=7)) == 1
    progress.record_attempt(it, False, module="preterito", now=t1)        # miss resets
    assert progress.due_count(now=t1) == 1


def test_never_missed_cards_not_queued(db):
    progress.record_attempt(item("fui"), True, now=datetime(2026, 1, 1))
    assert progress.due_count(now=datetime(2030, 1, 1)) == 0


def test_breakdown_groups_by_type_then_module():
    a = [{"is_correct": True, "exercise_type": "x", "module": "m"},
         {"is_correct": False, "exercise_type": "x", "module": "m"},
         {"is_correct": True, "exercise_type": "y", "module": "m"}]
    assert dict(progress.breakdown(a)) == {"x": (1, 2), "y": (1, 1)}
    a[2]["module"] = "n"
    assert dict(progress.breakdown(a)) == {"m": (1, 2), "n": (1, 1)}


def test_durations():
    assert sd.drill_duration("mixto") == 600
    assert sd.drill_duration("rutina") == 300
    assert sd.drill_duration("mixto", 180) == 180


def test_every_module_builds_items_that_grade_themselves():
    for module in ["imperativo", "pronombres", "cambios", "pasado", "preterito", "pluscuam", "por_para",
                   "demostrativos", "adverbios", "adjetivos", "numeros", "reflexivos", "participios",
                   "futuro", "estructuras", "lugares", "rutina", "gerundio", "vocabulario",
                   "indefinidos", "preposiciones", "ejercicio", "mixto"]:
        items = sd.get_drill_items(module)
        assert items, module
        for it in items:
            assert sd.check_answer(it["target_form"], it)[0], (module, it["target_form"])


def test_ui_drill_logs_and_summarizes(db):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", "app", "spanish_drill.py"), default_timeout=30)
    at.session_state["active_command"] = "!drill numeros"
    at.run()
    assert not at.exception
    # Answer wrong, continue, then answer right (accent-free) and finish via skip.
    at.text_input[0].set_value("zzz")
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert any("Incorrect" in e.value for e in at.error)
    next(b for b in at.button if "Continuar" in b.label).click()
    at.run()
    assert progress.due_count() == 1
    assert len(at.session_state["answers"]) == 1
    # Force the end-of-drill screen.
    at.session_state["current_item_index"] = len(at.session_state["drill_items"])
    at.run()
    assert not at.exception
    assert any("Por tipo" in m.value for m in at.markdown)
    assert any("Repasar lo que fallé" in b.label for b in at.button)
    # Review queue renders in Repaso.
    at.session_state["active_command"] = "!repasar fallos"
    at.run()
    assert not at.exception
