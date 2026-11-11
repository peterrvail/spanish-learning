"""A stand-in for Turso's HTTP API (POST /v2/pipeline, "execute" and "batch"
requests with step conditions), backed by an in-memory SQLite database. It
lets the tests run progress.py against the hosted code path without a
network. It follows the protocol as documented; it is not Turso."""
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _value(arg):
    kind = arg["type"]
    if kind == "null":
        return None
    if kind == "integer":
        return int(arg["value"])
    if kind == "float":
        return float(arg["value"])
    return arg["value"]


def _cell(v):
    if v is None:
        return {"type": "null"}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


class FakeTurso:
    def __init__(self, token="secret"):
        self.token = token
        self.db = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
        self.lock = threading.Lock()
        self.requests = 0          # HTTP requests served
        self.fail_next = 0         # answer this many requests with a 500
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests += 1
                if outer.fail_next:
                    outer.fail_next -= 1
                    return self._send(500, {"error": "boom"})
                if self.path != "/v2/pipeline" or self.headers.get("Authorization") != f"Bearer {outer.token}":
                    return self._send(401, {"error": "unauthorized"})
                with outer.lock:
                    results = [outer._request(r) for r in body["requests"]]
                self._send(200, {"baton": None, "base_url": None, "results": results})

            def _send(self, status, payload):
                raw = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def _execute(self, stmt):
        cur = self.db.execute(stmt["sql"], [_value(a) for a in stmt.get("args", [])])
        cols = [{"name": d[0]} for d in (cur.description or [])]
        rows = [[_cell(v) for v in row] for row in cur.fetchall()] if cur.description else []
        return {"cols": cols, "rows": rows, "affected_row_count": max(cur.rowcount, 0)}

    def _request(self, request):
        if request["type"] == "close":
            return {"type": "ok", "response": {"type": "close"}}
        try:
            if request["type"] == "execute":
                return {"type": "ok", "response": {"type": "execute", "result": self._execute(request["stmt"])}}
            if request["type"] == "batch":
                return {"type": "ok", "response": {"type": "batch", "result": self._batch(request["batch"]["steps"])}}
        except sqlite3.Error as e:
            return {"type": "error", "error": {"message": str(e)}}
        return {"type": "error", "error": {"message": "unsupported request"}}

    def _batch(self, steps):
        results, errors = [], []

        def holds(cond):
            if cond is None:
                return True
            if cond["type"] == "ok":
                return results[cond["step"]] is not None
            if cond["type"] == "error":
                return errors[cond["step"]] is not None
            if cond["type"] == "not":
                return not holds(cond["cond"])
            raise ValueError(cond)

        for step in steps:
            if not holds(step.get("condition")):
                results.append(None)
                errors.append(None)
                continue
            try:
                results.append(self._execute(step["stmt"]))
                errors.append(None)
            except sqlite3.Error as e:
                results.append(None)
                errors.append({"message": str(e)})
        return {"step_results": results, "step_errors": errors}
