"""Persistent attempt log + Leitner-style spaced repetition (SQLite, stdlib only).

Kept free of Streamlit so it can be unit-tested. Every public function swallows
storage errors (read-only filesystem, locked DB, ...): losing a log line must
never break a drill."""
import hashlib
import json
import os
import sqlite3
from collections import OrderedDict
from datetime import datetime, timedelta

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "progress", "progress.db")

# Leitner boxes: box 0 = missed (review now); each correct answer moves a card
# up one box and pushes its next review out by the matching interval.
BOX_INTERVAL_DAYS = [0, 1, 7, 14]

# What a missed item keeps so "!drill fallos" can ask it again as it was:
# its other right answers (also_accepted) and, for questions that come with
# their own options (e.g. "which kind of se?"), those options. Options that
# the drill added at random for multiple choice are not kept.
_ITEM_FIELDS = ("prompt", "target_form", "accepted_forms", "also_accepted", "exercise_type", "explanation",
                "module", "fixed_choices")


def db_path():
    return os.environ.get("SPANISH_PROGRESS_DB") or DEFAULT_DB


def _connect():
    path = db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            module TEXT,
            exercise_type TEXT,
            target_form TEXT NOT NULL,
            is_correct INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cards (
            key TEXT PRIMARY KEY,
            item_json TEXT NOT NULL,
            box INTEGER NOT NULL,
            due TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            misses INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    return conn


def card_key(item):
    raw = f"{item.get('prompt', '')}|{item['target_form']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def next_state(box, is_correct, now):
    """Pure Leitner step: returns (new_box, due_datetime)."""
    new_box = min(box + 1, len(BOX_INTERVAL_DAYS) - 1) if is_correct else 0
    return new_box, now + timedelta(days=BOX_INTERVAL_DAYS[new_box])


def record_attempt(item, is_correct, module=None, now=None):
    """Log one graded attempt and update the item's Leitner card."""
    now = now or datetime.now()
    module = module or item.get("module")
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO attempts (ts, module, exercise_type, target_form, is_correct) VALUES (?,?,?,?,?)",
                (now.isoformat(), module, item.get("exercise_type"), item["target_form"], int(bool(is_correct))),
            )
            key = card_key(item)
            row = conn.execute("SELECT box, misses FROM cards WHERE key=?", (key,)).fetchone()
            box, misses = (row["box"], row["misses"]) if row else (0, 0)
            # A first-ever correct answer starts in box 0 and moves to box 1.
            new_box, due = next_state(box, bool(is_correct), now)
            stored = {k: item[k] for k in _ITEM_FIELDS if k in item}
            if item.get("fixed_choices"):
                stored["choices"] = item["choices"]
            stored["module"] = module
            conn.execute(
                """INSERT INTO cards (key, item_json, box, due, attempts, misses) VALUES (?,?,?,?,1,?)
                   ON CONFLICT(key) DO UPDATE SET box=excluded.box, due=excluded.due,
                   attempts=attempts+1, misses=misses+excluded.misses""",
                (key, json.dumps(stored, ensure_ascii=False), new_box, due.isoformat(), 0 if is_correct else 1),
            )
        return True
    except (sqlite3.Error, OSError):
        return False


def due_items(limit=20, now=None):
    """Items that were missed at some point and are due for review, worst box first."""
    now = now or datetime.now()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT item_json FROM cards WHERE misses > 0 AND due <= ? ORDER BY box ASC, due ASC LIMIT ?",
                (now.isoformat(), limit),
            ).fetchall()
    except (sqlite3.Error, OSError):
        return []
    return [json.loads(r["item_json"]) for r in rows]


def due_keys(now=None):
    """card_key()s of every card due for review (missed and not yet relearned)."""
    now = now or datetime.now()
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT key FROM cards WHERE misses > 0 AND due <= ?", (now.isoformat(),)).fetchall()
    except (sqlite3.Error, OSError):
        return set()
    return {r["key"] for r in rows}


def due_count(now=None):
    now = now or datetime.now()
    try:
        with _connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM cards WHERE misses > 0 AND due <= ?", (now.isoformat(),)
            ).fetchone()[0]
    except (sqlite3.Error, OSError):
        return 0


def breakdown(answers):
    """Per-group tally of graded answers: OrderedDict label -> (correct, total).

    Groups by exercise_type ('preterite_irregular', 'por_para', ...), which is
    finer than the module and so shows *which kind* of item is weak. In the
    interleaved drill each item comes from a different module, so group by
    module there instead."""
    use_module = len({a.get("module") for a in answers if a.get("module")}) > 1
    tally = OrderedDict()
    for a in answers:
        label = (a.get("module") if use_module else a.get("exercise_type")) or "otros"
        right, total = tally.get(label, (0, 0))
        tally[label] = (right + (1 if a["is_correct"] else 0), total + 1)
    return OrderedDict(sorted(tally.items(), key=lambda kv: (kv[1][0] / kv[1][1], kv[0])))


