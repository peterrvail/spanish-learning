"""The concept taxonomy (data/concepts.json): what each drill, review card and
lesson observation is about, and the kinds of mistake. Kept free of Streamlit."""
import json
import os

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)

CONCEPTS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "concepts.json")
KINDS = ("grammar", "vocab", "error")

_cache = {}


def load(path=CONCEPTS_FILE):
    """id -> concept, in file order."""
    if path not in _cache:
        with open(path, encoding="utf-8") as f:
            _cache[path] = {c["id"]: c for c in json.load(f)["concepts"]}
    return _cache[path]


def ids(kind=None, path=CONCEPTS_FILE):
    return [c["id"] for c in load(path).values() if kind is None or c["kind"] == kind]


def error_tags(path=CONCEPTS_FILE):
    return ids("error", path)


def concept_for(module=None, exercise_type=None, path=CONCEPTS_FILE):
    """The concept an attempt belongs to, or None. The exercise type decides
    when it matches (longest prefix wins: it is finer than the module, and in
    the mixed drill it is the only thing that says what an item was); the
    module is the fallback."""
    concepts = load(path).values()
    if exercise_type:
        best = max(((len(p), c["id"]) for c in concepts for p in c.get("exercise_type_prefixes", [])
                    if exercise_type.startswith(p)), default=None)
        if best:
            return best[1]
    # Many simple drills use their module's name as the exercise type.
    for name in (module, exercise_type):
        found = next((c["id"] for c in concepts if name and name in c.get("modules", [])), None)
        if found:
            return found
    return None


def validate(path=CONCEPTS_FILE):
    """Problems with the taxonomy, as a list of strings (empty = OK)."""
    problems = []
    try:
        with open(path, encoding="utf-8") as f:
            nodes = json.load(f)["concepts"]
    except (OSError, ValueError, KeyError) as e:
        return [f"cannot load: {e!r}"]
    seen, modules, prefixes = set(), {}, {}
    for c in nodes:
        cid = c.get("id")
        if not cid or cid in seen:
            problems.append(f"missing or duplicate id: {cid!r}")
        seen.add(cid)
        if c.get("kind") not in KINDS:
            problems.append(f"{cid}: kind must be one of {KINDS}")
        if not str(c.get("label", "")).strip():
            problems.append(f"{cid}: empty label")
        if c.get("kind") == "error" and (c.get("modules") or c.get("exercise_type_prefixes")):
            problems.append(f"{cid}: an error tag has no modules or exercise types")
        for m in c.get("modules", []):
            if m in modules:
                problems.append(f"module {m!r} is in both {modules[m]} and {cid}")
            modules[m] = cid
        for p in c.get("exercise_type_prefixes", []):
            if p in prefixes:
                problems.append(f"prefix {p!r} is in both {prefixes[p]} and {cid}")
            prefixes[p] = cid
    by_id = {c.get("id"): c for c in nodes}
    for c in nodes:
        parent = c.get("parent")
        if parent and (parent not in by_id or by_id[parent]["kind"] != c.get("kind") or parent == c.get("id")):
            problems.append(f"{c.get('id')}: parent {parent!r} must be another concept of the same kind")
    return problems


if __name__ == "__main__":
    found = validate()
    print("concepts:", "OK" if not found else f"{len(found)} problem(s)")
    for p in found:
        print("   -", p)
