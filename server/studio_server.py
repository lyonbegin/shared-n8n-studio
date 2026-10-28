#!/usr/bin/env python3
"""Shared n8n Studio static UI + isolated SQLite draft service.

Pure stdlib. NEVER executes workflows or proxies any n8n/trading/business API.
Each anonymous browser receives an unguessable HttpOnly cookie: its drafts are
server-stored, but cannot be accessed across devices without future auth.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Lock
from urllib.parse import unquote, urlsplit

ROOT = Path(os.environ.get("STUDIO_STATIC_ROOT", "/app/dist")).resolve()
WORKFLOW_ROOT = (ROOT / "stock-workflows").resolve()
DB_PATH = Path(os.environ.get("STUDIO_DB_PATH", "/data/studio.sqlite3"))
PORT = int(os.environ.get("PORT", "3000"))
MAX_BYTES = 1_048_576
MAX_NODES = 350
SID = re.compile(r"^[a-f0-9]{48}$")
KEY = re.compile(r"^(operations|scenarios)/[a-zA-Z0-9_.-]+\.json$")
LOCK = Lock()

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH, timeout=15) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            sid TEXT NOT NULL, path TEXT NOT NULL, version INTEGER NOT NULL,
            payload TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (sid, path))""")
        db.execute("""CREATE TABLE IF NOT EXISTS revisions (
            sid TEXT NOT NULL, path TEXT NOT NULL, version INTEGER NOT NULL,
            payload TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (sid, path, version))""")

def db_connect():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    return db

def fixture_path(key: str) -> Path:
    if not KEY.fullmatch(key):
        raise ValueError("허용되지 않는 워크플로 경로")
    result = (WORKFLOW_ROOT / key).resolve()
    if not result.is_relative_to(WORKFLOW_ROOT) or not result.is_file():
        raise ValueError("존재하지 않는 원본 워크플로")
    return result

