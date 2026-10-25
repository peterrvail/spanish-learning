import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import conversation  # noqa: E402
import grading  # noqa: E402
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
    item = _start_typed_drill(at, "numeros")
    assert not at.exception
    # Answer wrong and continue; then jump to the end-of-drill screen.
    at.text_input(key=f"answer_{item['id']}").set_value("zzz")
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


def test_imperative_negative_accepts_bare_verb():
    items = sd.get_imperative_drill_items(sd.load_verbs(), count=200)
    neg = next(i for i in items if i["polarity"] == "negative")
    bare = neg["target_form"].split(" ", 1)[1]
    assert sd.check_answer(bare, neg)[0]
    assert sd.check_answer(neg["target_form"], neg)[0]
    # Prompts no longer leak the answer through a half-filled "¡Habla___!" blank.
    assert all("___" not in i["prompt"] for i in items)


def test_make_hint():
    assert sd.make_hint("se lo", 1) == "s_ __"
    assert sd.make_hint("¿Qué tal?", 2) == "¿Qu_ ___?"


def test_reflexive_explanation_strips_suffix_only():
    expl = {i["explanation"] for i in sd.get_reflexivos_drill_items(count=200)}
    assert not any("ntarse" in e for e in expl)


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(os.path.join(os.path.dirname(__file__), "..", "app", "spanish_drill.py"),
                             default_timeout=30)


def test_typed_command_does_not_override_buttons(db):
    at = _app()
    at.run()
    at.sidebar.text_input(key="desktop_typed_cmd").set_value("!drill numeros")
    at.run()
    assert at.session_state["drill_module"] == "numeros"
    next(b for b in at.sidebar.button if b.label.startswith("📜 Pretérito")).click()
    at.run()
    assert at.session_state["active_command"] == "!drill preterito"
    assert at.session_state["drill_module"] == "preterito"
    # Typing a different drill mid-drill really switches drills.
    at.sidebar.text_input(key="desktop_typed_cmd").set_value("!drill futuro")
    at.run()
    assert at.session_state["drill_module"] == "futuro"
    assert not at.exception


def _start_typed_drill(at, module):
    at.session_state["active_command"] = f"!drill {module}"
    at.run()
    # Make sure the first item is a typed one, not multiple choice.
    for it in at.session_state["drill_items"]:
        it.pop("choices", None)
    at.run()
    return at.session_state["drill_items"][0]


def test_accent_button_keeps_typed_text(db):
    at = _app()
    item = _start_typed_drill(at, "numeros")
    at.text_input(key=f"answer_{item['id']}").set_value("ma")
    next(b for b in at.button if b.label == "ñ").click()
    at.run()
    assert at.text_input(key=f"answer_{item['id']}").value == "mañ"
    assert at.session_state["answers"] == []  # an accent tap is not a submission


def test_no_se_reveals_and_queues(db):
    at = _app()
    item = _start_typed_drill(at, "numeros")
    next(b for b in at.button if "No sé" in b.label).click()
    at.run()
    assert any(item["target_form"] in i.value for i in at.info)
    assert at.session_state["answers"][0]["is_correct"] is False
    assert progress.due_count() == 1


def test_hinted_correct_answer_still_queued(db):
    at = _app()
    item = _start_typed_drill(at, "numeros")
    next(b for b in at.button if "Pista" in b.label).click()
    at.run()
    assert any("Pista" in i.value for i in at.info)
    assert item["target_form"] not in " ".join(i.value for i in at.info) or len(item["target_form"]) <= 2
    at.text_input(key=f"answer_{item['id']}").set_value(item["target_form"])
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert at.session_state["score"] == 1
    assert progress.due_count() == 1


def test_streak_days():
    from datetime import date
    today = date(2026, 3, 10)
    d = lambda n: today - timedelta(days=n)
    assert progress.streak_days([d(0), d(1), d(2), d(4)], today) == 3
    assert progress.streak_days([d(1), d(2)], today) == 2      # not broken before today's practice
    assert progress.streak_days([d(2)], today) == 0


def test_stats_and_progress_page(db):
    now = datetime(2026, 3, 10, 12)
    progress.record_attempt(item("fui"), True, module="preterito", now=now)
    progress.record_attempt(item("cero"), False, module="numeros", now=now - timedelta(days=8))
    s = progress.stats(now=now)
    assert s["total"] == 2 and s["streak"] == 1
    assert s["week"] == (1, 1) and s["prev_week"] == (0, 1)
    assert s["by_module"][0][0] == "numeros"  # weakest first
    at = _app()
    at.session_state["active_command"] = "!progreso"
    at.run()
    assert not at.exception
    assert any(m.label == "Intentos" for m in at.metric)


