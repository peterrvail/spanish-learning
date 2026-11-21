"""The gender drill (!drill genero): app/genero.py and its place in the app."""
import json
import os
import random
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import concepts  # noqa: E402
import flashcards  # noqa: E402
import genero  # noqa: E402
import grading  # noqa: E402
import progress  # noqa: E402
import spanish_drill as sd  # noqa: E402

PLACES = json.load(open(os.path.join(ROOT, "data", "vocabulary", "places.json"), encoding="utf-8"))["places"]


@pytest.fixture(scope="module")
def cards():
    return flashcards.load_cards()


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("SPANISH_PROGRESS_DB", str(tmp_path / "p.db"))
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)


def _app():
    from streamlit.testing.v1 import AppTest
    return AppTest.from_file(os.path.join(ROOT, "app", "spanish_drill.py"), default_timeout=30)


# --- the pool ---------------------------------------------------------------------

def test_pool_is_otros_sustantivos_plus_places(cards):
    pool = genero.nouns(cards, PLACES)
    otros = [c for c in cards if c["deck"] == genero.OTROS_DECK]
    assert 150 <= len(pool) <= len(otros) + 38
    assert len({genero.fold(n["spanish"]) for n in pool}) == len(pool)              # no repeats
    assert all(genero.parse(n["spanish"]) == (n["article"], n["noun"]) for n in pool)
    assert any(n["spanish"] == "el agujero" for n in pool) and any(n["spanish"] == "la farmacia" for n in pool)
    assert not any("/" in n["spanish"] or "(" in n["spanish"] for n in pool)        # alternatives are left out
    assert not any(n["spanish"].startswith(("el apartamento/piso", "el centro (de")) for n in pool)


def test_a_noun_whose_other_gender_is_also_a_word_is_never_a_minimal_pair():
    cards = [{"deck": genero.OTROS_DECK, "spanish": "el capital", "english": "capital (money)"},
             {"deck": genero.OTROS_DECK, "spanish": "la capital", "english": "capital (city)"},
             {"deck": genero.OTROS_DECK, "spanish": "la mesa", "english": "table"}]
    pool = genero.nouns(cards, {})
    assert {n["spanish"]: n["twin"] for n in pool} == {"el capital": True, "la capital": True, "la mesa": False}
    for seed in range(20):
        for item in genero.make_items(pool, random.Random(seed), 3):
            if "capital" in item["target_form"]:
                assert item["exercise_type"] == "genero_escribir"


# --- scoring ----------------------------------------------------------------------

@pytest.mark.parametrize("answer,article,noun,tag", [
    ("la calle", "ok", "ok", None),
    ("La  Calle.", "ok", "ok", None),
    ("el calle", "wrong", "ok", "gender_agreement"),
    ("los calle", "wrong", "ok", "gender_agreement"),
    ("una calle", "wrong", "ok", "article"),
    ("calle", "missing", "ok", "article"),
    ("la cale", "ok", "wrong", None),
    ("el cale", "wrong", "wrong", None),
    ("la", "ok", "missing", None),
    ("la  calle grande", "ok", "wrong", None),
])
def test_split_scoring(answer, article, noun, tag):
    parts = genero.explain(answer, "la calle")
    assert (parts["article"], parts["noun"], genero.error_tag(parts)) == (article, noun, tag)


def test_accents_are_their_own_status():
    assert genero.explain("el dia", "el día")["noun"] == "accent"
    assert genero.explain("el día", "el día")["noun"] == "ok"
    assert genero.error_tag(genero.explain("la dia", "el día")) == "gender_agreement"   # wrong article, accent too
    assert genero.feedback_lines(genero.explain("el dia", "el día")) == ["Article ✅ **el**"]  # the accent warning says the rest


def test_feedback_lines_name_the_part_that_is_wrong():
    assert genero.feedback_lines(genero.explain("el calle", "la calle")) == [
        "Article ❌ you wrote *el*; calle takes **la**", "Noun ✅ **calle**"]
    assert genero.feedback_lines(genero.explain("el calle", "la calle"), multiple_choice=True) == [
        "Article ❌ you wrote *el*; calle takes **la**"]
    assert genero.feedback_lines(genero.explain("la cale", "la calle")) == [
        "Article ✅ **la**", "Noun ❌ you wrote *cale*; it is **calle**"]
    assert genero.feedback_lines(genero.explain("calle", "la calle")) == ["Article ❌ you left it out: **la** calle"]


# --- the items --------------------------------------------------------------------

