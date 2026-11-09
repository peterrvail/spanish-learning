import os
import re
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import conversation  # noqa: E402
import external  # noqa: E402
import flashcards  # noqa: E402
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
                   "indefinidos", "preposiciones", "ejercicio", "estar_gerundio", "condicional",
                   "ser_estar", "subjuntivo", "gustar", "mixto"]:
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



def test_estar_gerundio_covers_every_tense_and_the_irregulars():
    import collections, json
    seen = collections.Counter()
    for _ in range(50):
        items = sd.get_estar_gerundio_drill_items()
        assert len(items) == 16
        seen.update(i["exercise_type"] for i in items)
    # Present, future and the four pasts each get ~2 questions per drill.
    for tense in ("presente", "imperfecto", "preterito", "perfecto", "pluscuamperfecto", "futuro"):
        assert seen[f"estar_gerundio_{tense}"] == 100, tense
    assert seen["gerundio_irregular"] == 150 and seen["gerundio_regular"] == 50
    # The lesson's irregular groups are all there.
    d = json.load(open(os.path.join(sd.GRAMMAR_DIR, "estar_gerundio.json")))["estar_gerundio"]
    gerunds = {v["infinitive"]: v["gerund"] for g in d["irregular_groups"] for v in g["verbs"]}
    assert {"dormir": "durmiendo", "poder": "pudiendo", "ir": "yendo", "oír": "oyendo",
            "traer": "trayendo", "reír": "riendo", "vestir": "vistiendo"}.items() <= gerunds.items()


def test_estar_gerundio_skips_verbs_not_used_in_the_progressive():
    for _ in range(100):
        for i in sd.get_estar_gerundio_drill_items():
            if i["prompt"].startswith("Estar + gerundio"):
                assert not any(f"'{v}'" in i["prompt"] for v in ("poder", "preferir", "creer", "ir")), i["prompt"]


def test_estar_gerundio_compound_pasts():
    items = [i for _ in range(30) for i in sd.get_estar_gerundio_drill_items()]
    perfect = next(i for i in items if i["exercise_type"] == "estar_gerundio_perfecto" and i["prompt"].startswith("Estar"))
    assert perfect["target_form"].split()[1] == "estado" and perfect["target_form"].split()[0] in {"he", "has", "ha", "hemos", "han"}
    pluperfect = next(i for i in items if i["exercise_type"] == "estar_gerundio_pluscuamperfecto" and i["prompt"].startswith("Estar"))
    assert pluperfect["target_form"].startswith(("había estado", "habías estado", "habíamos estado", "habían estado"))
    assert sd.check_answer(pluperfect["target_form"].replace("í", "i"), pluperfect)[:3:2] == (True, True)  # accent forgiven, flagged


def test_estar_gerundio_sentence_answers_match_the_tables():
    import json, re
    d = json.load(open(os.path.join(sd.GRAMMAR_DIR, "estar_gerundio.json")))["estar_gerundio"]
    gerund = {v["infinitive"]: v["gerund"] for v in d["regular_verbs"]}
    gerund.update({v["infinitive"]: v["gerund"] for g in d["irregular_groups"] for v in g["verbs"]})
    assert set(d["tense_notes"]) == set(d["estar_forms"]) == set(sd._TENSE_LABELS)
    for x in d["sentences"]:
        estar, ger = x["answer"].rsplit(" ", 1)
        assert estar in d["estar_forms"][x["tense"]].values(), x
        verb = re.search(r"\((\w+)\)", x["sentence"]).group(1)
        if verb in gerund:
            assert ger == gerund[verb], x


