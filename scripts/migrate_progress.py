#!/usr/bin/env python3
"""Move a progress backup into the configured database (one-off).

    TURSO_DATABASE_URL=libsql://<db>-<org>.turso.io TURSO_AUTH_TOKEN=<token> \\
        python scripts/migrate_progress.py progreso_espanol_2026-11-11.json

The backup is the JSON downloaded from "Mi progreso" (either format version).
It is merged, not copied over: attempts already there are skipped and a card
is only replaced by one with more attempts, so running this twice is safe.
Without the two TURSO_ variables it writes to the local SQLite file instead,
and says so.

    python scripts/migrate_progress.py --check

tests the connection first: it writes, reads back and removes one marker row,
and confirms a failed transaction leaves nothing behind."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
import progress  # noqa: E402
from store import StoreError  # noqa: E402


def check():
    """Prove the database works end to end without leaving anything behind:
    tables exist, a write can be read back, and a failed transaction leaves
    no trace (that is what keeps an interrupted import from half-applying)."""
    try:
        db = progress._store()  # creates the tables if they are missing
        db.batch([("INSERT OR REPLACE INTO meta (key, value) VALUES ('check', 'ok')", ())])
        assert db.query("SELECT value FROM meta WHERE key='check'") == [{"value": "ok"}], "write not read back"
        try:
            db.batch([("UPDATE meta SET value='half' WHERE key='check'", ()),
                      ("INSERT INTO no_such_table VALUES (1)", ())])
            raise AssertionError("a failing transaction did not report an error")
        except StoreError:
            pass
        assert db.query("SELECT value FROM meta WHERE key='check'") == [{"value": "ok"}], "failed transaction was kept"
        db.batch([("DELETE FROM meta WHERE key='check'", ())])
        counts = {t: db.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in ("attempts", "cards", "lt_done")}
    except (StoreError, AssertionError) as e:
        print(f"CHECK FAILED: {e}")
        return 1
    print(f"Check passed. In the database now: {counts['attempts']} attempts, {counts['cards']} cards, "
          f"{counts['lt_done']} tracks listened.")
    return 0


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    target = "Turso (hosted)" if progress.is_hosted() else f"local file {os.path.abspath(progress.db_path())}"
    print(f"Database: {target}")
    if argv[1] == "--check":
        return check()
    try:
        with open(argv[1], encoding="utf-8") as f:
            data = json.load(f)
        before = len(progress.lt_done())
        attempts, cards = progress.import_backup(data)
    except (OSError, ValueError, KeyError, TypeError, StoreError) as e:
        print(f"Failed, nothing was changed: {e}")
        return 1
    stats = progress.stats()
    print(f"Added {attempts} attempts, {cards} review cards, {len(progress.lt_done()) - before} listening ticks.")
    print(f"Now in the database: {stats['total']} attempts, {sum(stats['boxes'].values())} cards, "
          f"{stats['due']} due for review, {len(progress.lt_done())} tracks listened.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