def streak_days(days, today):
    """Consecutive practice days ending today, or yesterday if today has no
    attempts yet (so the streak isn't shown as broken first thing in the morning)."""
    days = set(days)
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def stats(now=None, window_days=14):
    """Everything the progress page shows, from the attempt log and cards.
    Returns None when the log can't be read."""
    now = now or datetime.now()
    today = now.date()
    try:
        with _connect() as conn:
            rows = conn.execute("SELECT ts, module, is_correct FROM attempts").fetchall()
            box_rows = conn.execute("SELECT box, COUNT(*) FROM cards GROUP BY box").fetchall()
            due = conn.execute(
                "SELECT COUNT(*) FROM cards WHERE misses > 0 AND due <= ?", (now.isoformat(),)
            ).fetchone()[0]
    except (sqlite3.Error, OSError):
        return None

    by_module, per_day = {}, {}
    week, prev_week = [0, 0], [0, 0]
    for ts, module, ok in rows:
        day = datetime.fromisoformat(ts).date()
        per_day[day] = per_day.get(day, 0) + 1
        m = by_module.setdefault(module or "otros", [0, 0, day])
        m[0] += ok
        m[1] += 1
        m[2] = max(m[2], day)
        age = (today - day).days
        bucket = week if age < 7 else prev_week if age < 14 else None
        if bucket is not None:
            bucket[0] += ok
            bucket[1] += 1

    return {
        "total": len(rows),
        "streak": streak_days(per_day, today),
        "week": tuple(week),
        "prev_week": tuple(prev_week),
        # weakest first, so the top of the table is what to practice
        "by_module": sorted(((m, c, t, last) for m, (c, t, last) in by_module.items()),
                            key=lambda r: (r[1] / r[2], -r[2])),
        "daily": [(today - timedelta(days=i), per_day.get(today - timedelta(days=i), 0))
                  for i in range(window_days - 1, -1, -1)],
        "boxes": {box: n for box, n in box_rows},
        "due": due,
    }


# --- backup / restore -----------------------------------------------------------
# Streamlit Community Cloud does not keep files the app writes: every reboot or
# redeploy starts from a fresh copy of the repo, so the progress database is
# lost. These let the learner download everything and upload it again later.

BACKUP_VERSION = 1


def export_backup(extra=None, now=None):
    """Everything in the progress database as a JSON-safe dict (plus any
    `extra` fields, e.g. listening progress)."""
    now = now or datetime.now()
    try:
        with _connect() as conn:
            attempts = [dict(r) for r in conn.execute(
                "SELECT ts, module, exercise_type, target_form, is_correct FROM attempts ORDER BY id")]
            cards = [dict(r) for r in conn.execute(
                "SELECT key, item_json, box, due, attempts, misses FROM cards")]
    except (sqlite3.Error, OSError):
        attempts, cards = [], []
    return {"app": "spanish-learning", "version": BACKUP_VERSION, "exported": now.isoformat(timespec="seconds"),
            "attempts": attempts, "cards": cards, **(extra or {})}


def import_backup(data):
    """Merge a backup into the database. Attempts already present (same
    time, item and result) are skipped; for a card in both, the one with
    more recorded attempts wins, so restoring an old file never undoes newer
    progress. Returns (attempts added, cards added or updated)."""
    if not isinstance(data, dict) or data.get("app") != "spanish-learning":
        raise ValueError("Este archivo no es una copia de seguridad de la app.")
    added_attempts = changed_cards = 0
    with _connect() as conn:
        existing = {(r["ts"], r["target_form"], r["is_correct"]) for r in
                    conn.execute("SELECT ts, target_form, is_correct FROM attempts")}
        for a in data.get("attempts", []):
            key = (a["ts"], a["target_form"], int(a["is_correct"]))
            if key in existing:
                continue
            conn.execute("INSERT INTO attempts (ts, module, exercise_type, target_form, is_correct) VALUES (?,?,?,?,?)",
                         (a["ts"], a.get("module"), a.get("exercise_type"), a["target_form"], int(a["is_correct"])))
            existing.add(key)
            added_attempts += 1
        for c in data.get("cards", []):
            row = conn.execute("SELECT attempts FROM cards WHERE key=?", (c["key"],)).fetchone()
            if row is not None and row["attempts"] >= c["attempts"]:
                continue
            conn.execute(
                """INSERT INTO cards (key, item_json, box, due, attempts, misses) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(key) DO UPDATE SET item_json=excluded.item_json, box=excluded.box,
                   due=excluded.due, attempts=excluded.attempts, misses=excluded.misses""",
                (c["key"], c["item_json"], c["box"], c["due"], c["attempts"], c["misses"]))
            changed_cards += 1
    return added_attempts, changed_cards
