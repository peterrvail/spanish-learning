"""Flashcard decks built from the user's lesson vocabulary.

The source is data/reference/vocabulary_reference.json, the "Spanish
Vocabulary — Complete Lesson Reference" (3,563 words and phrases from every
lesson screenshot and PDF, Lessons 1–119). Each group in it is a deck, except
verbs and adjectives, which are one deck each. Example sentences already in
the app (the whiteboard examples in class_notes_recent.json, core_verbs.json)
are attached to the matching cards, and the few class-notes entries the
reference doesn't have form an extra deck. Kept free of Streamlit so it can be
tested on its own."""
import html
import json
import os
import random
import re
import unicodedata

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
REFERENCE_FILE = os.path.join(DATA_DIR, "reference", "vocabulary_reference.json")
VOCAB_DIR = os.path.join(DATA_DIR, "vocabulary")
# Older extracted files whose example sentences are worth keeping on the cards.
EXAMPLE_SOURCES = ["class_notes_recent.json", "core_verbs.json", "food_and_restaurant.json",
                   "numbers_and_money.json"]
EXTRA_DECK = ("notas_de_clase:extra", "📝 Notas de clase (extra)")
# Words, expressions and example sentences read from lesson screenshots and
# approved (python scripts/ingest.py: run, review, compile). The file is
# generated; it also holds tutor corrections, drilled as "!drill correcciones".
LESSON_DECK = ("capturas:clase", "📸 De mis capturas")
COMPILED_FILE = os.path.join(DATA_DIR, "compiled", "lesson_observations.json")


