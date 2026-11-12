"""Persistent attempt log + Leitner-style spaced repetition.

Stored through store.py: a hosted Turso database when one is configured
(so progress survives redeploys and is shared between devices), otherwise a
local SQLite file. Kept free of Streamlit so it can be unit-tested. Every
public function swallows storage errors (no network, read-only filesystem,
locked DB, ...): losing a log line must never break a drill. storage_problem()
says whether the last operation failed, so the app can warn once."""
import hashlib
import json
import os
from collections import OrderedDict
from datetime import datetime, timedelta

from store import SqliteStore, StoreError, TursoStore

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

SCHEMA_VERSION = 2
_CREATE = (
    """CREATE TABLE IF NOT EXISTS attempts (
           id INTEGER PRIMARY KEY AUTOINCREMENT,
           ts TEXT NOT NULL,
           module TEXT,
           exercise_type TEXT,
           target_form TEXT NOT NULL,
           is_correct INTEGER NOT NULL,
           typed_answer TEXT,
           error_tag TEXT,
           card_key TEXT
       )""",
    """CREATE TABLE IF NOT EXISTS cards (
           key TEXT PRIMARY KEY,
           item_json TEXT NOT NULL,
           box INTEGER NOT NULL,
           due TEXT NOT NULL,
           attempts INTEGER NOT NULL DEFAULT 0,
           misses INTEGER NOT NULL DEFAULT 0
       )""",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)",
    # Language Transfer tracks ticked as listened to.
    "CREATE TABLE IF NOT EXISTS lt_done (track INTEGER PRIMARY KEY)",
)
# Columns added to `attempts` after the first version (version 2): what was
# typed, the kind of mistake (see data/concepts.json), and the review card.
_ADDED_ATTEMPT_COLUMNS = ("typed_answer TEXT", "error_tag TEXT", "card_key TEXT")
_ATTEMPT_COLUMNS = ("ts", "module", "exercise_type", "target_form", "is_correct", "typed_answer", "error_tag",
                    "card_key")

_config = {"url": None, "token": None}
_hosted = {}        # (url, token) -> TursoStore, schema already checked
_last_error = None  # message of the last storage failure, cleared by the next success


def configure(url=None, token=None):
    """Use a hosted Turso database (the app passes its secrets here). With no
    arguments, TURSO_DATABASE_URL / TURSO_AUTH_TOKEN from the environment are
    used; with neither, progress goes to the local SQLite file."""
    _config["url"], _config["token"] = url or None, token or None


def _hosted_settings():
    url = _config["url"] or os.environ.get("TURSO_DATABASE_URL")
    token = _config["token"] or os.environ.get("TURSO_AUTH_TOKEN")
    return (url, token) if url and token else None


def is_hosted():
    return _hosted_settings() is not None


def db_path():
    return os.environ.get("SPANISH_PROGRESS_DB") or DEFAULT_DB


def storage_problem():
    """Why the last storage operation failed, or None if it worked."""
    return _last_error


def _ensure_schema(store):
    store.batch([(sql, ()) for sql in _CREATE])
    version = store.query("SELECT value FROM meta WHERE key='schema_version'")
    if version and int(version[0]["value"]) >= SCHEMA_VERSION:
        return
    for column in _ADDED_ATTEMPT_COLUMNS:
        try:
            store.batch([(f"ALTER TABLE attempts ADD COLUMN {column}", ())])
        except StoreError as e:
            if "duplicate column" not in str(e).lower():
                raise
    if not store.hosted:
        _import_legacy_lt_file(store)
    store.batch([("INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                  "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))])


def _import_legacy_lt_file(store):
    """Listening ticks used to live in a JSON file next to the database."""
    legacy = os.path.join(os.path.dirname(os.path.abspath(store.path)), "lt_progress.json")
    try:
        with open(legacy, encoding="utf-8") as f:
            tracks = [int(t) for t in json.load(f).get("done", [])]
    except (OSError, ValueError, TypeError, AttributeError):
        return
    store.batch([("INSERT OR IGNORE INTO lt_done (track) VALUES (?)", (t,)) for t in tracks])


def _store():
    settings = _hosted_settings()
    if settings is None:
        local = SqliteStore(db_path())
        _ensure_schema(local)
        return local
    if settings not in _hosted:
        hosted = TursoStore(*settings)
        _ensure_schema(hosted)
        _hosted[settings] = hosted  # only once the schema is known to be in place
    return _hosted[settings]


# After the hosted database fails, don't try it again for this long: without
# the pause every answer would wait out a network timeout while it is down.
RETRY_AFTER_SECONDS = 30
_paused_until = None
# Writes that could not reach the hosted database (answers given while it
# was unreachable). They are sent, in order, before the next thing that does
# get through. Kept in memory only: a restart of the app loses them.
_unsent = []
MAX_UNSENT = 500


