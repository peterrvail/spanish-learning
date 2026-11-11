"""Language Transfer – Complete Spanish (free 90-track audio course), mapped onto
this app's lessons and drills. Data: data/external/language_transfer.json.
Kept free of Streamlit so it can be tested on its own."""
import json
import os

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)

LT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "external", "language_transfer.json")

_cache = {}


def load_lt(path=LT_FILE):
    if path not in _cache:
        with open(path, encoding="utf-8") as f:
            _cache[path] = json.load(f)
    return _cache[path]


def tracks_for_module(module_type, data=None):
    """Sorted track numbers of every topic drilled by this module."""
    data = data or load_lt()
    found = set()
    for topic in data["topics"]:
        if module_type in topic["app_modules"]:
            found.update(topic["lt_tracks"])
    return sorted(found)


def ranges(numbers):
    """[58, 59, 60, 61, 87, 88] -> '58–61, 87–88'."""
    out, numbers = [], sorted(set(numbers))
    i = 0
    while i < len(numbers):
        j = i
        while j + 1 < len(numbers) and numbers[j + 1] == numbers[j] + 1:
            j += 1
        out.append(str(numbers[i]) if i == j else f"{numbers[i]}–{numbers[j]}")
        i = j + 1
    return ", ".join(out)


def topic_labels(track, data=None):
    data = data or load_lt()
    by_id = {t["id"]: t for t in data["topics"]}
    return [by_id[t]["label"] for t in track["topics"]]


def is_gap_track(track, data=None):
    """A track that teaches something your lessons haven't covered yet."""
    data = data or load_lt()
    by_id = {t["id"]: t for t in data["topics"]}
    return any(by_id[t]["status"] == "gap" for t in track["topics"])


def next_track(done, total=90):
    return next((n for n in range(1, total + 1) if n not in done), None)
