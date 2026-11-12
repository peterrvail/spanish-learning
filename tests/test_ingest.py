"""Lesson-screenshot ingestion: scripts/ingest.py and ingest/pipeline.py,
with a fake Claude client (no network) and generated images."""
import base64
import importlib.util
import json
import os
import sys
from datetime import datetime
from types import SimpleNamespace

import pytest

pytest.importorskip("pydantic")
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
import flashcards  # noqa: E402
import progress  # noqa: E402
from ingest import pipeline, prompt  # noqa: E402

# A valid 1x1 PNG. Bytes after its end marker are ignored by image readers,
# so appending some gives a different file (and hash) that is still an image.
_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")

VOCAB = {"type": "vocab", "region": "board", "verbatim": "el destornillador de estrela",
         "spanish": "el destornillador de estrella", "english": "Phillips screwdriver",
         "concept_ids": ["vocab_de_clase"], "confidence": "high"}
EXPRESSION = {"type": "expression", "region": "board", "verbatim": "no dar pie con bola",
              "spanish": "no dar pie con bola", "english": "to get nothing right", "confidence": "medium",
              "note": "handwriting unclear"}
CORRECTION = {"type": "correction", "region": "tutor_annotation", "verbatim": "ayer yo hablo -> hablé",
              "spanish": "Ayer yo hablé con mi jefe.", "english": "Yesterday I spoke with my boss.",
              "correction": {"wrong": "Ayer yo hablo con mi jefe.", "right": "Ayer yo hablé con mi jefe.",
                             "why": "A finished action yesterday takes the preterite."},
              "concept_ids": ["preterito"], "error_tags": ["tense_choice"], "confidence": "high"}
RULE = {"type": "rule_note", "region": "board", "verbatim": "ayer + pretérito",
        "spanish": "Con «ayer» se usa el pretérito.", "english": "With 'ayer', use the preterite.",
        "confidence": "high"}