class _Block:
    def __init__(self, **d):
        self.d = d

    def to_dict(self):
        return dict(self.d)


class _FakeStream:
    def __init__(self, text, stop_reason):
        self.text_stream = iter([text[:5], text[5:]])
        self._final = type("M", (), {"stop_reason": stop_reason, "content": [
            _Block(type="thinking", thinking="", signature="sig"), _Block(type="text", text=text)]})()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._final


class FakeClient:
    """Records every request; replies with canned text."""
    def __init__(self, reply="¡Hola! ¿Qué tal?", stop_reason="end_turn"):
        self.calls, self.reply, self.stop_reason = [], reply, stop_reason
        self.beta = type("B", (), {"messages": self})()

    def stream(self, **kw):
        # Snapshot the messages: the caller keeps appending to the same list.
        self.calls.append({**kw, "messages": [dict(m) for m in kw["messages"]]})
        return _FakeStream(self.reply, self.stop_reason)


def test_stream_reply_request_shape_and_result():
    client, result = FakeClient(), {}
    text = "".join(conversation.stream_reply(client, "SYS", [{"role": "user", "content": "hola"}], result))
    assert text == "¡Hola! ¿Qué tal?"
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["output_config"] == {"effort": "low"}
    assert [b["type"] for b in result["content"]] == ["thinking", "text"]
    assert conversation.assistant_text(result["content"]) == "¡Hola! ¿Qué tal?"


def test_stream_reply_refusal_raises():
    with pytest.raises(conversation.ChatError):
        list(conversation.stream_reply(FakeClient(stop_reason="refusal"), "S", [{"role": "user", "content": "x"}], {}))


