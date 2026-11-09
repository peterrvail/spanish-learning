"""Grammar-pattern drills that share one data shape (feature 4 of
EXTERNAL_RESOURCES.md: se, relative pronouns, conditional perfect, si
clauses, cognates). Each module is a JSON file in data/grammar/ with:

{
  "<key>": {
    "source": "claude-draft: ...",
    "overview": "Spanish explanation of the pattern",
    "uses": [{"name": "...", "description": "... with an example"}],
    "instructions": {"fill_in": "Completa con ...", "classify": "¿Qué tipo de ...?"},
    "fill_in":   [{"sentence": "A mí ___ (olvidar) las llaves.", "answer": "se me olvidaron",
                   "english": "I forgot the keys.", "note": "optional"}],
    "translate": [{"english": "...", "spanish": "...", "also_accepted": ["..."]}],
    "classify":  [{"sentence": "...", "answer": "one of labels"}],   "labels": ["...", "..."],
    "correct":   [{"wrong": "...", "right": "...", "why": "...", "also_accepted": []}]
  }
}

Only the item lists named in a module's MIX need to exist. Kept free of
Streamlit; validate() is what the data drafts are checked against."""
import json
import os
import random
import re

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)

GRAMMAR_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "grammar")

# module -> data file, top-level key, menu label, items per run by kind
MODULES = {
    "se": {"file": "se_constructions.json", "key": "se_constructions",
           "label": "🔄 Se: accidental, impersonal y pasivo",
           "mix": {"fill_in": 9, "translate": 3, "classify": 3}},
    "relativos": {"file": "relative_pronouns.json", "key": "relative_pronouns",
                  "label": "🔗 Relativos (que, quien, lo que, cuyo)",
                  "mix": {"fill_in": 10, "translate": 3, "correct": 2}},
    "cond_perfecto": {"file": "conditional_perfect.json", "key": "conditional_perfect",
                      "label": "🕰️ Habría / debería haber",
                      "mix": {"fill_in": 9, "translate": 4, "correct": 2}},
    "si_hipotetico": {"file": "si_clauses.json", "key": "si_clauses",
                      "label": "💭 Si + hipótesis",
                      "mix": {"fill_in": 9, "translate": 4, "classify": 2}},
    "cognados": {"file": "cognates.json", "key": "cognates",
                 "label": "🔤 Cognados (-ción, -mente, -dad…)",
                 "mix": {"translate": 12, "classify": 3}},
}
BLANK = re.compile(r"___(\s*\([^)]*\))?")


def load(module, grammar_dir=GRAMMAR_DIR):
    spec = MODULES[module]
    with open(os.path.join(grammar_dir, spec["file"]), encoding="utf-8") as f:
        return json.load(f)[spec["key"]]


def fill_blank(sentence, answer):
    return BLANK.sub(answer, sentence, count=1)


def items(module, rng=random, grammar_dir=GRAMMAR_DIR):
    """One run's items, in the shape the drill runner expects."""
    d = load(module, grammar_dir)
    instructions = d.get("instructions", {})
    out = []

    def add(prompt, target, kind, explanation, also=(), choices=None):
        item = {"id": len(out), "prompt": prompt, "target_form": target, "exercise_type": f"{module}_{kind}",
                "explanation": explanation, "also_accepted": list(also)}
        if choices:
            item["choices"] = list(choices)
            item["fixed_choices"] = True  # its own options: kept when the item goes to review
        out.append(item)

    for kind, n in MODULES[module]["mix"].items():
        pool = d.get(kind, [])
        for x in rng.sample(pool, min(n, len(pool))):
            if kind == "fill_in":
                note = f" ({x['note']})" if x.get("note") else ""
                add(f"{instructions.get('fill_in', 'Completa')}: {x['sentence']}", x["answer"], kind,
                    f"{fill_blank(x['sentence'], x['answer'])} — {x['english']}{note}", x.get("also_accepted", []))
            elif kind == "translate":
                add(f"Translate to Spanish: {x['english']}", x["spanish"], kind,
                    f"{x['spanish']} — {x['english']}" + (f" ({x['note']})" if x.get("note") else ""),
                    x.get("also_accepted", []))
            elif kind == "classify":
                labels = list(d["labels"])
                rng.shuffle(labels)
                add(f"{instructions.get('classify', '¿Qué tipo?')} «{x['sentence']}»", x["answer"], kind,
                    f"«{x['sentence']}» → {x['answer']}" + (f". {x['why']}" if x.get("why") else ""), choices=labels)
            elif kind == "correct":
                add(f"Corrige la frase: {x['wrong']}", x["right"], kind,
                    f"✗ {x['wrong']} → ✓ {x['right']} — {x['why']}", x.get("also_accepted", []))
    rng.shuffle(out)
    for i, item in enumerate(out):
        item["id"] = i
    return out


def concept(module, grammar_dir=GRAMMAR_DIR):
    d = load(module, grammar_dir)
    return {"overview": d["overview"], "uses": d.get("uses", [])}


def validate(module, grammar_dir=GRAMMAR_DIR):
    """Problems with a module's data, as a list of strings (empty = OK).
    Each item list must hold at least twice what one run uses."""
    problems = []
    try:
        d = load(module, grammar_dir)
    except (OSError, ValueError, KeyError) as e:
        return [f"cannot load: {e!r}"]
    for field in ("source", "overview", "uses"):
        if not d.get(field):
            problems.append(f"missing '{field}'")
    if not str(d.get("source", "")).startswith("claude-draft"):
        problems.append("source must start with 'claude-draft'")
    for kind, n in MODULES[module]["mix"].items():
        pool = d.get(kind, [])
        if len(pool) < 2 * n:
            problems.append(f"'{kind}' has {len(pool)} items; needs at least {2 * n}")
        seen = set()
        for i, x in enumerate(pool):
            where = f"{kind}[{i}]"
            text = x.get("sentence") or x.get("english") or x.get("wrong")
            if text in seen:
                problems.append(f"{where}: duplicate {text!r}")
            seen.add(text)
            if kind == "fill_in":
                if len(BLANK.findall(x.get("sentence", ""))) != 1 or x["sentence"].count("___") != 1:
                    problems.append(f"{where}: sentence needs exactly one ___")
                for k in ("answer", "english"):
                    if not str(x.get(k, "")).strip():
                        problems.append(f"{where}: empty '{k}'")
            elif kind == "translate":
                for k in ("english", "spanish"):
                    if not str(x.get(k, "")).strip():
                        problems.append(f"{where}: empty '{k}'")
            elif kind == "classify":
                if x.get("answer") not in d.get("labels", []):
                    problems.append(f"{where}: answer {x.get('answer')!r} not in labels")
            elif kind == "correct":
                for k in ("wrong", "right", "why"):
                    if not str(x.get(k, "")).strip():
                        problems.append(f"{where}: empty '{k}'")
                if x.get("wrong") == x.get("right"):
                    problems.append(f"{where}: wrong == right")
            if not isinstance(x.get("also_accepted", []), list):
                problems.append(f"{where}: also_accepted must be a list")
    if "classify" in MODULES[module]["mix"] and not 2 <= len(d.get("labels", [])) <= 6:
        problems.append("'labels' must list 2-6 categories")
    return problems


if __name__ == "__main__":
    import sys
    for name in sys.argv[1:] or MODULES:
        found = validate(name)
        print(f"{name}: {'OK' if not found else str(len(found)) + ' problem(s)'}")
        for p in found:
            print("   -", p)