def unsent_count():
    """Answers and ticks waiting for the hosted database to come back."""
    return len(_unsent)


def _run(work, fallback):
    """Run `work(store)`; on any storage failure remember why and return `fallback`."""
    global _last_error, _paused_until
    hosted = is_hosted()
    if hosted and _paused_until and datetime.now() < _paused_until:
        return fallback
    try:
        store = _store()
        if hosted and _unsent:
            store.batch([statement for write in _unsent for statement in write])
            del _unsent[:]
        result = work(store)
    except (StoreError, OSError) as e:
        _last_error = str(e)
        if hosted:
            _paused_until = datetime.now() + timedelta(seconds=RETRY_AFTER_SECONDS)
        return fallback
    _last_error, _paused_until = None, None
    return result


def _write(statements):
    """Run a write. If the hosted database can't be reached, keep it to send
    later and report False (the caller's "not saved yet")."""
    if _run(lambda s: s.batch(statements) is not None, False):
        return True
    if is_hosted() and len(_unsent) < MAX_UNSENT:
        _unsent.append(statements)
    return False


def card_key(item):
    raw = f"{item.get('prompt', '')}|{item['target_form']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def next_state(box, is_correct, now):
    """Pure Leitner step: returns (new_box, due_datetime)."""
    new_box = min(box + 1, len(BOX_INTERVAL_DAYS) - 1) if is_correct else 0
    return new_box, now + timedelta(days=BOX_INTERVAL_DAYS[new_box])


def record_attempt(item, is_correct, module=None, now=None, typed_answer=None, error_tag=None):
    """Log one graded attempt and update the item's Leitner card.

    One round trip: the Leitner step (see next_state) is done in the UPDATE
    itself, so a hosted database doesn't need a read before every write."""
    now = now or datetime.now()
    module = module or item.get("module")
    correct = int(bool(is_correct))
    key = card_key(item)
    stored = {k: item[k] for k in _ITEM_FIELDS if k in item}
    if item.get("fixed_choices"):
        stored["choices"] = item["choices"]
    stored["module"] = module
    top = len(BOX_INTERVAL_DAYS) - 1
    due = [(now + timedelta(days=d)).isoformat() for d in BOX_INTERVAL_DAYS]
    # A first-ever correct answer starts in box 0 and moves to box 1. The
    # stored item is refreshed on every attempt, so a card saved before the
    # app learned more right answers picks them up.
    due_case = " ".join(f"WHEN {b} THEN ?" for b in range(1, top))
    statements = [
        ("INSERT INTO attempts (ts, module, exercise_type, target_form, is_correct, typed_answer, error_tag, card_key) "
         "VALUES (?,?,?,?,?,?,?,?)",
         (now.isoformat(), module, item.get("exercise_type"), item["target_form"], correct,
          typed_answer, error_tag, key)),
        (f"""INSERT INTO cards (key, item_json, box, due, attempts, misses) VALUES (?,?,?,?,1,?)
             ON CONFLICT(key) DO UPDATE SET
               item_json=excluded.item_json,
               due=CASE WHEN ? THEN CASE MIN(cards.box + 1, {top}) {due_case} ELSE ? END ELSE ? END,
               box=CASE WHEN ? THEN MIN(cards.box + 1, {top}) ELSE 0 END,
               attempts=cards.attempts + 1,
               misses=cards.misses + excluded.misses""",
         (key, json.dumps(stored, ensure_ascii=False), 1 if correct else 0, due[1] if correct else due[0],
          0 if correct else 1, correct, *due[1:top], due[top], due[0], correct)),
    ]
    return _write(statements)


def due_items(limit=20, now=None):
    """Items that were missed at some point and are due for review, worst box first."""
    now = now or datetime.now()
    rows = _run(lambda s: s.query(
        "SELECT item_json FROM cards WHERE misses > 0 AND due <= ? ORDER BY box ASC, due ASC LIMIT ?",
        (now.isoformat(), limit)), [])
    return [json.loads(r["item_json"]) for r in rows]


def due_keys(now=None):
    """card_key()s of every card due for review (missed and not yet relearned)."""
    now = now or datetime.now()
    rows = _run(lambda s: s.query("SELECT key FROM cards WHERE misses > 0 AND due <= ?", (now.isoformat(),)), [])
    return {r["key"] for r in rows}