def test_chat_ui_appends_and_replays_history_verbatim(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(conversation, "credentials_configured", lambda *a: True)
    monkeypatch.setattr(conversation, "get_client", lambda *a: client)
    at = _app()
    at.session_state["active_command"] = "!hablar"
    at.run()
    at.chat_input[0].set_value("Ayer fui al cine.").run()
    assert not at.exception
    at.chat_input[0].set_value("Me gustó mucho.").run()
    first, second = client.calls
    assert first["system"] == second["system"]                # system prompt fixed per conversation
    assert second["messages"][:2] == [first["messages"][0],  # earlier turns replayed unchanged,
                                      {"role": "assistant", "content": [  # thinking block included
                                          {"type": "thinking", "thinking": "", "signature": "sig"},
                                          {"type": "text", "text": "¡Hola! ¿Qué tal?"}]}]
    assert len(at.session_state["chat_hablar"]) == 4


def test_chat_failure_drops_unanswered_turn(monkeypatch):
    monkeypatch.setattr(conversation, "credentials_configured", lambda *a: True)
    monkeypatch.setattr(conversation, "get_client", lambda *a: FakeClient(stop_reason="refusal"))
    at = _app()
    at.session_state["active_command"] = "!rol restaurante"
    at.run()
    at.chat_input[0].set_value("Hola").run()
    assert not at.exception
    assert at.error and at.session_state["chat_rol_" + at.session_state["rol_scenario_restaurante"]] == []


def test_without_credentials_falls_back_to_instructions(monkeypatch):
    monkeypatch.setattr(conversation, "credentials_configured", lambda *a: False)
    at = _app()
    at.session_state["active_command"] = "!hablar"
    at.run()
    assert not at.exception and not at.chat_input
    assert any("Chatear aquí mismo" in e.label for e in at.expander)


def test_missing_credentials_at_request_time_is_a_chat_error(monkeypatch):
    class NoCreds(FakeClient):
        def stream(self, **kw):
            raise TypeError("Could not resolve authentication method. Expected one of api_key, ...")
    with pytest.raises(conversation.ChatError):
        list(conversation.stream_reply(NoCreds(), "S", [{"role": "user", "content": "x"}], {}))


def test_adverb_synonyms_accept_both_answers():
    items = sd.get_adverbios_drill_items(count=999)
    prompts = [i["prompt"] for i in items]
    assert len(prompts) == len(set(prompts))  # one question per English word
    outside = next(i for i in items if i["prompt"].endswith(": outside"))
    assert sd.check_answer("fuera", outside)[0] and sd.check_answer("afuera", outside)[0]


def test_module_names_normalized_and_unknown_rejected(db):
    assert sd.parse_command("!drill Pretérito") == ("drill", "preterito")
    assert all(cmd.split()[1] in sd.KNOWN_MODULES for _, cmd in sd.DRILL_COMMANDS if cmd.startswith("!drill "))
    at = _app()
    at.session_state["active_command"] = "!drill zzz"
    at.run()
    assert not at.exception
    assert any("No existe el módulo" in e.value for e in at.error)
    assert "drill_items" not in at.session_state  # no imperative drill started under the typo


class FakeGrader:
    """Stands in for client.beta.messages.create in grading.judge."""
    def __init__(self, text='{"correct": true, "feedback": "Also natural."}', stop_reason="end_turn", exc=None):
        self.calls, self.text, self.stop_reason, self.exc = [], text, stop_reason, exc
        self.beta = type("B", (), {"messages": self})()

    def create(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc
        block = type("T", (), {"type": "text", "text": self.text})()
        return type("R", (), {"stop_reason": self.stop_reason, "content": [block]})()


SENTENCE = {"prompt": "Translate to Spanish (imperfect): I wanted to ask you a favor.", "id": 0,
            "target_form": "Quería pedirte un favor.", "exercise_type": "imperfect", "explanation": "x"}


def test_grading_eligible_only_for_typed_sentences():
    assert grading.eligible(SENTENCE)
    assert grading.eligible(dict(SENTENCE, target_form="Tenía cansancio."))  # short, but a sentence
    assert not grading.eligible(dict(SENTENCE, target_form="quería"))
    assert not grading.eligible(dict(SENTENCE, target_form="se lo"))
    assert not grading.eligible(dict(SENTENCE, choices=["a", "b"]))


def test_judge_request_and_verdicts():
    client = FakeGrader()
    assert grading.judge(client, SENTENCE, "Te quería pedir un favor") == {"correct": True, "feedback": "Also natural."}
    kw = client.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["fallbacks"] == "default"
    assert kw["output_config"]["effort"] == "low" and kw["output_config"]["format"]["type"] == "json_schema"
    assert "Te quería pedir un favor" in kw["messages"][0]["content"]
    # Every failure means "no verdict", so the drill keeps exact grading.
    assert grading.judge(FakeGrader(stop_reason="refusal"), SENTENCE, "x") is None
    assert grading.judge(FakeGrader(stop_reason="max_tokens"), SENTENCE, "x") is None
    assert grading.judge(FakeGrader(text="not json"), SENTENCE, "x") is None
    assert grading.judge(FakeGrader(exc=TypeError("Could not resolve authentication method")), SENTENCE, "x") is None


def test_word_diff():
    assert grading.word_diff("Yo vivo en Madrid", "Vivía en Madrid.") == "~~Yo vivo~~ **Vivía** en Madrid."
    assert grading.word_diff("vivia en madrid", "Vivía en Madrid.") == "Vivía en Madrid."  # accents/case ignored
    assert grading.word_diff("Vivía en *Madrid", "Vivía en Madrid.") == "Vivía en ~~\\*Madrid~~ **Madrid.**"  # escaped
    assert grading.word_diff("hola", "hola") is None                                      # one-word target
    assert grading.word_diff("", "Vivía en Madrid.") is None
    assert grading.word_diff("Yo quiero pedir un favor", "Mientras estudiaba, oí un ruido extraño.") is None


def _sentence_drill(at, monkeypatch, client):
    monkeypatch.setattr(conversation, "credentials_configured", lambda *a: True)
    monkeypatch.setattr(conversation, "get_client", lambda *a: client)
    at.session_state["active_command"] = "!drill pasado"
    at.run()
    for it in at.session_state["drill_items"]:
        it.pop("choices", None)
    at.run()
    item = at.session_state["drill_items"][0]
    return item


def test_drill_accepts_paraphrase_claude_approves(db, monkeypatch):
    client = FakeGrader()
    at = _app()
    item = _sentence_drill(at, monkeypatch, client)
    at.text_input(key=f"answer_{item['id']}").set_value("una paráfrasis válida")
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert not at.exception
    assert len(client.calls) == 1 and at.session_state["score"] == 1
    assert any("también vale" in m.value for m in at.success)
    assert progress.due_count() == 0  # logged as correct


def test_drill_shows_claude_feedback_and_diff_when_wrong(db, monkeypatch):
    client = FakeGrader(text='{"correct": false, "feedback": "Use the imperfect here."}')
    at = _app()
    item = _sentence_drill(at, monkeypatch, client)
    # One word off: close enough for the word diff to be shown.
    words = item["target_form"].split()
    at.text_input(key=f"answer_{item['id']}").set_value(" ".join(["zzz"] + words[1:]))
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert at.session_state["score"] == 0 and progress.due_count() == 1
    assert any("Use the imperfect" in i.value for i in at.info)
    assert any(m.value.startswith("🔍") and "~~zzz~~" in m.value for m in at.markdown)


def test_claude_not_asked_when_exact_match_or_single_word(db, monkeypatch):
    client = FakeGrader()
    at = _app()
    item = _sentence_drill(at, monkeypatch, client)
    at.text_input(key=f"answer_{item['id']}").set_value(item["target_form"])
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert client.calls == [] and at.session_state["score"] == 1


def _find(module, prompt_part, tries=60):
    """The item in `module` whose prompt contains prompt_part (pools are sampled)."""
    for _ in range(tries):
        for it in sd._build_drill_items(module):
            if prompt_part in it["prompt"]:
                return it
    raise AssertionError(f"no {module} item with {prompt_part!r}")


def _ok(answer, item):
    return sd.check_answer(answer, item)[0]


def test_answer_key_corrections():
    assert _find("pasado", "3 o'clock")["target_form"].startswith("Eran las tres")
    assert _find("participios", "'imprimir'")["target_form"] == "impreso"
    assert _find("participios", "'proveer'")["target_form"] == "provisto"
    assert _find("participios", "'maldecir'")["target_form"] == "maldecido"


def test_tu_and_usted_both_accepted_when_english_is_ambiguous():
    hungry = _find("estructuras", "Are you hungry")
    assert _ok("¿Tiene hambre? ¿Tiene sed?", hungry) and _ok("tienes hambre tienes sed", hungry)
    origin = _find("estructuras", "Where are you from")
    assert _ok("¿De dónde eres?", origin) and _ok("¿De dónde es usted?", origin)
    assert _ok("Qué significa tu nombre", _find("estructuras", "[your name]"))  # no literal brackets


def test_common_variants_accepted():
    assert _ok("Voy en tren", _find("rutina", "I go by train"))
    assert _ok("Juego al fútbol", _find("rutina", "I play soccer"))
    assert _ok("Estaba cansada", _find("pasado", "I was tired."))
    assert _ok("en resumen", _find("preposiciones", "in summary"))
    assert _ok("dentro", _find("adverbios", ": inside"))
    assert _ok("adelante", _find("adverbios", ": in front"))


def test_solo_is_not_corrected_to_old_accent():
    only = _find("adverbios", ": only")
    assert sd.check_answer("solo", only) == (True, "solo", False)  # no "Ojo con la tilde" warning


def test_optional_se_verbs_accept_both_forms():
    for infinitive in ("divertir(se)", "acostar(se)"):
        item = _find("cambios", f"'{infinitive}'")
        bare = item["target_form"].removeprefix("me ")
        assert _ok(bare, item) and _ok("me " + bare, item)


def test_pausa_and_resumen_stop_the_clock(db):
    at = _app()
    _start_typed_drill(at, "numeros")
    at.session_state["drill_start_time"] = datetime.now() - timedelta(seconds=60)
    at.session_state["active_command"] = "!pausa"
    at.run()
    assert at.session_state["paused_at"]
    # Ten minutes reading the explanation: the drill ran 60s, then sat paused for 10 min.
    at.session_state["paused_at"] = at.session_state["paused_at"] - timedelta(minutes=10)
    at.session_state["drill_start_time"] = at.session_state["drill_start_time"] - timedelta(minutes=10)
    next(b for b in at.button if "Volver al drill" in b.label).click()
    at.run()
    at.run()
    elapsed = (datetime.now() - at.session_state["drill_start_time"]).total_seconds()
    assert 55 <= elapsed <= 70          # ...don't count against the drill
    assert "paused_at" not in at.session_state
    assert "Drill Complete" not in " ".join(s.value for s in at.success)
