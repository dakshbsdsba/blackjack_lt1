#!/usr/bin/env python3
"""Serve the blackjack presentation and persist editable speaker notes.

The deck is static. The only dynamic surface is:
  GET  /api/notes        -> {"notes": {"1": "...", ...}, "updatedAt": "..."}
  PUT  /api/notes/<n>    -> {"text": "..."} with a 1000-character / 200-word limit
  GET  /api/health       -> {"ok": true}

Notes live outside the repository so a git pull never replaces them. Under
systemd the path comes from STATE_DIRECTORY=/var/lib/blackjack-presentation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import threading
from functools import partial
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

MAX_CHARS = 1000
MAX_WORDS = 200
SLIDE_COUNT = 22
MAX_BODY = 64 * 1024
LOCK = threading.Lock()
WORD_RE = re.compile(r"\S+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_state(path: Path) -> dict:
    if not path.exists():
        return {"notes": {}, "updatedAt": None}
    try:
        data = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        return {"notes": {}, "updatedAt": None}
    notes = data.get("notes") if isinstance(data, dict) else None
    if not isinstance(notes, dict):
        notes = {}
    clean = {str(k): v for k, v in notes.items() if isinstance(v, str)}
    return {
        "notes": clean,
        "updatedAt": data.get("updatedAt") if isinstance(data, dict) else None,
    }


def write_state(path: Path, notes: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"notes": notes, "updatedAt": utc_now()}
    if path.exists():
        try:
            shutil.copy2(path, path.with_suffix(".bak"))
        except OSError:
            pass
    handle, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=".notes-", suffix=".tmp"
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return payload


def validate_note(text: str) -> str | None:
    if len(text) > MAX_CHARS:
        return f"Note must be at most {MAX_CHARS} characters"
    if len(WORD_RE.findall(text)) > MAX_WORDS:
        return f"Note must be at most {MAX_WORDS} words"
    return None


class NotesHandler(SimpleHTTPRequestHandler):
    server_version = "BlackjackNotes/1.0"

    def __init__(
        self,
        *args,
        directory: str | None = None,
        notes_file: Path | None = None,
        **kwargs,
    ):
        self.notes_file = notes_file or Path("notes.json")
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        if self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json(
                HTTPStatus.OK, {"ok": True, "notesFile": str(self.notes_file)}
            )
            return
        if path == "/api/notes":
            with LOCK:
                data = read_state(self.notes_file)
            self.send_json(HTTPStatus.OK, data)
            return
        super().do_GET()

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/notes/(\d+)", path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
            return
        slide = int(match.group(1))
        if slide < 1 or slide > SLIDE_COUNT:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown slide"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request size"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Body must be JSON"})
            return
        text = payload.get("text") if isinstance(payload, dict) else None
        if not isinstance(text, str):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "text must be a string"})
            return
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        problem = validate_note(text)
        if problem:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": problem})
            return
        with LOCK:
            data = read_state(self.notes_file)
            data["notes"][str(slide)] = text
            saved = write_state(self.notes_file, data["notes"])
        self.send_json(
            HTTPStatus.OK,
            {"ok": True, "slide": slide, "text": text, "updatedAt": saved["updatedAt"]},
        )

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "GET, PUT, OPTIONS")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent))
    parser.add_argument(
        "--state",
        default=os.environ.get("STATE_DIRECTORY") or "/var/lib/blackjack-presentation",
    )
    args = parser.parse_args()
    state_dir = Path(args.state.split(":")[0])
    notes_file = state_dir / "notes.json"
    handler = partial(NotesHandler, directory=args.root, notes_file=notes_file)
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(
        f"Serving {args.root} on http://{args.bind}:{args.port} (notes: {notes_file})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
