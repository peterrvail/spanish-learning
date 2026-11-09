"""Flashcard decks built from the vocabulary in the user's class screenshots.

Every file in data/vocabulary/ except common_words.json was extracted from the
lesson screenshots, so each one becomes a deck. Adding a file there (e.g.
after ingesting newer lessons) adds a deck with no code change. Kept free of
Streamlit so it can be tested on its own."""
import glob
import html
import json
import os
import random
import re
import unicodedata

VOCAB_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "vocabulary")
# General word-frequency list, not from the lessons (see its _meta).
NOT_FROM_LESSONS = {"common_words.json"}

DECK_LABELS = {
    "additional_verbs": "🏃 Verbos (más)",
    "adverbs": "🧭 Adverbios",
    "body_and_health": "🩺 Cuerpo y salud",
    "class_notes_recent": "📝 Clases recientes",
    "clothing": "👕 Ropa",
    "expressions_reference": "💬 Expresiones",
    "core_verbs": "⚙️ Verbos básicos",
    "emotions_and_adjectives": "😊 Emociones y adjetivos",
    "family_and_people": "👪 Familia y personas",
    "food_and_restaurant": "🍽 Restaurante",
    "food_extended": "🥖 Comida",
    "household_and_rooms": "🏠 Casa",
    "llevar_vs_traer": "📦 Llevar y traer",
    "misc_common_nouns": "🧩 Sustantivos comunes",
    "nature_weather_animals": "🌦 Naturaleza y animales",
    "numbers_and_money": "🔢 Números y dinero",
    "places": "📍 Lugares",
    "time_and_calendar": "📅 Tiempo y calendario",
}

# Group names inside files that are split into one deck per group.
SUB_LABELS = {
    "saludos_y_cortesia": "saludos y cortesía",
    "conversacion_y_sentimientos": "conversación y sentimientos",
    "tiempo_y_frecuencia": "tiempo y frecuencia",
    "estructuras_utiles": "estructuras útiles",
    "clima_y_naturaleza": "clima y naturaleza",
    "salud_y_cuerpo": "salud y cuerpo",
    "viajes_y_direcciones": "viajes y direcciones",
    "comida_casa_y_compras": "comida, casa y compras",
    "personas_trabajo_y_sociedad": "personas, trabajo y sociedad",
}

# List keys that only group entries; the category is the key above them.
_GROUPING_KEYS = {"words", "examples", "verbs", "places", "numbers"}


def _sub_label(key):
    return SUB_LABELS.get(key, key.replace("_", " "))


def deck_label(deck):
    """'places' -> '📍 Lugares'; split decks 'file:group' -> '💬 Expresiones: saludos y cortesía'."""
    base, _, sub = deck.partition(":")
    label = DECK_LABELS.get(base, base.replace("_", " ").capitalize())
    return f"{label}: {_sub_label(sub)}" if sub else label


def _front_back(entry):
    """(spanish, english) for an entry, or None if it has no English side.
    Numbers and years have no English, so the digits stand in for it."""
    spanish = entry.get("spanish")
    if not isinstance(spanish, str) or not spanish.strip():
        return None
    for key in ("english", "number", "year"):
        if isinstance(entry.get(key), (str, int)) and str(entry[key]).strip():
            return spanish.strip(), str(entry[key]).strip()
    return None


def _walk(node, path, out):
    if isinstance(node, dict):
        if isinstance(node.get("spanish"), str):
            out.append((path, node))
        for key, value in node.items():
            if not key.startswith("_"):
                _walk(value, path + [key], out)
    elif isinstance(node, list):
        for value in node:
            _walk(value, path, out)


def _category(path):
    keys = [k for k in path if k not in _GROUPING_KEYS] or path or ["general"]
    return _sub_label(keys[-1])


def _gender(entry):
    g = str(entry.get("gender", "")).lower()
    if g.startswith("masc") and "fem" not in g:
        return "m"
    if g.startswith("fem"):
        return "f"
    # No gender field: guess from the article, but only for "article + one
    # word" - a phrase like "la cuenta, por favor" is not a feminine noun.
    words = entry.get("spanish", "").lower().split()
    if not g and len(words) == 2 and words[0] in ("el", "los", "un"):
        return "m"
    if not g and len(words) == 2 and words[0] in ("la", "las", "una"):
        return "f"
    return ""


def _key(text):
    """Comparison key: case, accents, ¿?¡!.,() and extra spaces don't make
    two entries different ('darse cuenta (de)' == 'darse cuenta de')."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[¿?¡!.,()]", " ", text).split())


def _lesson_label(first_seen):
    """'L95' -> 'Lección 95'; other labels ('Pasado simple') as they are."""
    m = re.fullmatch(r"L(\d+(?:\.\d+)?)", first_seen or "")
    if m:
        return f"Lección {m.group(1)}"
    return "" if first_seen in ("", "Untitled") else first_seen


def load_cards(vocab_dir=VOCAB_DIR):
    """Every lesson word or phrase as a card dict, deduplicated across files
    (the same word extracted from two lessons is one card)."""
    cards, seen = [], set()
    for path in sorted(glob.glob(os.path.join(vocab_dir, "*.json"))):
        name = os.path.basename(path)
        if name in NOT_FROM_LESSONS:
            continue
        file_deck = name[:-len(".json")]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # A file can ask to be one deck per top-level group (e.g. 640
        # expressions, grouped by situation) instead of one big deck.
        split = isinstance(data.get("_meta"), dict) and data["_meta"].get("split_decks")
        entries = []
        _walk(data, [], entries)
        for entry_path, entry in entries:
            deck = f"{file_deck}:{entry_path[0]}" if split and entry_path else file_deck
            sides = _front_back(entry)
            if not sides:
                continue
            spanish, english = sides
            if (_key(spanish), _key(english)) in seen:
                continue
            seen.add((_key(spanish), _key(english)))
            note = entry.get("note") or entry.get("type") or ""
            if entry.get("alternate"):
                note = (note + " · " if note else "") + f"también: {entry['alternate']}"
            cards.append({
                "id": f"{deck}:{len(cards)}",
                "deck": deck,
                "category": "año" if "year" in entry else "número" if "number" in entry else _category(entry_path),
                "spanish": spanish,
                "english": english,
                "gender": _gender(entry),
                "note": str(note),
                "example": entry.get("example", ""),
                "example_english": entry.get("example_english", ""),
                "example_from_class": entry.get("example_source") == "pizarra",
                "is_number": "number" in entry or "year" in entry,
                "lesson": _lesson_label(entry.get("first_seen", "")),
            })
    return cards


def decks(cards):
    """{deck: card count}, in file order."""
    out = {}
    for card in cards:
        out[card["deck"]] = out.get(card["deck"], 0) + 1
    return out


def quiz_item(card, split_alternates):
    """The card as a typed English→Spanish drill item, which is what goes into
    the spaced-repetition log: a missed card comes back in "!drill fallos" as
    a question to type, not just to flip. Numbers reuse the numeros drill's
    prompt so both drills share one review card per number."""
    forms = split_alternates(card["spanish"])
    if card["is_number"]:
        prompt = f"Write this number in Spanish: {card['english']}"
    else:
        prompt = f"Translate to Spanish ({card['category']}): {card['english']}"
    return {
        "prompt": prompt,
        "target_form": forms[0],
        "accepted_forms": forms,
        "exercise_type": f"tarjetas_{card['deck']}",
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