def test_items_are_typed_or_minimal_pairs(cards):
    pool = genero.nouns(cards, PLACES)
    kinds = set()
    for seed in range(10):
        items = genero.make_items(pool, random.Random(seed), 20)
        assert len(items) == 20 and [i["id"] for i in items] == list(range(20))
        assert len({i["target_form"] for i in items}) == 20
        for item in items:
            kinds.add(item["exercise_type"])
            article, noun = genero.parse(item["target_form"])
            assert item["accepted_forms"] == [item["target_form"]]               # the article is not optional
            if item["exercise_type"] == "genero_elegir":
                assert sorted(item["choices"]) == sorted([f"el {noun}", f"la {noun}"]) or \
                    sorted(item["choices"]) == sorted([f"los {noun}", f"las {noun}"])
                assert item["target_form"] in item["choices"] and item["fixed_choices"]
            else:
                assert "choices" not in item and "with its article" in item["prompt"]
    assert kinds == {"genero_elegir", "genero_escribir"}


def test_hints_never_give_away_the_article():
    item = {"exercise_type": "genero_escribir", "target_form": "la gotera"}
    assert genero.hint_text(item, 0) == "__ ______" and genero.hint_text(item, 2) == "__ go____"
    assert genero.hint_limit(item) == 5
    assert sd._hint_for(item, 1) == "__ g_____" and sd._hint_limit(item) == 5
    other = {"exercise_type": "vocabulario_mio", "target_form": "la gotera"}
    assert sd._hint_for(other, 1) == "l_ ______"                                  # other drills are unchanged


def test_claude_is_not_asked_to_second_guess_an_article():
    long_noun = {"prompt": "x", "target_form": "la estación de tren", "exercise_type": "genero_escribir"}
    assert not grading.eligible(long_noun)
    assert grading.eligible({**long_noun, "exercise_type": "vocabulario_mio"})


def test_generic_multiple_choice_leaves_gender_items_alone(cards):
    items = genero.make_items(genero.nouns(cards, PLACES), random.Random(1), 20)
    typed = [i for i in items if i["exercise_type"] == "genero_escribir"]
    for _ in range(20):
        sd._add_recognition_variants(typed, fraction=1.0)
    assert not any("choices" in i for i in typed)


# --- the rules of thumb are true of your vocabulary --------------------------------

def _reference_nouns(cards):
    out = []
    for c in cards:
        parsed = genero.parse(c["spanish"])
        if parsed and c["deck"].startswith("sustantivos") and genero.head_noun(parsed[1]) == parsed[1] \
                and parsed[0] in ("el", "la"):
            out.append(parsed)
    return out


def test_rules_file_is_valid_and_its_rules_hold_for_the_vocabulary(cards):
    assert genero.validate() == []
    nouns = _reference_nouns(cards)
    assert len(nouns) > 1000
    for rule in genero.load()["rules"]:
        matching = [(a, n) for a, n in nouns if any(genero.fold(n).endswith(genero.fold(e)) for e in rule["endings"])]
        agree = sum(1 for a, _ in matching if a == rule["article"])
        assert matching and agree / len(matching) >= 0.9, (rule["endings"], agree, len(matching))


def test_listed_exceptions_really_are_what_they_say(cards):
    seen = {n: a for a, n in _reference_nouns(cards)}
    for group in genero.load()["exceptions"]:
        for word in group["words"]:
            if word in seen:
                assert seen[word] == group["article"], word


def test_hints_cover_most_of_the_vocabulary_and_say_the_right_thing(cards):
    shown = 0
    for article, noun in _reference_nouns(cards):
        hint = genero.rule_hint(article, noun)
        if hint:
            shown += 1
    assert shown > 1000
    assert "stressed a-" in genero.rule_hint("el", "agua") and "Exception" in genero.rule_hint("el", "problema")
    assert genero.rule_hint("la", "información").startswith("Rule of thumb: -ción")
    assert genero.rule_hint("el", "viaje").startswith("Rule of thumb: -aje")
    assert genero.rule_hint("la", "estación de tren").startswith("Rule of thumb: -ción")
    assert genero.rule_hint("la", "mala suerte") is None and genero.rule_hint("las", "elecciones") is None
    assert genero.rule_hint("el", "cuaderno").startswith("Rule of thumb: -o")
    assert genero.rule_hint("la", "mano") .startswith("Exception")
    assert genero.rule_hint("la", "calle") is None                                   # no rule for -e: quiet


# --- in the app -------------------------------------------------------------------

def _start(at):
    at.session_state["active_command"] = "!drill genero"
    at.run()
    return at.session_state["drill_items"]