def load_compiled(path=None):
    """The compiled lesson observations, or empty lists when nothing has been compiled yet."""
    try:
        with open(path or COMPILED_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {key: data.get(key, []) for key in ("cards", "corrections", "rule_notes")}
_NOUN_PARTS = {"sustantivos_vida_diaria", "sustantivos_mundo"}
_QUOTED = re.compile(r'^"[^"]+"(\s*;\s*"[^"]+")*$')

_labels = {}  # deck id -> label, filled by load_cards()


def deck_label(deck):
    return _labels.get(deck, deck)


def _key(text):
    """Comparison key: case, accents, ¿?¡!.,() and extra spaces don't make
    two entries different ('darse cuenta (de)' == 'darse cuenta de')."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[¿?¡!.,()]", " ", text).split())


_SINGULAR_ARTICLE = {"los": "el", "las": "la"}


def _match_keys(spanish):
    """Ways an older file may write a reference entry: 'inclinado/a' for
    'inclinado', 'las pasas' for 'la pasa', 'el maestro (de obra)', or one
    half of 'la loma / la colina'."""
    out = set()
    base = re.sub(r"\s*\([^)]*\)", "", spanish)
    for chunk in [spanish, base] + base.split(" / "):
        words = _key(re.sub(r"/a\b", "", chunk)).split()
        if not words:
            continue
        out.add(" ".join(words))
        if len(words) >= 2 and words[0] in _SINGULAR_ARTICLE:
            singular = _SINGULAR_ARTICLE[words[0]]
            out.add(" ".join([singular, re.sub(r"s$", "", words[1])] + words[2:]))
            if words[1].endswith("es") and len(words[1]) > 4:
                out.add(" ".join([singular, words[1][:-2]] + words[2:]))
    return out


def _gender(spanish):
    """Nouns carry their article; 'el tío / la tía' (both forms) gets none."""
    words = spanish.lower().split()
    if " / " in spanish or not words:
        return ""
    return {"el": "m", "los": "m", "un": "m", "la": "f", "las": "f", "una": "f"}.get(words[0], "")


def lesson_number(first_seen):
    """'L95' -> 95.0, 'L112.5' -> 112.5; named sources ('Pasado simple') -> None."""
    m = re.fullmatch(r"L(\d+(?:\.\d+)?)", first_seen or "")
    return float(m.group(1)) if m else None


def _lesson_label(first_seen):
    num = lesson_number(first_seen)
    if num is not None:
        return f"Lección {num:g}"
    return "" if first_seen in ("", "Untitled") else first_seen


def _older_examples():
    """{match key: (example, english, from the whiteboard?)} from older files."""
    found = {}
    for name in EXAMPLE_SOURCES:
        path = os.path.join(VOCAB_DIR, name)
        if not os.path.exists(path):
            continue
        stack = [json.load(open(path, encoding="utf-8"))]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if isinstance(node.get("spanish"), str) and node.get("example"):
                    value = (node["example"], node.get("example_english", ""), node.get("example_source") == "pizarra")
                    for key in _match_keys(node["spanish"]):
                        found.setdefault(key, value)
                stack.extend(v for k, v in node.items() if not k.startswith("_"))
            elif isinstance(node, list):
                stack.extend(node)
    return found


def _card(deck, category, entry, gender, examples):
    note = entry.get("note", "")
    example, example_english, from_class = "", "", False
    if note and _QUOTED.match(note):  # a note that is only a quoted class sentence
        example, note = " / ".join(q.strip().strip('"') for q in note.split(";")), ""
    older = next((examples[k] for k in _match_keys(entry["spanish"]) if k in examples), None)
    if older and (not example or older[2]):  # prefer a translated whiteboard example
        example, example_english, from_class = older
    return {
        # Exact text, accents included: el / él and si / sí are different words.
        "id": f"{deck}:{entry['spanish'].strip()}",
        "deck": deck,
        "category": category,
        "spanish": entry["spanish"],
        "english": entry["english"],
        "gender": gender,
        "note": note,
        "example": example,
        "example_english": example_english,
        "example_from_class": from_class,
        "lesson": _lesson_label(entry.get("first_seen", "")),
        "lesson_num": lesson_number(entry.get("first_seen", "")),
    }


def load_cards(reference_file=REFERENCE_FILE):
    """Every reference entry as a card, plus the class-notes extras."""
    with open(reference_file, encoding="utf-8") as f:
        ref = json.load(f)
    examples = _older_examples()
    cards, seen = [], set()
    for part in ref["parts"]:
        for group in part["groups"]:
            deck = f"{part['id']}:{group['id']}"
            if part["id"] == "expresiones":
                label = f"{part['label']}: {group['label']}"
            else:
                label = group["label"]
            _labels[deck] = label
            category = re.sub(r"^\W+\s*", "", label)  # label without its emoji
            for entry in group["entries"]:
                gender = _gender(entry["spanish"]) if part["id"] in _NOUN_PARTS else ""
                cards.append(_card(deck, category, entry, gender, examples))
                seen |= _match_keys(entry["spanish"])

    # Class-notes words the reference doesn't have (mostly commands like
    # "Vaya recto", which it leaves out as conjugated forms).
    extra_path = os.path.join(VOCAB_DIR, "class_notes_recent.json")
    if os.path.exists(extra_path):
        deck, label = EXTRA_DECK
        _labels[deck] = label
        notes = json.load(open(extra_path, encoding="utf-8"))
        for key, entries in notes.items():
            if key.startswith("_"):
                continue
            for entry in entries:
                if _match_keys(entry["spanish"]) & seen:
                    continue
                card = _card(deck, "notas de clase", {**entry, "first_seen": ""},
                             "m" if entry.get("gender") == "masculine" else "f" if entry.get("gender") == "feminine" else "",
                             examples)
                card["example"], card["example_english"] = entry.get("example", ""), entry.get("example_english", "")
                card["example_from_class"] = entry.get("example_source") == "pizarra"
                card["lesson"] = "Lecciones 113–119"
                cards.append(card)
                seen |= _match_keys(entry["spanish"])

    # From lesson screenshots. Anything the decks above already have is left
    # out (the ingestion script marks those as duplicates, this is the backstop).
    deck, label = LESSON_DECK
    _labels[deck] = label
    for entry in load_compiled()["cards"]:
        if _match_keys(entry["spanish"]) & seen:
            continue
        seen |= _match_keys(entry["spanish"])
        is_noun = entry.get("type") == "vocab"
        card = _card(deck, "de mis capturas", {**entry, "first_seen": entry.get("lesson") or ""},
                     _gender(entry["spanish"]) if is_noun else "", examples)
        card["id"] = f"{deck}:{entry['id']}"  # the observation id: stable if the text is edited later
        cards.append(card)
    return cards


def lesson_range(cards):
    """(first, last) lesson number among the cards."""
    nums = [c["lesson_num"] for c in cards if c["lesson_num"] is not None]
    return (int(min(nums)), int(max(nums))) if nums else (0, 0)


def decks(cards):
    """{deck: card count}, in file order."""
    out = {}
    for card in cards:
        out[card["deck"]] = out.get(card["deck"], 0) + 1
    return out


def same_meaning(cards, split_alternates):
    """(category, english) -> every Spanish form given for it. Some English
    prompts have more than one card ("me too": yo también / a mí también),
    and either answer is right."""
    index = {}
    for c in cards:
        forms = index.setdefault((c["category"], c["english"]), [])
        forms.extend(f for f in split_alternates(c["spanish"]) if f not in forms)
    return index


def quiz_item(card, split_alternates, same=None):
    """The card as a typed English→Spanish drill item, which is what goes into
    the spaced-repetition log: a missed card comes back in "!drill fallos" as
    a question to type, not just to flip. `same` is same_meaning()'s index,
    so the other cards' answers to the same prompt count too."""
    forms = split_alternates(card["spanish"])
    forms += [f for f in (same or {}).get((card["category"], card["english"]), []) if f not in forms]
    return {
        "prompt": f"Translate to Spanish ({card['category']}): {card['english']}",
        "target_form": forms[0],
        "accepted_forms": forms,
        "exercise_type": f"tarjetas_{card['deck'].replace(':', '_')}",
        "explanation": f"{card['spanish']} — {card['english']}",
        "module": "tarjetas",
    }


def build_deck(cards, chosen_decks, size, due_keys=frozenset(), key_of=None, rng=random):
    """Pick a session's cards from the chosen decks: cards due for review come
    first, then the rest at random, `size` in all (0 = all of them)."""
    pool = [c for c in cards if c["deck"] in chosen_decks]
    rng.shuffle(pool)
    if key_of:
        pool.sort(key=lambda c: key_of(c) not in due_keys)  # stable: due cards first
    return pool if not size else pool[:size]


def requeue(queue, position, gap=3):
    """'Otra vez': put the card at `position` back a few cards later, so it
    returns in this same session (or at the end if the deck is nearly done)."""
    card = queue.pop(position)
    queue.insert(min(position + gap, len(queue)), card)
    return queue


def card_html(card, direction, flip_id, variant=0):
    """A flashcard that flips when tapped. The flip is CSS only (a hidden
    checkbox whose label is the card), so it is instant on a phone and costs
    no round trip; grading happens with the buttons below the card.

    `variant` should alternate between consecutive cards (0, 1, 0, ...): it
    adds one wrapper element on odd cards. Streamlit patches the previous
    card's DOM in place where it can, and a reused checkbox keeps its ticked
    state, so the next card would open already flipped. A different nesting
    depth forces a brand-new checkbox."""
    if direction == "es_en":
        front, back, front_lang, back_lang = card["spanish"], card["english"], "ESPAÑOL", "ENGLISH"
    else:
        front, back, front_lang, back_lang = card["english"], card["spanish"], "ENGLISH", "ESPAÑOL"
    e = html.escape
    gender = {"m": ("masculino", "fc-m"), "f": ("femenino", "fc-f")}.get(card["gender"], ("", ""))
    chip = f'<span class="fc-chip {gender[1]}">{gender[0]}</span>' if gender[0] else ""
    details = ""
    if card["note"]:
        details += f'<div class="fc-note">{e(card["note"])}</div>'
    if card["example"]:
        details += f'<div class="fc-example">{e(card["example"])}'
        if card["example_english"]:
            details += f'<br><span>{e(card["example_english"])}</span>'
        if card.get("example_from_class"):
            details += '<br><span class="fc-from-class">📝 de tu clase</span>'
        details += "</div>"
    if card.get("lesson"):
        details += f'<div class="fc-lesson">📚 {e(card["lesson"])}</div>'
    category = e(card["category"])
    markup = f"""
<div class="fc-scene">
  <input type="checkbox" id="{flip_id}" class="fc-toggle">
  <label for="{flip_id}" class="fc-card {gender[1]}">
    <div class="fc-face fc-front">
      <div class="fc-lang">{front_lang} · {category}</div>
      <div class="fc-word">{e(front)}</div>
      <div class="fc-hint">toca para voltear ↻</div>
    </div>
    <div class="fc-face fc-back">
      <div class="fc-lang">{back_lang}</div>
      <div class="fc-word">{e(back)}</div>
      {chip}{details}
    </div>
  </label>
</div>"""
    if variant % 2:
        markup = f'<div class="fc-alt">{markup}</div>'
    # One line: Streamlit renders this through Markdown, where an indented
    # line after a blank one (an empty chip/details slot) becomes a code block.
    return " ".join(line.strip() for line in markup.splitlines() if line.strip())


CARD_CSS = """
<style>
.fc-scene { perspective: 1200px; margin: 0.5rem 0 1rem; }
.fc-toggle { position: absolute; opacity: 0; pointer-events: none; }
.fc-card {
  display: block; position: relative; width: 100%; height: 280px; cursor: pointer;
  transform-style: preserve-3d; transition: transform 0.45s ease; -webkit-tap-highlight-color: transparent;
}
.fc-toggle:checked + .fc-card { transform: rotateY(180deg); }
.fc-face {
  position: absolute; inset: 0; border-radius: 18px; padding: 1.2rem 1.4rem;
  display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center;
  backface-visibility: hidden; -webkit-backface-visibility: hidden;
  background: #ffffff; color: #1f2937; border: 1px solid #e5e7eb;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.12);
}
.fc-back { transform: rotateY(180deg); background: #f8fafc; }
.fc-card.fc-m .fc-face { border-top: 6px solid #2563eb; }
.fc-card.fc-f .fc-face { border-top: 6px solid #db2777; }
.fc-lang { position: absolute; top: 0.9rem; font-size: 0.72rem; letter-spacing: 0.08em; color: #6b7280; }
.fc-word { font-size: clamp(1.6rem, 6vw, 2.4rem); font-weight: 650; line-height: 1.2; overflow-wrap: anywhere; }
.fc-hint { position: absolute; bottom: 0.9rem; font-size: 0.8rem; color: #9ca3af; }
.fc-chip { margin-top: 0.6rem; font-size: 0.75rem; padding: 0.15rem 0.6rem; border-radius: 999px; }
.fc-chip.fc-m { background: #dbeafe; color: #1e40af; }
.fc-chip.fc-f { background: #fce7f3; color: #9d174d; }
.fc-note { margin-top: 0.6rem; font-size: 0.85rem; color: #4b5563; }
.fc-example { margin-top: 0.6rem; font-size: 0.9rem; font-style: italic; color: #374151; }
.fc-example span { font-style: normal; color: #6b7280; font-size: 0.8rem; }
.fc-example .fc-from-class { color: #0f766e; font-size: 0.72rem; }
.fc-lesson { position: absolute; bottom: 0.8rem; font-size: 0.72rem; color: #6b7280; }
</style>
"""