def due_count(now=None):
    now = now or datetime.now()
    rows = _run(lambda s: s.query("SELECT COUNT(*) AS n FROM cards WHERE misses > 0 AND due <= ?",
                                  (now.isoformat(),)), [])
    return rows[0]["n"] if rows else 0


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

    def read(s):
        return (s.query("SELECT ts, module, is_correct FROM attempts"),
                s.query("SELECT box, COUNT(*) AS n FROM cards GROUP BY box"),
                s.query("SELECT COUNT(*) AS n FROM cards WHERE misses > 0 AND due <= ?", (now.isoformat(),)))

    data = _run(read, None)
    if data is None:
        return None
    rows, box_rows, due_rows = data

    by_module, per_day = {}, {}
    week, prev_week = [0, 0], [0, 0]
    for row in rows:
        module, ok = row["module"], row["is_correct"]
        try:
            day = datetime.fromisoformat(row["ts"]).date()
        except (TypeError, ValueError):
            continue  # an unreadable row must not take the whole page down
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
        "boxes": {r["box"]: r["n"] for r in box_rows},
        "due": due_rows[0]["n"],
    }


# --- Language Transfer listening progress ----------------------------------------

def lt_done():
    """Track numbers ticked as listened to."""
    return {r["track"] for r in _run(lambda s: s.query("SELECT track FROM lt_done"), [])}


def set_lt_done(track, done=True):
    sql = "INSERT OR IGNORE INTO lt_done (track) VALUES (?)" if done else "DELETE FROM lt_done WHERE track=?"
    return _write([(sql, (int(track),))])


# --- backup / restore -----------------------------------------------------------
# With a hosted database nothing needs backing up to keep progress across
# redeploys; the export stays as an offline copy, and import_backup is how an
# older local history is moved in (scripts/migrate_progress.py).

BACKUP_VERSION = 2


def export_backup(extra=None, now=None):
    """Everything in the progress database as a JSON-safe dict (plus any
    `extra` fields)."""
    now = now or datetime.now()

    def read(s):
        return (s.query(f"SELECT {', '.join(_ATTEMPT_COLUMNS)} FROM attempts ORDER BY id"),
                s.query("SELECT key, item_json, box, due, attempts, misses FROM cards"),
                sorted(r["track"] for r in s.query("SELECT track FROM lt_done")))

    attempts, cards, tracks = _run(read, ([], [], []))
    return {"app": "spanish-learning", "version": BACKUP_VERSION, "exported": now.isoformat(timespec="seconds"),
            "attempts": attempts, "cards": cards, "lt_done": tracks, **(extra or {})}


def _check_backup_dates(data):
    """Reject a backup whose dates can't be read before anything is stored:
    one bad date in the log would otherwise break the progress page later."""
    for what, rows, field in (("intento", data.get("attempts", []), "ts"), ("tarjeta", data.get("cards", []), "due")):
        for row in rows:
            value = row.get(field) if isinstance(row, dict) else None
            try:
                datetime.fromisoformat(value)
            except (TypeError, ValueError):
                raise ValueError(f"Hay un {what} con una fecha que no se puede leer: {value!r}") from None


def import_backup(data):
    """Merge a backup (version 1 or 2) into the database. Attempts already
    present (same time, item and result) are skipped; for a card in both, the
    one with more recorded attempts wins, so restoring an old file never
    undoes newer progress. Listening ticks are added. Returns (attempts
    added, cards added or updated). Raises ValueError for a file that isn't
    a backup and StoreError if the database can't be written."""
    if not isinstance(data, dict) or data.get("app") != "spanish-learning":
        raise ValueError("Este archivo no es una copia de seguridad de la app.")
    _check_backup_dates(data)
    tracks = [int(t) for t in data.get("lt_done", [])]
    store = _store()
    existing = {(r["ts"], r["target_form"], r["is_correct"])
                for r in store.query("SELECT ts, target_form, is_correct FROM attempts")}
    card_attempts = {r["key"]: r["attempts"] for r in store.query("SELECT key, attempts FROM cards")}
    statements, added_attempts, changed_cards = [], 0, 0
    for a in data.get("attempts", []):
        key = (a["ts"], a["target_form"], int(a["is_correct"]))
        if key in existing:
            continue
        existing.add(key)
        added_attempts += 1
        statements.append((
            f"INSERT INTO attempts ({', '.join(_ATTEMPT_COLUMNS)}) VALUES ({','.join('?' * len(_ATTEMPT_COLUMNS))})",
            (a["ts"], a.get("module"), a.get("exercise_type"), a["target_form"], int(a["is_correct"]),
             a.get("typed_answer"), a.get("error_tag"), a.get("card_key"))))
    for c in data.get("cards", []):
        if card_attempts.get(c["key"], -1) >= c["attempts"]:
            continue
        card_attempts[c["key"]] = c["attempts"]
        changed_cards += 1
        statements.append((
            """INSERT INTO cards (key, item_json, box, due, attempts, misses) VALUES (?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET item_json=excluded.item_json, box=excluded.box,
               due=excluded.due, attempts=excluded.attempts, misses=excluded.misses""",
            (c["key"], c["item_json"], c["box"], c["due"], c["attempts"], c["misses"])))
    statements += [("INSERT OR IGNORE INTO lt_done (track) VALUES (?)", (t,)) for t in tracks]
    if statements:
        store.batch(statements)
    return added_attempts, changed_cards
