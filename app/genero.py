"""Gender and articles for nouns: el or la?

The drill (!drill genero) takes nouns from the "Otros sustantivos" flashcard
deck and the places list, and asks for them in two ways:

- typed: an English word, answered with the noun and its article ("el balde"),
  scored in two parts (article, noun) so a right word with the wrong article
  is told apart from a wrong word;
- minimal pair: "el balde" or "la balde", the same noun with each article.

Kept free of Streamlit. Rules of thumb (endings, exceptions) live in
data/grammar/genero.json."""
import json
import os
import re
import unicodedata

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)

GRAMMAR_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "grammar", "genero.json")
OTROS_DECK = "sustantivos_mundo:otros_sustantivos"
PLACE_GROUPS = ("everyday_errands", "civic_institutional", "leisure_dining", "home_and_city_structure")
ARTICLES = ("el", "la", "los", "las")
FLIP = {"el": "la", "la": "el", "los": "las", "las": "los"}
EXERCISE_TYPES = ("genero_escribir", "genero_elegir")  # typed / minimal pair
GENDER_TAG = "gender_agreement"  # the error tag (data/concepts.json) for a wrong article
_NOUN = re.compile(r"(el|la|los|las) ([^/()]+)")
_cache = {}


def load(path=GRAMMAR_FILE):
    if path not in _cache:
        with open(path, encoding="utf-8") as f:
            _cache[path] = json.load(f)["genero"]
    return _cache[path]


def concept(path=GRAMMAR_FILE):
    d = load(path)
    return {"overview": d["overview"], "uses": d["uses"]}


def is_gender_item(item):
    return str(item.get("exercise_type", "")).startswith("genero_")