def test_estar_gerundio_is_in_menu_review_and_mixto():
    import json
    assert ("🎬 Estar + gerundio", "!drill estar_gerundio") in sd.DRILL_COMMANDS
    concept = sd.get_module_concept("estar_gerundio")
    assert len(concept["uses"]) == 5 + 6  # formation, 3 irregular groups, stative note; one per tense
    assert "estar_gerundio" in sd._MIXTO_MODULES and "progresivo" in sd.KNOWN_MODULES
    sentences = json.load(open(os.path.join(sd.GRAMMAR_DIR, "estar_gerundio.json")))["estar_gerundio"]["sentences"]
    oir = next(x for x in sentences if x["answer"] == "estaba oyendo")
    assert "estaba escuchando" in oir["also_accepted"]



def test_flashcard_deck_building_and_requeue():
    import random as _r
    cards = [{"id": str(i), "deck": "a" if i < 8 else "b"} for i in range(12)]
    deck = flashcards.build_deck(cards, {"a"}, 5, due_keys={"6", "7"}, key_of=lambda c: c["id"], rng=_r.Random(1))
    assert len(deck) == 5 and {c["id"] for c in deck[:2]} == {"6", "7"} and all(c["deck"] == "a" for c in deck)
    assert len(flashcards.build_deck(cards, {"a", "b"}, 0)) == 12
    assert flashcards.requeue(list("abcdef"), 0) == list("bcdaef")
    assert flashcards.requeue(list("ab"), 0) == list("ba")


def test_flashcard_html_is_one_line_and_escaped():
    card = {"spanish": "<b>x</b>", "english": "y", "category": "c", "gender": "", "note": "", "example": "",
            "example_english": "", "is_number": False}
    markup = flashcards.card_html(card, "es_en", "f1")
    assert "\n" not in markup and "<b>x</b>" not in markup and "&lt;b&gt;" in markup


def test_flashcards_flow(db):
    at = _app()
    at.session_state["active_command"] = "!tarjetas"
    at.run()
    next(r for r in at.radio if r.label == "Tarjetas").set_value("10")
    next(b for b in at.button if "Empezar" in b.label).click()
    at.run()
    assert not at.exception and at.session_state["fc"]["total"] == 10
    first = at.session_state["fc"]["queue"][0]
    next(b for b in at.button if "Otra vez" in b.label).click()
    at.run()
    assert at.session_state["fc"]["queue"].index(first) == 3          # comes back 3 cards later
    assert progress.due_count() == 1                                   # and into the review queue
    for _ in range(10):                                                # 10 cards, the missed one included
        next(b for b in at.button if "Lo sabía" in b.label).click()
        at.run()
    assert any("Mazo terminado" in s.value for s in at.success)
    assert any("9 de 10" in s.value for s in at.success)
    assert progress.due_count() == 0                                   # relearned: due tomorrow, not now
    next(b for b in at.button if "Nuevo mazo" in b.label).click()
    at.run()
    assert "fc" not in at.session_state



def _reference():
    import json
    return json.load(open(flashcards.REFERENCE_FILE))


def test_reference_matches_the_document():
    ref = _reference()
    entries = [e for p in ref["parts"] for g in p["groups"] for e in g["entries"]]
    assert len(entries) == ref["_meta"]["total"] == 3563
    sizes = {p["id"]: sum(len(g["entries"]) for g in p["groups"]) for p in ref["parts"]}
    assert sizes == {"expresiones": 640, "verbos": 533, "sustantivos_vida_diaria": 787,
                     "sustantivos_mundo": 858, "adjetivos": 407, "palabras_pequenas": 338}
    assert all(e["spanish"] and e["english"] and e["first_seen"] for e in entries)


