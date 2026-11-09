"""Language Transfer – Complete Spanish (free 90-track audio course), mapped onto
this app's lessons and drills. Data: data/external/language_transfer.json.
Kept free of Streamlit so it can be tested on its own."""
import json
import os
from datetime import datetime

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


# --- listening progress -------------------------------------------------------
# Saved to a small JSON file next to the progress database (data/progress/,
# git-ignored), because Streamlit's session state resets when the app restarts.

def progress_path(db_path):
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), "lt_progress.json")


def load_done(path):
    try:
        with open(path, encoding="utf-8") as f:
            return set(json.load(f).get("done", []))
    except (OSError, ValueError):
        return set()


def save_done(path, done):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"done": sorted(done), "updated": datetime.now().isoformat(timespec="seconds")}, f)
        return True
    except OSError:
        return False


def next_track(done, total=90):
    return next((n for n in range(1, total + 1) if n not in done), None)