def fold(text):
    """Lowercase, without accents or punctuation, single-spaced."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[¿?¡!.,;:]", " ", text).split())


def _plain(text):
    """Lowercase and single-spaced, punctuation dropped, accents kept."""
    return " ".join(re.sub(r"[¿?¡!.,;:]", " ", text.lower()).split())


def parse(spanish):
    """'el balde' -> ('el', 'balde'); None for anything that isn't one article
    plus one plain noun phrase (alternatives with '/', notes in brackets)."""
    m = _NOUN.fullmatch(spanish.strip())
    return (m.group(1), m.group(2).strip()) if m else None


def nouns(cards, places):
    """The drill's nouns: [{"spanish", "english", "article", "noun", "twin"}].
    `cards` are flashcards.load_cards(), `places` is places.json's "places".
    `twin` is True when the same noun with the other article is also a word
    (el capital / la capital): such a noun is only asked by typing, where the
    English prompt says which one is meant."""
    entries = [(c["spanish"], c["english"]) for c in cards if c["deck"] == OTROS_DECK]
    entries += [(p["spanish"], p["english"]) for group in PLACE_GROUPS for p in places.get(group, [])]
    every_word = {fold(c["spanish"]) for c in cards}
    out, seen = [], set()
    for spanish, english in entries:
        parsed = parse(spanish)
        if not parsed or fold(spanish) in seen:
            continue
        seen.add(fold(spanish))
        article, noun = parsed
        out.append({"spanish": spanish.strip(), "english": english.strip(), "article": article, "noun": noun,
                    "twin": fold(f"{FLIP[article]} {noun}") in every_word})
    return out


def head_noun(noun):
    """The word the gender comes from: the noun itself, or the first word of
    'noun de ...'. None for phrases with an adjective ('la mala suerte')."""
    words = noun.split()
    if len(words) == 1 or (len(words) > 2 and words[1] == "de"):
        return words[0]
    return None


def rule_hint(article, noun, path=GRAMMAR_FILE):
    """One line on why this noun takes this article, or None. Only singular
    nouns, and only when a rule or a known exception agrees with the answer:
    a rule that contradicts it is never shown."""
    head = head_noun(noun) if article in ("el", "la") else None
    if not head:
        return None
    d, word = load(path), fold(head)
    for group in d["exceptions"]:
        if group["article"] == article and word in {fold(w) for w in group["words"]}:
            return f"Exception ({head}): {group['tip']}"
    best = max(((len(e), r) for r in d["rules"] if r["article"] == article for e in r["endings"]
                if word.endswith(fold(e))), key=lambda x: x[0], default=None)
    return f"Rule of thumb: {best[1]['tip']}" if best else None


def explain(answer, target):
    """Score an answer to a gender item in two parts.

    article: 'ok', 'wrong' (another article, or un/una), 'missing'.
    noun:    'ok', 'accent' (right but for the accents), 'wrong', 'missing'.
    Both are 'ok' exactly when the answer is the target."""
    article, noun = parse(target)
    words = _plain(answer).split()
    if words and fold(words[0]) in ARTICLES + ("un", "una", "unos", "unas"):
        typed_article, typed_noun = fold(words[0]), " ".join(words[1:])
        article_status = "ok" if typed_article == article else "wrong"
    else:
        typed_article, typed_noun, article_status = None, " ".join(words), "missing"
    if not typed_noun:
        noun_status = "missing"
    elif typed_noun == _plain(noun):
        noun_status = "ok"
    elif fold(typed_noun) == fold(noun):
        noun_status = "accent"
    else:
        noun_status = "wrong"
    return {"article": article_status, "noun": noun_status, "typed_article": typed_article,
            "typed_noun": typed_noun, "target_article": article, "target_noun": noun}


def error_tag(parts):
    """The error tag for a wrong article on the right noun (el for la, or the
    reverse; a missing or indefinite article is a plain 'article' slip), else None."""
    if parts["noun"] not in ("ok", "accent") or parts["article"] == "ok":
        return None
    return GENDER_TAG if parts["typed_article"] in ARTICLES else "article"


def feedback_lines(parts, multiple_choice=False):
    """Markdown lines saying which part was right. The noun line only appears
    when something is wrong with it (a missing accent has its own warning)."""
    art, noun = parts["target_article"], parts["target_noun"]
    if parts["article"] == "ok":
        lines = [f"Article ✅ **{art}**"]
    elif parts["article"] == "missing":
        lines = [f"Article ❌ you left it out: **{art}** {noun}"]
    else:
        lines = [f"Article ❌ you wrote *{parts['typed_article']}*; {noun} takes **{art}**"]
    if not multiple_choice and parts["noun"] in ("wrong", "missing"):
        lines.append("Noun ❌ " + (f"you wrote *{parts['typed_noun']}*; it is **{noun}**"
                                   if parts["noun"] == "wrong" else f"you left it out: **{noun}**"))
    elif not multiple_choice and parts["noun"] == "ok" and parts["article"] != "missing":
        lines.append(f"Noun ✅ **{noun}**")
    return lines


def make_items(noun_list, rng, count=20):
    """A drill's items: half asked as a minimal pair, half typed (a noun with
    a twin is always typed). Ids restart at 0, as everywhere else."""
    chosen = rng.sample(noun_list, min(count, len(noun_list)))
    items = []
    for n in chosen:
        hint = rule_hint(n["article"], n["noun"])
        explanation = f"{n['spanish']} — {n['english']}" + (f". {hint}" if hint else "")
        base = {"id": len(items), "target_form": n["spanish"], "accepted_forms": [n["spanish"]],
                "explanation": explanation}
        if not n["twin"] and rng.random() < 0.5:
            choices = [n["spanish"], f"{FLIP[n['article']]} {n['noun']}"]
            rng.shuffle(choices)
            items.append({**base, "prompt": f"Choose the right article: {n['english']}",
                          "exercise_type": "genero_elegir", "choices": choices, "fixed_choices": True})
        else:
            items.append({**base, "prompt": f"Translate to Spanish, with its article: {n['english']}",
                          "exercise_type": "genero_escribir"})
    return items


def hint_text(item, level):
    """The typed item's letter hint. The article is masked (its first letter
    would answer the question); the hint reveals letters of the noun."""
    article, noun = parse(item["target_form"])
    out, shown = [], 0
    for ch in noun:
        if ch.isalpha():
            out.append(ch if shown < level else "_")
            shown += 1
        else:
            out.append(ch)
    return "_" * len(article) + " " + "".join(out)


def hint_limit(item):
    """How many hint levels a typed item has (one letter short of the noun)."""
    return sum(ch.isalpha() for ch in parse(item["target_form"])[1]) - 1


def validate(path=GRAMMAR_FILE):
    """Problems with the rules file, as a list of strings (empty = OK)."""
    try:
        d = load(path)
    except (OSError, ValueError, KeyError) as e:
        return [f"cannot load: {e!r}"]
    problems = []
    for field in ("source", "overview", "rules", "exceptions", "uses"):
        if not d.get(field):
            problems.append(f"missing '{field}'")
    for kind in ("rules", "exceptions"):
        for i, r in enumerate(d.get(kind, [])):
            if r.get("article") not in ("el", "la"):
                problems.append(f"{kind}[{i}]: article must be el or la")
            if not str(r.get("tip", "")).strip():
                problems.append(f"{kind}[{i}]: empty tip")
            if not r.get("endings" if kind == "rules" else "words"):
                problems.append(f"{kind}[{i}]: nothing listed")
    return problems