def test_flashcards_are_built_from_the_reference():
    cards = flashcards.load_cards()
    ref_cards = [c for c in cards if not c["deck"].startswith("notas_de_clase")]
    assert len(ref_cards) == 3563 and len({c["id"] for c in cards}) == len(cards)
    decks = flashcards.decks(cards)
    assert len([d for d in decks if d.startswith("expresiones:")]) == 9      # one deck per situation
    assert decks["verbos:todos"] == 533 and decks["adjetivos:todos"] == 407  # verbs, adjectives: one deck each
    assert flashcards.deck_label("expresiones:saludos_y_cortesia") == "💬 Expresiones: saludos y cortesía"
    spanish = {c["spanish"] for c in cards}
    assert {"el", "él", "si", "sí"} <= spanish                                # accent pairs stay separate
    cocina = next(c for c in cards if c["spanish"] == "la cocina")
    assert cocina["gender"] == "f" and cocina["lesson_num"] is not None
    assert not any(c["gender"] for c in cards if c["deck"].startswith(("verbos", "adjetivos", "expresiones")))
    acabar = next(c for c in cards if c["spanish"] == "acabar de")
    assert acabar["lesson"] == "Lección 23" and acabar["example"] == "Acabo de llegar a casa"
    assert "Lección 23" in flashcards.card_html(acabar, "es_en", "x")


def test_class_note_examples_attach_to_reference_cards_and_extras_are_kept():
    cards = flashcards.load_cards()
    gotera = next(c for c in cards if c["spanish"] == "la gotera")
    assert not gotera["deck"].startswith("notas_de_clase")                    # it's a reference card...
    assert gotera["example_from_class"] and gotera["example_english"]         # ...with the whiteboard example
    extras = {c["spanish"] for c in cards if c["deck"] == "notas_de_clase:extra"}
    assert "Vaya recto." in extras and "la gotera" not in extras
    assert sum(1 for c in cards if c["example"]) > 600


def test_flashcard_lesson_helpers():
    assert flashcards.lesson_number("L95") == 95 and flashcards.lesson_number("L112.5") == 112.5
    assert flashcards.lesson_number("Pasado simple") is None
    assert flashcards.lesson_range(flashcards.load_cards()) == (1, 119)
    assert flashcards._key("¿A quién le importa?") == flashcards._key("a quien le importa")
    assert "inclinado" in flashcards._match_keys("inclinado/a")
    assert "la pasa" in flashcards._match_keys("las pasas")


def test_flashcards_by_lesson_range(db):
    at = _app()
    at.session_state["active_command"] = "!tarjetas"
    at.run()
    next(r for r in at.radio if r.label == "Elegir por").set_value("Lección")
    at.run()
    assert at.slider[0].value == (110, 119)                                   # default: last ten lessons
    at.slider[0].set_value((119, 119))
    next(r for r in at.radio if r.label == "Tarjetas").set_value("Todas")
    next(b for b in at.button if "Empezar" in b.label).click()
    at.run()
    cards = {c["id"]: c for c in flashcards.load_cards()}
    queue = at.session_state["fc"]["queue"]
    assert queue and all(cards[cid]["lesson_num"] == 119 for cid in queue)



def test_language_transfer_data():
    data = external.load_lt()
    assert len(data["topics"]) == 27 and [t["track"] for t in data["tracks"]] == list(range(1, 91))
    assert [t["track"] for t in data["tracks"] if not t["topics"]] == [1, 6, 28, 84, 90]
    modules = {m for t in data["topics"] for m in t["app_modules"]}
    assert modules <= sd.KNOWN_MODULES                                    # every mapped drill exists
    for t in data["topics"]:
        if t["status"] != "gap":
            assert t["app_modules"], t["id"]                                  # covered topics are drilled
    # A gap topic can be drilled ahead of the lessons: the subjunctive is.
    assert next(t for t in data["topics"] if t["id"] == "subjuntivo")["app_modules"] == ["subjuntivo"]


def test_language_transfer_tracks_per_module():
    assert external.ranges(external.tracks_for_module("preterito")) == "58–64, 87–89"
    assert external.tracks_for_module("numeros") == []
    assert external.tracks_for_module("condicional") == [41]
    assert external.tracks_for_module("estar_gerundio") == [34, 35]
    assert external.ranges([1, 2, 3, 5, 7, 8]) == "1–3, 5, 7–8"


