#!/usr/bin/env python3
"""
earnkit-runner — localhost HTTP service that executes add-team.yml on request.

The one machine-triggered doorway into team provisioning: amebo calls it when a
brand-new org arrives from a GovKit founder accept (see amebo's
team_stack_runner.py), so the venture gets its full stack (Odoo DB, Taiga
project, instance row, Caddy route) without an operator SSH session. Humans keep
using ansible-playbook directly; this service is for services.

Deliberately tiny and dependency-free (Python stdlib only): it validates a
bearer token, validates the two variables, and hands off to the sudo-whitelisted
wrapper /opt/earnkit/bin/run-add-team — the same one-job-at-a-time queue an
operator terminal is. It binds 127.0.0.1 only; the token is defense in depth,
not the perimeter.

API (all JSON):
  POST /run/add-team {"team_slug": ..., "team_name": ...} -> 202 {"job_id": ...}
       409 if a job for that slug is already queued/running; 400 on bad input.
  GET  /jobs           -> most recent jobs, newest first
  GET  /jobs/<id>      -> one job + the tail of its playbook log
  GET  /health         -> {"ok": true}

State: one JSON + one log file per job under RUNNER_STATE_DIR/jobs. Queue is
in-memory (jobs queued but not started are lost on restart — visible as
'queued' in state with no outcome; the caller's reconcile/retry covers that).
Env: RUNNER_TOKEN (required), RUNNER_PORT, RUNNER_STATE_DIR, RUNNER_WRAPPER.
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("earnkit-runner")

TOKEN = os.environ.get("RUNNER_TOKEN") or ""
PORT = int(os.environ.get("RUNNER_PORT") or "8946")
STATE_DIR = os.environ.get("RUNNER_STATE_DIR") or "/var/lib/earnkit-runner"
WRAPPER = os.environ.get("RUNNER_WRAPPER") or "/opt/earnkit/bin/run-add-team"
# "0" runs the wrapper directly — tests only; deployed units keep the default.
USE_SUDO = (os.environ.get("RUNNER_USE_SUDO") or "1") != "0"
JOBS_DIR = os.path.join(STATE_DIR, "jobs")

# Same shape add-team.yml itself asserts; the wrapper re-checks (defense in depth).
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")

_queue: "queue.Queue[str]" = queue.Queue()
_lock = threading.Lock()  # guards job-state read/modify/write across threads


def _job_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def _log_path(job_id: str) -> str:
    return os.path.join(JOBS_DIR, f"{job_id}.log")


def _read_job(job_id: str) -> dict | None:
    try:
        with open(_job_path(job_id)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_job(job: dict) -> None:
    path = _job_path(job["job_id"])
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(job, f)
    os.replace(tmp, path)


def _all_jobs() -> list[dict]:
    jobs = []
    try:
        names = os.listdir(JOBS_DIR)
    except OSError:
        return []
    for name in names:
        if name.endswith(".json"):
            job = _read_job(name[:-5])
            if job:
                jobs.append(job)
    jobs.sort(key=lambda j: j.get("created_at", ""), reverse=True)
    return jobs


def _slug_busy(slug: str) -> bool:
    return any(
        j["team_slug"] == slug and j["state"] in ("queued", "running") for j in _all_jobs()
    )


def _worker() -> None:
    """One job at a time, forever. The playbook is not concurrency-safe per VM
    (shared Odoo/Taiga shells), so serialization IS the correctness model."""
    while True:
        job_id = _queue.get()
        with _lock:
            job = _read_job(job_id)
            if job is None:
                continue
            job["state"] = "running"
            job["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _write_job(job)
        argv = (["sudo", "-n"] if USE_SUDO else []) + [WRAPPER, job["team_slug"], job["team_name"]]
        logger.info("job %s: %s", job_id, " ".join(argv[:3] + [job["team_slug"], "..."]))
        try:
            with open(_log_path(job_id), "ab") as log:
                rc = subprocess.run(
                    argv, stdout=log, stderr=subprocess.STDOUT, timeout=1800
                ).returncode
        except subprocess.TimeoutExpired:
            rc = -1
        except OSError as exc:
            rc = -2
            logger.error("job %s failed to start: %s", job_id, exc)
        with _lock:
            job = _read_job(job_id) or job
            job["state"] = "done" if rc == 0 else "failed"
            job["returncode"] = rc
            job["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _write_job(job)
        logger.info("job %s finished: %s (rc=%s)", job_id, job["state"], rc)


class Handler(BaseHTTPRequestHandler):
    server_version = "earnkit-runner"

    def log_message(self, fmt, *args):  # route http.server chatter into logging
        logger.info("%s %s", self.address_string(), fmt % args)

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self) -> bool:
        header = self.headers.get("Authorization") or ""
        presented = header[len("Bearer "):] if header.startswith("Bearer ") else ""
        return bool(TOKEN) and hmac.compare_digest(presented.encode(), TOKEN.encode())

    def do_GET(self):
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if not self._authed():
            return self._send(401, {"error": "bad or missing bearer token"})
        if self.path == "/jobs":
            return self._send(200, {"jobs": _all_jobs()[:50]})
        if self.path.startswith("/jobs/"):
            job_id = self.path[len("/jobs/"):].strip("/")
            if not re.fullmatch(r"[a-f0-9-]{8,40}", job_id):
                return self._send(400, {"error": "bad job id"})
            job = _read_job(job_id)
            if job is None:
                return self._send(404, {"error": "no such job"})
            try:
                with open(_log_path(job_id), "rb") as f:
                    f.seek(0, os.SEEK_END)
                    f.seek(max(0, f.tell() - 8000))
                    job["log_tail"] = f.read().decode(errors="replace")
            except OSError:
                job["log_tail"] = ""
            return self._send(200, job)
        return self._send(404, {"error": "unknown path"})

    def do_POST(self):
        if not self._authed():
            return self._send(401, {"error": "bad or missing bearer token"})
        if self.path != "/run/add-team":
            return self._send(404, {"error": "unknown path"})
        try:
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._send(400, {"error": "body is not JSON"})
        slug = body.get("team_slug") or ""
        name = (body.get("team_name") or "").strip()
        if not SLUG_RE.fullmatch(slug):
            return self._send(400, {"error": "team_slug must match [a-z0-9][a-z0-9-]{1,30}"})
        if not (1 < len(name) <= 255) or any(ord(c) < 32 for c in name):
            return self._send(400, {"error": "team_name must be 2-255 printable characters"})
        with _lock:
            if _slug_busy(slug):
                return self._send(409, {"error": f"a job for '{slug}' is already queued/running"})
            job = {
                "job_id": uuid.uuid4().hex,
                "team_slug": slug,
                "team_name": name,
                "state": "queued",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            _write_job(job)
        _queue.put(job["job_id"])
        logger.info("job %s queued for team %s", job["job_id"], slug)
        return self._send(202, {"job_id": job["job_id"]})


def main() -> None:
    if not TOKEN:
        raise SystemExit("RUNNER_TOKEN is not set; refusing to start without auth.")
    os.makedirs(JOBS_DIR, exist_ok=True)
    threading.Thread(target=_worker, daemon=True, name="job-worker").start()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    logger.info("earnkit-runner listening on 127.0.0.1:%s", PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