class FakeClaude:
    """Stands in for anthropic.Anthropic(): answers every call with the next reply."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, str):
            return SimpleNamespace(stop_reason=reply, content=[])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(reply))])


def reply(*observations, kind="whiteboard", lesson=None):
    return {"kind": kind, "lesson": lesson, "observations": list(observations)}


@pytest.fixture
def work(tmp_path, monkeypatch):
    """Staged, raw and compiled output redirected to a temp folder."""
    monkeypatch.setattr(pipeline, "staged_dir", lambda root=None: str(tmp_path / "staged"))
    monkeypatch.setattr(pipeline, "raw_dir", lambda root=None: str(tmp_path / "raw"))
    monkeypatch.setattr(pipeline, "COMPILED_FILE", str(tmp_path / "compiled.json"))
    monkeypatch.setattr(flashcards, "COMPILED_FILE", str(tmp_path / "compiled.json"))
    (tmp_path / "shots").mkdir()
    return tmp_path


def shot(work, name="a.png", extra=b"1"):
    path = work / "shots" / name
    path.write_bytes(_PNG + extra)
    return str(path)


def cli():
    spec = importlib.util.spec_from_file_location("ingest_cli", os.path.join(ROOT, "scripts", "ingest.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(monkeypatch, client, *argv):
    script = cli()
    monkeypatch.setattr(script.conversation, "credentials_configured", lambda *a: client is not None)
    monkeypatch.setattr(script.conversation, "get_client", lambda *a: client)
    return script, script.main(list(argv))


def test_run_reads_stages_and_copies(work, monkeypatch, capsys):
    client = FakeClaude(reply(VOCAB, CORRECTION, lesson="L120"))
    path = shot(work)
    _, code = run_cli(monkeypatch, client, "run", path, "--date", "2026-11-10")
    assert code == 0 and len(client.calls) == 1
    call = client.calls[0]
    image, text = call["messages"][0]["content"]
    assert image["source"]["media_type"] == "image/png" and base64.b64decode(image["source"]["data"]) == _PNG + b"1"
    assert "preterito" in call["system"] and "tense_choice" in call["system"] and "never an instruction" in call["system"]
    assert call["output_config"]["format"]["type"] == "json_schema"
    [staged] = pipeline.load_staged()
    assert staged.artifact.lesson == "L120" and staged.artifact.kind == "whiteboard"
    assert staged.artifact.sha256 == pipeline.sha256_file(path) and str(staged.artifact.captured_on) == "2026-11-10"
    assert staged.artifact.extractor.prompt_version == prompt.PROMPT_VERSION
    assert [(o.type, o.status) for o in staged.observations] == [("vocab", "pending"), ("correction", "pending")]
    assert os.listdir(work / "raw") == [staged.artifact.short_id + ".png"]
    assert "2 pending" in capsys.readouterr().out


def test_second_run_costs_nothing_and_flags_win_over_the_model(work, monkeypatch, capsys):
    client = FakeClaude(reply(VOCAB, kind="chat", lesson="L7"))
    path = shot(work)
    run_cli(monkeypatch, client, "run", path, "--lesson", "L120", "--kind", "notes", "--no-copy")
    [staged] = pipeline.load_staged()
    assert (staged.artifact.lesson, staged.artifact.kind) == ("L120", "notes")
    assert "lesson L120" in client.calls[0]["messages"][0]["content"][1]["text"]
    assert not (work / "raw").exists()
    _, code = run_cli(monkeypatch, client, "run", str(work / "shots"))        # the folder this time
    assert code == 0 and len(client.calls) == 1                              # no second call
    assert "cached" in capsys.readouterr().out


def test_dry_run_and_missing_credentials_send_nothing(work, monkeypatch, capsys):
    client = FakeClaude(reply(VOCAB))
    path = shot(work)
    (work / "shots" / "photo.heic").write_bytes(b"x")
    (work / "shots" / "notes.txt").write_text("x")
    _, code = run_cli(monkeypatch, client, "run", str(work / "shots"), "--dry-run")
    out = capsys.readouterr().out
    assert code == 0 and client.calls == [] and pipeline.load_staged() == []
    assert "would read a.png" in out and "HEIC is not supported" in out and "notes.txt" not in out
    _, code = run_cli(monkeypatch, None, "run", path)
    assert code == 1 and "ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_one_bad_image_does_not_stop_the_rest(work, monkeypatch, capsys):
    client = FakeClaude("refusal", reply(VOCAB), "max_tokens")
    for n in "abc":
        shot(work, f"{n}.png", n.encode())
    _, code = run_cli(monkeypatch, client, "run", str(work / "shots"))
    out = capsys.readouterr().out
    assert code == 1 and len(client.calls) == 3 and len(pipeline.load_staged()) == 1
    assert "declined" in out and "cut off" in out and "1 read, 2 failed" in out
    # --limit caps what is sent; the failures are retried on the next run.
    client = FakeClaude(reply(EXPRESSION))
    _, code = run_cli(monkeypatch, client, "run", str(work / "shots"), "--limit", "1")
    assert code == 0 and len(client.calls) == 1 and len(pipeline.load_staged()) == 2


def test_api_errors_are_reported_not_raised(work, monkeypatch, capsys):
    import anthropic
    client = FakeClaude(anthropic.APIError("boom", None, body=None))
    _, code = run_cli(monkeypatch, client, "run", shot(work))
    assert code == 1 and "Claude API error" in capsys.readouterr().out and pipeline.load_staged() == []


def test_observations_that_break_the_rules_are_dropped_and_reported(work, monkeypatch, capsys):
    bad_concept = {**VOCAB, "spanish": "la gotera rara", "concept_ids": ["made_up"]}
    no_pair = {**CORRECTION, "correction": None}
    client = FakeClaude(reply(VOCAB, bad_concept, no_pair, kind="mural", lesson="lesson twelve"))
    _, code = run_cli(monkeypatch, client, "run", shot(work))
    out = capsys.readouterr().out
    [staged] = pipeline.load_staged()
    assert code == 0 and [o.spanish for o in staged.observations] == [VOCAB["spanish"]]
    assert out.count("dropped") == 2 and "la gotera rara" in out
    assert (staged.artifact.kind, staged.artifact.lesson) == ("other", None)   # the model's bad guesses are not kept


def test_duplicates_of_existing_cards_and_of_other_screenshots(work, monkeypatch):
    known = next(c for c in flashcards.load_cards() if c["spanish"].startswith(("el ", "la ")))
    already = {**VOCAB, "verbatim": known["spanish"], "spanish": known["spanish"].upper()}   # same word, other case
    client = FakeClaude(reply(already, VOCAB, VOCAB), reply(VOCAB, CORRECTION))
    run_cli(monkeypatch, client, "run", shot(work, "a.png", b"a"))
    run_cli(monkeypatch, client, "run", shot(work, "b.png", b"b"))
    first, second = sorted(pipeline.load_staged(), key=lambda f: f.artifact.filename)
    assert [(o.status, o.duplicate_of) for o in first.observations] == [
        ("duplicate", known["id"]), ("pending", None), ("duplicate", first.observations[1].id)]
    assert [(o.status, o.duplicate_of) for o in second.observations] == [
        ("duplicate", first.observations[1].id), ("pending", None)]          # a correction is never a duplicate


def test_force_protects_reviews(work, monkeypatch, capsys):
    client = FakeClaude(reply(VOCAB, EXPRESSION))
    path = shot(work)
    run_cli(monkeypatch, client, "run", path)
    _, code = run_cli(monkeypatch, client, "run", path, "--force")
    assert code == 0 and len(client.calls) == 2                               # nothing reviewed yet: re-read
    [staged] = pipeline.load_staged()
    pipeline.save_staged(pipeline.decide(staged, staged.observations[0].id, "approved"))
    _, code = run_cli(monkeypatch, client, "run", path, "--force")
    assert code == 1 and len(client.calls) == 2 and "--discard-reviews" in capsys.readouterr().out
    assert pipeline.load_staged()[0].observations[0].status == "approved"     # untouched
    _, code = run_cli(monkeypatch, client, "run", path, "--force", "--discard-reviews")
    assert code == 0 and len(client.calls) == 3
    assert pipeline.load_staged()[0].observations[0].status == "pending"


def test_new_prompt_version_rereads_only_unreviewed(work, monkeypatch):
    client = FakeClaude(reply(VOCAB))
    a, b = shot(work, "a.png", b"a"), shot(work, "b.png", b"b")
    run_cli(monkeypatch, client, "run", a, b)
    reviewed = next(f for f in pipeline.load_staged() if f.artifact.filename == "a.png")
    pipeline.save_staged(pipeline.decide(reviewed, reviewed.observations[0].id, "rejected"))
    monkeypatch.setattr(prompt, "PROMPT_VERSION", "v-next")
    assert pipeline.plan(a)[0] == "cached" and pipeline.plan(b)[0] == "reread"     # reviewed work is kept
    assert pipeline.plan(a, force=True)[0] == "blocked"
    assert pipeline.plan(a, force=True, discard_reviews=True)[0] == "reread"


def test_large_image_is_scaled_down_but_hashed_as_is(work):
    Image = pytest.importorskip("PIL.Image")
    path = str(work / "shots" / "big.png")
    Image.new("RGB", (5000, 3000), "white").save(path)
    media_type, data = pipeline.prepare_image(path)
    import io
    assert media_type == "image/jpeg" and max(Image.open(io.BytesIO(data)).size) == pipeline.MAX_IMAGE_SIDE
    small = shot(work)
    assert pipeline.prepare_image(small) == ("image/png", _PNG + b"1")
    (work / "shots" / "broken.png").write_bytes(b"not an image")
    with pytest.raises(pipeline.IngestError):
        pipeline.prepare_image(str(work / "shots" / "broken.png"))


def test_review_approve_edit_reject_and_approve_high(work, monkeypatch, capsys):
    client = FakeClaude(reply(VOCAB, EXPRESSION, CORRECTION, RULE, lesson="L120"))
    script, _ = run_cli(monkeypatch, client, "run", shot(work))
    answers = iter([
        "e", "wrong",                                            # the expression: it has no wrong/right to edit
        "r",
        "e", "why", "Yesterday is finished time: preterite.",   # the correction: edit, then approve
        "e", "right", "",                                        # an edit that breaks a rule is refused
        "a",
        "s",                                                     # the rule note: skip
    ])
    asked = []

    def ask(question):
        asked.append(question)
        return next(answers)

    args = script.build_parser().parse_args(["review", "--approve-high", "--lesson", "L120"])
    assert script.cmd_review(args, ask=ask) == 0
    out = capsys.readouterr().out
    assert "Approved 1 high-confidence" in out and "3 to review" in out and "not one of those fields" in out and "not saved" in out
    by_type = {o.type: o for o in pipeline.load_staged()[0].observations}
    assert by_type["vocab"].status == "approved"                 # by --approve-high
    assert by_type["correction"].status == "approved" and by_type["correction"].reviewed_at
    assert by_type["correction"].correction.why == "Yesterday is finished time: preterite."
    assert by_type["expression"].status == "rejected"            # medium confidence: needed a person
    assert by_type["rule_note"].status == "pending"
    args = script.build_parser().parse_args(["review", "--lesson", "L5"])
    assert script.cmd_review(args, ask=ask) == 0 and "Nothing left" in capsys.readouterr().out
    assert script.main(["status"]) == 0
    assert "2 approved, 1 pending, 1 rejected" in capsys.readouterr().out


def test_review_stops_cleanly_without_a_terminal(work, monkeypatch, capsys):
    script, _ = run_cli(monkeypatch, FakeClaude(reply(EXPRESSION)), "run", shot(work))

    def no_input(_):
        raise EOFError

    assert script.cmd_review(script.build_parser().parse_args(["review"]), ask=no_input) == 0
    assert "still pending" in capsys.readouterr().out


def approve_all(work):
    for obs_file in pipeline.load_staged():
        for o in obs_file.observations:
            if o.status == "pending":
                obs_file = pipeline.decide(obs_file, o.id, "approved", now=datetime(2026, 11, 12))
        pipeline.save_staged(obs_file)


def test_compile_is_deterministic_and_only_takes_approved(work, monkeypatch, capsys):
    no_english = {**EXPRESSION, "spanish": "a duras penas", "verbatim": "a duras penas", "english": None}
    client = FakeClaude(reply(VOCAB, CORRECTION, RULE, no_english, lesson="L120"), reply(EXPRESSION, lesson="L119"))
    script, _ = run_cli(monkeypatch, client, "run", shot(work, "a.png", b"a"), shot(work, "b.png", b"b"))
    assert script.main(["compile"]) == 0
    assert pipeline.compile_observations(pipeline.load_staged())["cards"] == []      # nothing approved yet
    approve_all(work)
    assert script.main(["compile"]) == 0 and "updated" in capsys.readouterr().out
    compiled = json.load(open(work / "compiled.json", encoding="utf-8"))
    assert [c["spanish"] for c in compiled["cards"]] == ["no dar pie con bola", "el destornillador de estrella"]  # L119 first
    assert compiled["corrections"][0]["right"] == "Ayer yo hablé con mi jefe."
    assert compiled["corrections"][0]["error_tags"] == ["tense_choice"] and len(compiled["rule_notes"]) == 1
    before = (work / "compiled.json").read_bytes()
    assert script.main(["compile"]) == 0 and "no change" in capsys.readouterr().out
    assert (work / "compiled.json").read_bytes() == before


def test_app_reads_the_compiled_file(work, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import spanish_drill as sd
    monkeypatch.setenv("SPANISH_PROGRESS_DB", str(work / "p.db"))
    app = os.path.join(ROOT, "app", "spanish_drill.py")
    # Nothing compiled: no deck, no drill in the menu, and the drill explains itself.
    assert flashcards.load_compiled() == {"cards": [], "corrections": [], "rule_notes": []}
    assert not any(c["deck"] == flashcards.LESSON_DECK[0] for c in flashcards.load_cards())
    at = AppTest.from_file(app, default_timeout=30)
    at.session_state["active_command"] = "!drill correcciones"
    at.run()
    assert not at.exception and any("scripts/ingest.py" in i.value for i in at.info)
    assert not any("Correcciones" in b.label for b in at.sidebar.button)

    client = FakeClaude(reply(VOCAB, EXPRESSION, CORRECTION, lesson="L120"))
    script, _ = run_cli(monkeypatch, client, "run", shot(work))
    approve_all(work)
    script.main(["compile"])
    deck = [c for c in flashcards.load_cards() if c["deck"] == flashcards.LESSON_DECK[0]]
    assert {c["spanish"] for c in deck} == {VOCAB["spanish"], EXPRESSION["spanish"]}
    noun = next(c for c in deck if c["spanish"] == VOCAB["spanish"])
    assert noun["lesson"] == "Lección 120" and noun["lesson_num"] == 120 and noun["gender"] == "m"
    assert flashcards.deck_label(flashcards.LESSON_DECK[0]) == "📸 De mis capturas"
    quiz = flashcards.quiz_item(noun, sd.split_alternates)
    assert sd.check_answer("el destornillador de estrella", quiz)[0]

    [item] = sd.get_correcciones_drill_items()
    assert item["prompt"] == "Corrige la frase: Ayer yo hablo con mi jefe." and item["exercise_type"] == "correccion_tense_choice"
    assert "preterite" in item["explanation"] and "lección 120" in item["explanation"]
    assert sd.check_answer("Ayer yo hablé con mi jefe", item)[0] and not sd.check_answer("Ayer yo hablo con mi jefe", item)[0]
    import concepts
    assert concepts.concept_for("correcciones", item["exercise_type"]) == "correcciones_de_clase"

    at = AppTest.from_file(app, default_timeout=30)
    at.run()
    next(b for b in at.sidebar.button if "Correcciones de clase" in b.label).click()
    at.run()
    assert not at.exception and at.session_state["drill_module"] == "correcciones"
    at.text_input(key="answer_0").set_value("Ayer yo hablé con mi jefe.")
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert not at.exception and at.session_state["answers"][0]["is_correct"]
    assert progress.export_backup()["attempts"][0]["module"] == "correcciones"
    # Ingesting again later treats the compiled deck as its own output, not as "already known".
    assert pipeline.known_items([]).get(next(iter(flashcards._match_keys(VOCAB["spanish"])))) is None


def test_several_words_in_one_observation_become_one_card_each(work, monkeypatch):
    joined = {**VOCAB, "verbatim": "plumas emigran? vuelan", "spanish": "las plumas raras; emigrar lejos; volar alto",
              "english": "odd feathers; to migrate far; to fly high"}
    uneven = {**VOCAB, "verbatim": "x", "spanish": "la tuerca rara; el tornillo raro", "english": "nut and bolt"}
    sentence = {**EXPRESSION, "spanish": "no dar pie con bola; ni una", "english": "to get nothing right; not one"}
    run_cli(monkeypatch, FakeClaude(reply(joined, uneven, sentence)), "run", shot(work))
    [staged] = pipeline.load_staged()
    assert [(o.spanish, o.english) for o in staged.observations] == [
        ("las plumas raras", "odd feathers"), ("emigrar lejos", "to migrate far"), ("volar alto", "to fly high"),
        ("la tuerca rara; el tornillo raro", "nut and bolt"),         # can't be paired up: left for review
        ("no dar pie con bola; ni una", "to get nothing right; not one")]   # only word lists are split
    assert [o.id[-2:] for o in staged.observations] == ["-1", "-2", "-3", "-4", "-5"]


def test_sentence_that_is_already_a_cards_example_is_a_duplicate(work, monkeypatch):
    card = next(c for c in flashcards.load_cards() if c["example"] and " / " not in c["example"])
    example = {"type": "example", "region": "board", "verbatim": card["example"].lower(),
               "spanish": card["example"], "english": "x", "confidence": "high"}
    run_cli(monkeypatch, FakeClaude(reply(example)), "run", shot(work))
    [staged] = pipeline.load_staged()
    assert [(o.status, o.duplicate_of) for o in staged.observations] == [("duplicate", card["id"])]


def test_compiled_order_follows_the_screenshot(work, monkeypatch):
    words = [{**VOCAB, "spanish": f"la palabra inventada {n}", "verbatim": str(n), "english": f"word {n}"}
             for n in range(1, 13)]
    script, _ = run_cli(monkeypatch, FakeClaude(reply(*words)), "run", shot(work))
    approve_all(work)
    compiled = pipeline.compile_observations(pipeline.load_staged())
    assert [c["english"] for c in compiled["cards"]] == [f"word {n}" for n in range(1, 13)]   # 9 before 10


def test_review_can_go_back_over_approved_items(work, monkeypatch, capsys):
    script, _ = run_cli(monkeypatch, FakeClaude(reply(VOCAB, EXPRESSION)), "run", shot(work))
    approve_all(work)
    answers = iter(["e", "english", "cross-head screwdriver", "s", "r"])
    args = script.build_parser().parse_args(["review", "--status", "approved"])
    assert script.cmd_review(args, ask=lambda _: next(answers)) == 0
    first, second = pipeline.load_staged()[0].observations
    assert (first.status, first.english) == ("approved", "cross-head screwdriver")   # an edit keeps the decision
    assert second.status == "rejected"
    args = script.build_parser().parse_args(["review", "--status", "duplicate"])
    assert script.cmd_review(args, ask=lambda _: "q") == 0 and "Nothing is duplicate" in capsys.readouterr().out


def test_a_wrongly_flagged_duplicate_can_be_approved(work, monkeypatch):
    known = next(c for c in flashcards.load_cards() if c["spanish"].startswith(("el ", "la ")))
    script, _ = run_cli(monkeypatch, FakeClaude(reply({**VOCAB, "spanish": known["spanish"]})), "run", shot(work))
    args = script.build_parser().parse_args(["review", "--status", "duplicate"])
    assert script.cmd_review(args, ask=lambda _: "a") == 0
    [o] = pipeline.load_staged()[0].observations
    assert (o.status, o.duplicate_of) == ("approved", None)


def test_marking_a_duplicate_by_hand_needs_what_it_repeats(work, monkeypatch):
    run_cli(monkeypatch, FakeClaude(reply(VOCAB)), "run", shot(work))
    [staged] = pipeline.load_staged()
    oid = staged.observations[0].id
    with pytest.raises(ValueError):
        pipeline.decide(staged, oid, "duplicate")
    marked = pipeline.decide(staged, oid, "duplicate", duplicate_of="some:card")
    assert marked.observations[0].duplicate_of == "some:card"
    assert pipeline.decide(marked, oid, "approved").observations[0].duplicate_of is None


def test_a_damaged_staged_file_is_reported_not_a_traceback(work, monkeypatch, capsys):
    path = shot(work)
    script, _ = run_cli(monkeypatch, FakeClaude(reply(VOCAB)), "run", path)
    [name] = os.listdir(work / "staged")
    (work / "staged" / name).write_text('{"schema_version": 1, "oops": true}')
    for argv in (["status"], ["review"], ["compile"]):
        assert script.main(argv) == 1
        out = capsys.readouterr().out
        assert "Stopped:" in out and name in out
    client = FakeClaude(reply(VOCAB))
    _, code = run_cli(monkeypatch, client, "run", path)
    assert code == 1 and client.calls == [] and "can't be read" in capsys.readouterr().out