def test_repaso_shows_language_transfer_tracks(db):
    at = _app()
    at.session_state["active_command"] = "!repasar preterito"
    at.run()
    assert any("Language Transfer" in m.value and "58–64, 87–89" in m.value for m in at.markdown)
    at = _app()
    at.session_state["active_command"] = "!repasar numeros"
    at.run()
    assert not any("Language Transfer" in m.value for m in at.markdown)


def test_language_transfer_ticks_survive_a_restart(db):
    at = _app()
    at.session_state["active_command"] = "!lt"
    at.run()
    assert any("0 / 90" in m.value for m in at.markdown)
    at.checkbox(key="lt_1").check().run()
    at.checkbox(key="lt_2").check().run()
    assert not at.exception
    at = _app()                                                           # a fresh app: nothing in session state
    at.session_state["active_command"] = "!lt"
    at.run()
    assert any("2 / 90" in m.value and "siguiente: **3**" in m.value for m in at.markdown)
    assert at.checkbox(key="lt_1").value and not at.checkbox(key="lt_3").value
    at.checkbox(key="lt_1").uncheck().run()
    assert external.load_done(external.progress_path(progress.db_path())) == {2}


def test_condicional_and_ser_estar_drills():
    cond = sd.get_condicional_drill_items()
    assert len(cond) == 15
    tener = [i for _ in range(40) for i in sd.get_condicional_drill_items() if "'tener'" in i["prompt"]]
    assert all(i["target_form"].startswith("tendr") for i in tener) and tener
    types = {i["exercise_type"] for _ in range(20) for i in sd.get_ser_estar_drill_items()}
    assert types == {"ser_estar_ser", "ser_estar_estar", "ser_estar_hay"}
    for module, label in [("condicional", "🤔 Condicional"), ("ser_estar", "⚖️ Ser, estar y hay")]:
        assert (label, f"!drill {module}") in sd.DRILL_COMMANDS and sd.get_module_concept(module)
        assert module in sd._MIXTO_MODULES



def _subj_forms():
    import json
    d = json.load(open(os.path.join(sd.GRAMMAR_DIR, "subjunctive.json")))["subjunctive"]
    return d, {v["infinitive"]: v for g in d["groups"] for v in g["verbs"]}


def test_subjunctive_forms():
    d, verbs = _subj_forms()
    f = lambda inf, person: verbs[inf]["forms"][person]
    assert [f("dar", p) for p in ("yo", "nosotros")] == ["dé", "demos"]
    assert f("dormir", "nosotros") == "durmamos" and f("dormir", "tú") == "duermas"   # -ir: o→u in nosotros
    assert f("sentir", "nosotros") == "sintamos" and f("pensar", "nosotros") == "pensemos"
    assert f("empezar", "yo") == "empiece" and f("empezar", "nosotros") == "empecemos"
    assert f("conocer", "ellos/ustedes") == "conozcan" and f("buscar", "yo") == "busque"
    # Agrees with the subjunctive already in verbs.json for its 12 verbs.
    import json
    core = {v["infinitive"]: v["moods"]["present_subjunctive"]
            for v in json.load(open(os.path.join(sd.DATA_DIR, "verbs", "verbs.json")))["verbs"]}
    for inf, forms in core.items():
        assert verbs[inf]["forms"]["nosotros"] == forms["nosotros"] and verbs[inf]["forms"]["yo"] == forms["yo"]


def test_subjunctive_drill_mix():
    for _ in range(50):
        items = sd.get_subjuntivo_drill_items()
        kinds = [i["exercise_type"] for i in items]
        assert len(items) == 16 and kinds.count("subjuntivo_formas") == 6
        assert kinds.count("indicativo_contraste") == 3                        # knowing WHEN, not just the forms
        for i in items:
            if i["exercise_type"] == "subjuntivo_formas":
                assert "'llover'" not in i["prompt"] and "'gustar'" not in i["prompt"]   # no "yo llueva"