def validate_workflow(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("워크플로 JSON 객체 필요")
    nodes = payload.get("nodes")
    connections = payload.get("connections")
    if not isinstance(nodes, list) or not 0 < len(nodes) <= MAX_NODES or not isinstance(connections, dict):
        raise ValueError("nodes 또는 connections 형식 오류")
    ids, names = set(), set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or not isinstance(n.get("name"), str) or not isinstance(n.get("type"), str):
            raise ValueError("노드 id/name/type 형식 오류")
        if not n["id"] or len(n["id"]) > 128 or not n["name"] or len(n["name"]) > 180:
            raise ValueError("노드 식별자 크기 오류")
        if n["id"] in ids or n["name"] in names:
            raise ValueError("노드 id/name 중복")
        ids.add(n["id"]); names.add(n["name"])
        position = n.get("position")
        if not isinstance(position, list) or len(position) != 2 or any(not isinstance(v, (int, float)) or isinstance(v, bool) or abs(v) > 10_000_000 for v in position):
            raise ValueError("노드 위치 형식 오류")
        if not isinstance(n.get("parameters", {}), dict):
            raise ValueError("노드 parameters 형식 오류")
    edges_count = 0
    for source, ports in connections.items():
        if source not in names or not isinstance(ports, dict):
            raise ValueError("존재하지 않는 원본 연결")
        for outputs in ports.values():
            if not isinstance(outputs, list):
                raise ValueError("출력 포트 형식 오류")
            for targets in outputs:
                if not isinstance(targets, list):
                    raise ValueError("연결 목록 형식 오류")
                for t in targets:
                    edges_count += 1
                    if not isinstance(t, dict) or t.get("node") not in names or not isinstance(t.get("index"), int):
                        raise ValueError("존재하지 않는 대상 노드")
                    if edges_count > 1500:
                        raise ValueError("연결선 한도 초과")
    safe = dict(payload)
    safe["active"] = False  # No public write is allowed to activate a workflow
    return safe

class Handler(BaseHTTPRequestHandler):
    server_version = "SharedN8nStudio/1"
    def log_message(self, format, *args):
        print("%s %s" % (self.address_string(), format % args), flush=True)

    def _sid(self):
        raw = self.headers.get("Cookie", "")
        for cookie in raw.split(";"):
            k, _, v = cookie.strip().partition("=")
            if k == "studio_sid" and SID.fullmatch(v):
                return v, False
        return secrets.token_hex(24), True

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", sid=None, new_cookie=False, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if "json" in ctype or code != 200 else "public, max-age=120")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if sid and new_cookie:
            secure = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
            self.send_header("Set-Cookie", "studio_sid="+sid+"; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000"+secure)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code, obj, sid=None, new_cookie=False):
        self._send(code, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), sid=sid, new_cookie=new_cookie)

    def _workflow_request(self, method, path):
        sid, new_cookie = self._sid()
        tail = unquote(path.removeprefix("/api/studio/workflows/"))
        is_versions = tail.endswith("/versions")
        key = tail[:-len("/versions")] if is_versions else tail
        try:
            fixture = fixture_path(key)
        except ValueError as e:
            return self._json(404, {"error": str(e)}, sid, new_cookie)
        if is_versions:
            if method != "GET":
                return self._json(405, {"error": "허용되지 않는 메서드"}, sid, new_cookie)
            with db_connect() as db:
                rows = db.execute("SELECT version, created_at FROM revisions WHERE sid=? AND path=? ORDER BY version DESC LIMIT 30", (sid, key)).fetchall()
            return self._json(200, {"versions": [dict(row) for row in rows]}, sid, new_cookie)
        if method == "GET":
            with db_connect() as db:
                row = db.execute("SELECT version, payload, updated_at FROM snapshots WHERE sid=? AND path=?", (sid, key)).fetchone()
            if row:
                result = {"version": row["version"], "workflow": json.loads(row["payload"]), "updatedAt": row["updated_at"], "source": "server"}
            else:
                result = {"version": 0, "workflow": json.loads(fixture.read_text()), "updatedAt": None, "source": "original"}
            return self._json(200, result, sid, new_cookie)
        if method != "PUT":
            return self._json(405, {"error": "허용되지 않는 메서드"}, sid, new_cookie)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BYTES:
                raise ValueError("저장 데이터 크기 초과")
            request = json.loads(self.rfile.read(size))
            version = request.get("expectedVersion")
            if not isinstance(version, int) or isinstance(version, bool) or version < 0:
                raise ValueError("버전 지정 누락")
            workflow = validate_workflow(request.get("workflow"))
            encoded = json.dumps(workflow, ensure_ascii=False, separators=(",", ":"))
            if len(encoded.encode()) > MAX_BYTES:
                raise ValueError("워크플로 저장 용량 초과")
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError, AttributeError) as e:
            return self._json(400, {"error": str(e)}, sid, new_cookie)
        now = datetime.now(timezone.utc).isoformat()
        with db_connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT version FROM snapshots WHERE sid=? AND path=?", (sid, key)).fetchone()
            current = int(row["version"]) if row else 0
            if current != version:
                db.rollback()
                return self._json(409, {"error": "다른 탭에서 먼저 저장했습니다. 다시 불러온 후 수정하세요.", "currentVersion": current}, sid, new_cookie)
            new_version = current + 1
            db.execute("""INSERT INTO snapshots(sid,path,version,payload,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(sid,path) DO UPDATE SET
                version=excluded.version,payload=excluded.payload,updated_at=excluded.updated_at""",
                (sid, key, new_version, encoded, now))
            db.execute("INSERT INTO revisions(sid,path,version,payload,created_at) VALUES(?,?,?,?,?)", (sid, key, new_version, encoded, now))
            db.execute("""DELETE FROM revisions WHERE sid=? AND path=? AND version NOT IN
                (SELECT version FROM revisions WHERE sid=? AND path=? ORDER BY version DESC LIMIT 30)""",
                (sid, key, sid, key))
            db.commit()
        return self._json(200, {"ok": True, "version": new_version, "updatedAt": now, "source": "server"}, sid, new_cookie)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            return self._send(200, b"ok", "text/plain")
        if path == "/api/studio/health":
            return self._json(200, {"status": "ok", "storage": "sqlite", "executionEnabled": False, "mode": "isolated-demo"})
        if path.startswith("/api/studio/workflows/"):
            return self._workflow_request("GET", path)
        if path.startswith("/api/"):
            return self._json(404, {"error": "존재하지 않는 API"})
        # No access outside the immutable pre-built UI assets.
        try:
            relative = unquote(path).lstrip("/") or "index.html"
            file = (ROOT / relative).resolve()
            if not file.is_relative_to(ROOT) or file.is_dir():
                return self._send(403, b"Forbidden", "text/plain")
            if not file.is_file():
                file = ROOT / "index.html"
            typ = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            return self._send(200, file.read_bytes(), typ)
        except OSError:
            return self._send(404, b"Not found", "text/plain")

    def do_HEAD(self):
        self.do_GET()

    def do_PUT(self):
        if self.headers.get("Origin"):
            try:
                origin = urlsplit(self.headers["Origin"])
                if origin.netloc != self.headers.get("Host") or origin.scheme not in ("https", "http"):
                    return self._json(403, {"error": "다른 출처의 저장 요청은 허용되지 않습니다"})
            except ValueError:
                return self._json(403, {"error": "출처 오류"})
        path = urlsplit(self.path).path
        if path.startswith("/api/studio/workflows/"):
            return self._workflow_request("PUT", path)
        return self._json(404, {"error": "지원하지 않는 요청"})

    def do_POST(self):
        return self._json(405, {"error": "외부 워크플로 실행이 비활성화되어 있습니다"})

if __name__ == "__main__":
    init_db()
    print(f"Shared Studio SQLite draft server listening on :{PORT}; executions DISABLED", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