def _first(items, kind):
    return next(i for i in items if i["exercise_type"] == kind)


def test_in_the_menu_and_mapped_to_a_concept():
    assert ("🚹🚺 Género: el o la", "!drill genero") in sd.DRILL_CATEGORIES["Vocabulario"]
    assert "genero" in sd.KNOWN_MODULES and "genero" in sd._MIXTO_MODULES
    assert sd.get_module_concept("genero")["uses"]
    assert concepts.concept_for("genero", "genero_elegir") == "genero_articulo"
    assert sd.parse_command("!drill género") == ("drill", "genero")


def test_typed_wrong_article_is_told_apart_from_a_wrong_noun(db):
    at = _app()
    at.run()
    items = _start(at)
    while at.session_state["current_item_index"] < len(items) and items[at.session_state["current_item_index"]]["exercise_type"] != "genero_escribir":
        at.session_state["current_item_index"] += 1
        at.run()
    item = items[at.session_state["current_item_index"]]
    article, noun = genero.parse(item["target_form"])
    at.text_input(key=f"answer_{item['id']}").set_value(f"{genero.FLIP[article]} {noun}")
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Article ❌" in text and f"takes **{article}**" in text and "Noun ✅" in text
    assert at.session_state["answers"][-1]["is_correct"] is False
    [attempt] = progress.export_backup()["attempts"]
    assert attempt["error_tag"] == "gender_agreement" and attempt["exercise_type"] == "genero_escribir"
    assert attempt["typed_answer"] == f"{genero.FLIP[article]} {noun}" and attempt["module"] == "genero"
    assert progress.due_count() == 1                                              # in the review queue, with its own tag


def test_minimal_pair_in_the_app_and_the_review_queue(db):
    at = _app()
    at.run()
    items = _start(at)
    item = _first(items, "genero_elegir") if any(i["exercise_type"] == "genero_elegir" for i in items) else None
    if item is None:
        pytest.skip("this draw had no minimal pair")
    at.session_state["current_item_index"] = item["id"]
    at.run()
    assert at.radio(key=f"choice_{item['id']}").options == item["choices"]
    wrong = next(c for c in item["choices"] if c != item["target_form"])
    at.radio(key=f"choice_{item['id']}").set_value(wrong)
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert not at.exception and any("Article ❌" in m.value for m in at.markdown)
    assert not any("Noun" in m.value for m in at.markdown)                       # a minimal pair is about the article only
    [attempt] = progress.export_backup()["attempts"]
    assert attempt["error_tag"] == "gender_agreement" and attempt["exercise_type"] == "genero_elegir"
    # "!drill fallos" asks it again as it was: same two options, same split feedback.
    at2 = _app()
    at2.session_state["active_command"] = "!drill fallos"
    at2.run()
    [again] = at2.session_state["drill_items"]
    assert again["choices"] == item["choices"] and again["exercise_type"] == "genero_elegir"
    at2.radio(key="choice_0").set_value(wrong)
    next(b for b in at2.button if "Submit" in b.label).click()
    at2.run()
    assert not at2.exception and any("Article ❌" in m.value for m in at2.markdown)


def test_typed_hint_masks_the_article_and_correct_answers_pass(db):
    at = _app()
    at.run()
    items = _start(at)
    item = _first(items, "genero_escribir") if any(i["exercise_type"] == "genero_escribir" for i in items) else None
    if item is None:
        pytest.skip("this draw had no typed item")
    at.session_state["current_item_index"] = item["id"]
    at.run()
    next(b for b in at.button if "Pista" in b.label).click()
    at.run()
    article, _ = genero.parse(item["target_form"])
    # (Streamlit 1.46 keeps the icon in the text, newer versions take it out.)
    assert any(i.value.removeprefix("💡 ").startswith("Pista: `" + "_" * len(article) + " ") for i in at.info)
    at.text_input(key=f"answer_{item['id']}").set_value(item["target_form"])
    next(b for b in at.button if "Submit" in b.label).click()
    at.run()
    assert not at.exception and at.session_state["answers"][-1]["is_correct"] is True


def test_repaso_and_mixto_work(db):
    at = _app()
    at.session_state["active_command"] = "!repasar genero"
    at.run()
    assert not at.exception and any("Feminine nouns that take el" in m.value for m in at.markdown)
    for module in ("genero", "mixto"):
        at = _app()
        at.session_state["active_command"] = f"!drill {module}"
        at.run()
        assert not at.exception and at.session_state["drill_items"]