def test_subjunctive_is_wired_in(db):
    assert ("🌱 Subjuntivo presente", "!drill subjuntivo") in sd.DRILL_COMMANDS
    assert "subjuntivo" in sd._MIXTO_MODULES and sd.drill_duration("subjuntivo") == 420
    concept = sd.get_module_concept("subjuntivo")
    assert any(u["name"].startswith("Cuándo: Pero indicativo") for u in concept["uses"])
    assert external.ranges(external.tracks_for_module("subjuntivo")) == "69–71, 74, 76–77, 79, 81–82, 85"
    at = _app()
    at.session_state["active_command"] = "!repasar subjuntivo"
    at.run()
    assert not at.exception
    assert any("69–71, 74, 76–77, 79, 81–82, 85" in m.value for m in at.markdown)


def test_explanations_show_the_completed_sentence():
    assert sd.fill_blank("Cuando yo ___ (tener) tiempo, leo.", "tengo") == "Cuando yo tengo tiempo, leo."
    assert sd.fill_blank("Hoy ___ martes.", "es") == "Hoy es martes."
    for gen in (sd.get_subjuntivo_drill_items, sd.get_estar_gerundio_drill_items, sd.get_ser_estar_drill_items):
        for item in gen():
            assert "___" not in item["explanation"] and not re.search(r"\w \(\w+\) ", item["explanation"].split(" — ")[0])



def _gustar():
    import json
    return json.load(open(os.path.join(sd.GRAMMAR_DIR, "gustar_verbs.json")))["gustar_verbs"]


def test_gustar_data_agrees():
    d = _gustar()
    person = {"mí": "me", "ti": "te", "nosotros": "nos", "ellos": "les", "ellas": "les", "ustedes": "les", "los niños": "les"}
    for x in d["fill_in"]:
        who = re.search(r"\b[Aa] (mí|ti|nosotros|ellos|ellas|ustedes|los niños)\b", x["sentence"])
        assert x["answer"].split()[0] == (person[who.group(1)] if who else "le"), x
    singular_infinitives = next(x for x in d["fill_in"] if "bailar y cantar" in x["sentence"])
    assert singular_infinitives["answer"] == "me gusta"                     # two infinitives, still singular
    assert {v["infinitive"]: v["first_seen"] for v in d["verbs"]}["gustar"] == "L9"


def test_gustar_drill_mix_and_answers():
    for _ in range(30):
        items = sd.get_gustar_drill_items()
        kinds = [i["exercise_type"] for i in items]
        assert (kinds.count("gustar_completar"), kinds.count("gustar_traducir"), kinds.count("gustar_corregir")) == (8, 4, 3)
    d = _gustar()
    item = lambda x: {"target_form": x["spanish"], "also_accepted": x["also_accepted"]}
    coffee = next(x for x in d["translate"] if x["english"] == "I like coffee.")
    assert sd.check_answer("A mí me gusta el café", item(coffee))[0]        # with or without "a mí"
    yo_gusto = next(x for x in d["correct"] if x["english"] == "Yo gusto el café.")
    assert not sd.check_answer("Yo gusto el café.", item(yo_gusto))[0]       # leaving the mistake is wrong


def test_gustar_is_wired_in(db):
    assert ("💛 Gustar y similares", "!drill gustar") in sd.DRILL_COMMANDS
    assert "gustar" in sd._MIXTO_MODULES and sd.drill_duration("gustar") == 420
    concept = sd.get_module_concept("gustar")
    assert any("lección 9" in u["description"] for u in concept["uses"])   # links back to the lessons
    assert external.tracks_for_module("gustar") == [42, 45, 63]
    at = _app()
    at.session_state["active_command"] = "!repasar gustar"
    at.run()
    assert not at.exception and any("42, 45, 63" in m.value for m in at.markdown)
