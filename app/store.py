"""Where progress is kept: a local SQLite file, or a hosted Turso (libSQL)
database reached over its HTTP API.

Both speak the same SQL (libSQL is SQLite), so progress.py is written once
against this small interface:

    store.query(sql, args)      -> list of dict rows
    store.batch([(sql, args)])  -> list of affected-row counts, all in one
                                   transaction (all or nothing)

The Turso client uses only the standard library, so the deployed app needs
no extra package. Kept free of Streamlit."""
import http.client
import json
import os
import sqlite3
import threading
from urllib.parse import urlsplit

# Recorded so spanish_drill.py can tell when this file changed under a running
# app and reload it (see _reload_stale_modules there).
_SOURCE_MTIME = os.path.getmtime(__file__)


class StoreError(Exception):
    """The store could not run a statement (network, auth, or SQL error)."""


class SqliteStore:
    hosted = False

    def __init__(self, path):
        self.path = path

    def _connect(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql, args=()):
        try:
            conn = self._connect()
            try:
                return [dict(r) for r in conn.execute(sql, tuple(args))]
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as e:
            raise StoreError(str(e)) from e

    def batch(self, statements):
        try:
            conn = self._connect()
            try:
                with conn:  # one transaction: commit on success, roll back on error
                    return [conn.execute(sql, tuple(args)).rowcount for sql, args in statements]
            finally:
                conn.close()
        except (sqlite3.Error, OSError) as e:
            raise StoreError(str(e)) from e


def _encode(value):
    """A Python value as a Hrana (Turso HTTP protocol) value."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


def _decode(cell):
    kind = cell.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(cell["value"])
    if kind == "float":
        return float(cell["value"])
    return cell.get("value")


def _stmt(sql, args):
    return {"sql": sql, "args": [_encode(a) for a in args]}


class TursoStore:
    """Turso over HTTP: POST {url}/v2/pipeline with a bearer token. One
    connection is kept open between calls, since a new TLS handshake per
    answer would be the slowest part of answering a question."""
    hosted = True
    BATCH_LIMIT = 400  # statements per request, to keep request bodies modest

    def __init__(self, url, token, timeout=6):
        parts = urlsplit(url if "://" in url else f"https://{url}")
        if not parts.hostname:
            raise StoreError(f"TURSO_DATABASE_URL no es una URL válida: {url!r}")
        self.host, self.port = parts.hostname, parts.port
        self.secure = parts.scheme != "http"  # libsql://, https://, wss:// all mean TLS
        self.token, self.timeout = token, timeout
        self._conn = None
        self._lock = threading.Lock()

    def _post(self, body):
        payload = json.dumps(body).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        last = None
        for attempt in range(2):  # a kept-open connection may have gone stale: retry once on a fresh one
            try:
                if self._conn is None:
                    cls = http.client.HTTPSConnection if self.secure else http.client.HTTPConnection
                    self._conn = cls(self.host, self.port, timeout=self.timeout)
                self._conn.request("POST", "/v2/pipeline", body=payload, headers=headers)
                response = self._conn.getresponse()
                raw = response.read()
                if response.status != 200:
                    raise StoreError(f"Turso respondió {response.status}: {raw[:200].decode('utf-8', 'replace')}")
                return json.loads(raw)
            except (OSError, http.client.HTTPException, ValueError) as e:
                last = e
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None
        raise StoreError(f"No se pudo conectar con Turso: {last}") from last

    def _pipeline(self, request):
        with self._lock:
            reply = self._post({"requests": [request, {"type": "close"}]})
        result = (reply.get("results") or [{}])[0]
        if result.get("type") != "ok":
            raise StoreError((result.get("error") or {}).get("message", "error desconocido de Turso"))
        return result["response"]["result"]

    def query(self, sql, args=()):
        result = self._pipeline({"type": "execute", "stmt": _stmt(sql, args)})
        names = [c["name"] for c in result["cols"]]
        return [dict(zip(names, (_decode(c) for c in row))) for row in result["rows"]]

    def batch(self, statements):
        statements = list(statements)
        counts = []
        for start in range(0, len(statements), self.BATCH_LIMIT):
            counts += self._transaction(statements[start:start + self.BATCH_LIMIT])
        return counts

    def _transaction(self, statements):
        # BEGIN, each statement only if the one before worked, COMMIT only if
        # the last one worked, ROLLBACK otherwise.
        steps = [{"stmt": _stmt("BEGIN", ())}]
        for sql, args in statements:
            steps.append({"stmt": _stmt(sql, args), "condition": {"type": "ok", "step": len(steps) - 1}})
        commit = len(steps)
        steps.append({"stmt": _stmt("COMMIT", ()), "condition": {"type": "ok", "step": commit - 1}})
        steps.append({"stmt": _stmt("ROLLBACK", ()),
                      "condition": {"type": "not", "cond": {"type": "ok", "step": commit}}})
        result = self._pipeline({"type": "batch", "batch": {"steps": steps}})
        errors = result.get("step_errors") or []
        for i in range(commit + 1):
            if i < len(errors) and errors[i]:
                raise StoreError(errors[i].get("message", "error de Turso"))
        results = result.get("step_results") or []
        if len(results) <= commit or results[commit] is None:
            raise StoreError("Turso no confirmó la transacción.")
        return [(results[i] or {}).get("affected_row_count", 0) for i in range(1, commit)]
