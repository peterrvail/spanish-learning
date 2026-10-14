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

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "progress", "progress.db")

# Leitner boxes: box 0 = missed (review now); each correct answer moves a card
# up one box and pushes its next review out by the matching interval.
BOX_INTERVAL_DAYS = [0, 1, 7, 14]

_ITEM_FIELDS = ("prompt", "target_form", "accepted_forms", "exercise_type", "explanation", "module")


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
