#!/usr/bin/env python3
"""Shared n8n Studio static UI + isolated SQLite draft service.

Pure stdlib. Project-registered allowlisted nodes only. No full workflows, trading or arbitrary code.
Each anonymous browser receives an unguessable HttpOnly cookie: its drafts are
server-stored, but cannot be accessed across devices without future auth.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import gzip
import inspect
import shutil
import tempfile
import time
from urllib.parse import parse_qs
import project_adapter_runtime as project_adapter
from node_run_store import (init_node_run_db,store_node_result,resolve_transfer,consume_transfer,
                            available_transfers,latest_graph_state)
from node_workspace_store import (init_workspace_db, get_workspace, update_workspace, list_workspace_revisions)
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Lock
from urllib.parse import unquote, urlsplit

ROOT = Path(os.environ.get("STUDIO_STATIC_ROOT", "/app/dist")).resolve()
WORKFLOW_DIR=os.environ.get("STUDIO_WORKFLOW_DIR","stock-workflows")
if WORKFLOW_DIR not in ("stock-workflows","procure-workflows"):
    raise RuntimeError("INVALID_STUDIO_WORKFLOW_DIR")
WORKFLOW_ROOT = (ROOT / WORKFLOW_DIR).resolve()
DB_PATH = Path(os.environ.get("STUDIO_DB_PATH", "/data/studio.sqlite3"))
PORT = int(os.environ.get("PORT", "3000"))
MAX_BYTES = 1_048_576
MAX_NODES = 350
SID = re.compile(r"^[a-f0-9]{48}$")
KEY = re.compile(r"^(operations|scenarios)/[a-zA-Z0-9_.-]+\.json$")
LOCK = Lock()

def archive_verified_old_sqlite_backup():
    """One-time space recovery, preserving the old backup as verified gzip.

    The LIVE database and immutable Pine/PG source are never touched.
    Explicitly scoped to the 2026-11-02 pre-Postgres backup; not a generic
    backup deletion or retention policy.
    """
    backup_dir=DB_PATH.parent/"investment-backups"
    source=backup_dir/"studio_before_investment_pg_20261102T154812Z.sqlite3"
    destination=backup_dir/(source.name+".gz")
    if not source.is_file():
        return
    if destination.exists():
        raise RuntimeError("BACKUP_DUPLICATE_ARCHIVE_REQUIRES_MANUAL_REVIEW")
    size=source.stat().st_size
    if size<10_000_000:
        raise RuntimeError("BACKUP_SIZE_UNEXPECTED_STOP_FOR_MANUAL_REVIEW")
    with tempfile.TemporaryDirectory(prefix="investment-backup-archive-") as tmp:
        temporary=Path(tmp)/destination.name
        source_sha=hashlib.sha256()
        length=0
        with open(source,"rb") as reader,gzip.open(temporary,"wb",compresslevel=6) as writer:
            while True:
                data=reader.read(1024*1024)
                if not data:break
                length+=len(data)
                source_sha.update(data)
                writer.write(data)
        verified=hashlib.sha256()
        inflated=0
        with gzip.open(temporary,"rb") as reader:
            while True:
                data=reader.read(1024*1024)
                if not data:break
                inflated+=len(data)
                verified.update(data)
        if inflated!=length or source_sha.hexdigest()!=verified.hexdigest():
            raise RuntimeError("BACKUP_COMPRESSED_SHA256_VERIFICATION_FAILED")
        archived_bytes=temporary.stat().st_size
        if archived_bytes>=size:
            raise RuntimeError("BACKUP_NOT_COMPRESSIBLE_ABORT_WITHOUT_CHANGES")
        # Only after the ephemeral gzip was fully verified can the redundant
        # old snapshot be replaced. The live SQLite is left unchanged.
        print("STUDIO_BACKUP_VERIFIED_IN_TEMP",source.name,
              "original_bytes",size,"compressed_bytes",archived_bytes,
              "sha256",source_sha.hexdigest(),flush=True)
        source.unlink()
        staged=destination.with_name(destination.name+".partial")
        try:
            with open(temporary,"rb") as reader,open(staged,"wb") as writer:
                shutil.copyfileobj(reader,writer,length=1024*1024)
                writer.flush()
                os.fsync(writer.fileno())
            final_sha=hashlib.sha256()
            final_size=0
            with gzip.open(staged,"rb") as reader:
                while True:
                    data=reader.read(1024*1024)
                    if not data:break
                    final_sha.update(data)
                    final_size+=len(data)
            if final_size!=length or final_sha.hexdigest()!=source_sha.hexdigest():
                raise RuntimeError("PERSISTED_BACKUP_ARCHIVE_VERIFICATION_FAILED")
            os.replace(staged,destination)
        finally:
            if staged.exists():staged.unlink()
        print("STUDIO_BACKUP_ARCHIVED_VERIFIED",destination.name,
              "original_bytes",size,"compressed_bytes",destination.stat().st_size,
              "sha256",source_sha.hexdigest(),flush=True)


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
        db.execute("""CREATE TABLE IF NOT EXISTS node01_executions (
            sid TEXT NOT NULL, run_id TEXT PRIMARY KEY, workflow_path TEXT NOT NULL,
            node_id TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
            input_json TEXT NOT NULL, output_json TEXT, error TEXT,
            python_module TEXT NOT NULL, python_function TEXT NOT NULL,
            code_version TEXT NOT NULL, code_sha256 TEXT NOT NULL,
            duration_ms REAL NOT NULL, created_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_node01_recent ON node01_executions(sid, workflow_path, node_id, created_at DESC)")
        init_workspace_db(db)
        init_node_run_db(db)

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

def project_database_trace(workflow,workflow_run_id,node_id,node_name,state,output,error=None):
    module=project_adapter.adapter()
    if not module or not hasattr(module,"record_node_execution"):
        return {"status":"NOT_CONFIGURED"}
    try:
        return module.record_node_execution(workflow,workflow_run_id,node_id,node_name,
                                            state,output,error)
    except Exception as exc:
        print("INVESTMENT_POSTGRES_NODE_TRACE_FAILED",
              workflow,node_id,type(exc).__name__,str(exc)[:180],flush=True)
        return {"status":"FAILED","error":type(exc).__name__+": "+str(exc)[:160]}


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
        revision_match = re.fullmatch(r"(.+)/versions/([1-9][0-9]*)", tail)
        key = revision_match.group(1) if revision_match else tail[:-len("/versions")] if is_versions else tail
        try:
            fixture = fixture_path(key)
        except ValueError as e:
            return self._json(404, {"error": str(e)}, sid, new_cookie)
        if revision_match:
            if method != "GET":
                return self._json(405, {"error": "허용되지 않는 메서드"}, sid, new_cookie)
            rev = int(revision_match.group(2))
            with db_connect() as db:
                row = db.execute("SELECT payload, created_at FROM revisions WHERE sid=? AND path=? AND version=?", (sid, key, rev)).fetchone()
            if not row:
                return self._json(404, {"error": "버전 기록이 없습니다"}, sid, new_cookie)
            return self._json(200, {"version": rev, "workflow": json.loads(row["payload"]), "createdAt": row["created_at"]}, sid, new_cookie)
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

    def _node_workspace(self, method, history=False):
        sid,new_cookie=self._sid()
        if method=="PUT" and self.headers.get("Origin"):
            try:
                origin=urlsplit(self.headers["Origin"])
                if origin.netloc!=self.headers.get("Host") or origin.scheme not in ("http","https"):
                    return self._json(403,{"error":"CROSS_ORIGIN_FORBIDDEN"},sid,new_cookie)
            except ValueError:
                return self._json(403,{"error":"INVALID_ORIGIN"},sid,new_cookie)
        try:
            if method=="PUT":
                if not self.headers.get("Content-Type","").startswith("application/json"):
                    return self._json(415,{"error":"JSON_CONTENT_TYPE_REQUIRED"},sid,new_cookie)
                size=int(self.headers.get("Content-Length","0"))
                if size<2 or size>65_536:
                    return self._json(413,{"error":"NODE_CONFIG_TOO_LARGE"},sid,new_cookie)
                req=json.loads(self.rfile.read(size))
            else:
                query=parse_qs(urlsplit(self.path).query)
                req={k:v[0] for k,v in query.items() if v}
            if not isinstance(req,dict):
                raise ValueError("REQUEST_OBJECT_REQUIRED")
            path,node_id=req.get("workflow"),req.get("node_id")
            if not isinstance(path,str) or not isinstance(node_id,str):
                raise ValueError("WORKFLOW_AND_NODE_REQUIRED")
            fixture=fixture_path(path)
            with db_connect() as db:
                saved=db.execute("SELECT payload FROM snapshots WHERE sid=? AND path=?",(sid,path)).fetchone()
            workflow=json.loads(saved["payload"]) if saved else json.loads(fixture.read_text())
            if not any(node.get("id")==node_id for node in workflow.get("nodes",[])):
                return self._json(404,{"error":"NODE_NOT_IN_WORKFLOW"},sid,new_cookie)
            if method=="GET":
                with db_connect() as db:
                    result=list_workspace_revisions(db,sid,path,node_id) if history else get_workspace(db,sid,path,node_id)
                return self._json(200,{"workflow":path,"node_id":node_id,
                    **({"revisions":result} if history else {"workspace":result})},sid,new_cookie)
            with db_connect() as db:
                saved,conflict=update_workspace(db,sid,path,node_id,
                    req.get("expected_revision"),req.get("input_json"),req.get("execution_draft"))
            if conflict is not None:
                return self._json(409,{"error":"NODE_WORKSPACE_REVISION_CONFLICT",
                                       "current_revision":conflict},sid,new_cookie)
            return self._json(200,{"workflow":path,"node_id":node_id,"workspace":saved},sid,new_cookie)
        except (ValueError,TypeError,json.JSONDecodeError) as error:
            return self._json(400,{"error":str(error)},sid,new_cookie)

    def _node01_run(self):
        sid, new_cookie = self._sid()
        if self.headers.get("Origin"):
            origin = urlsplit(self.headers["Origin"])
            if origin.netloc != self.headers.get("Host") or origin.scheme not in ("https", "http"):
                return self._json(403, {"error": "CROSS_ORIGIN_FORBIDDEN"}, sid, new_cookie)
        if self.headers.get("X-Studio-Node-Run") != "N01":
            return self._json(403, {"error": "EXPLICIT_N01_ACTION_REQUIRED"}, sid, new_cookie)
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            return self._json(415, {"error": "JSON_CONTENT_TYPE_REQUIRED"}, sid, new_cookie)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 600_000:
                raise ValueError("INPUT_SIZE_INVALID")
            req = json.loads(self.rfile.read(size))
            if not isinstance(req, dict):
                raise ValueError("REQUEST_OBJECT_REQUIRED")
            path, node_id, data = req.get("workflow"), req.get("node_id"), req.get("input_json")
            if size > project_adapter.root_input_limit(path,node_id):
                raise ValueError("INPUT_SIZE_INVALID_FOR_REGISTERED_NODE")
            kind = project_adapter.kind_for(path)
            binding = project_adapter.binding_for(path,node_id)
            if not kind or not binding or binding.get("node_character")!="manual_collection_start":
                return self._json(403, {"error": "ONLY_WF01_N01_IS_EXECUTABLE"}, sid, new_cookie)
            file = fixture_path(path)
            with db_connect() as db:
                row = db.execute("SELECT payload FROM snapshots WHERE sid=? AND path=?", (sid, path)).fetchone()
            workflow = json.loads(row["payload"]) if row else json.loads(file.read_text())
            if not project_adapter.check_node(workflow,path,node_id):
                return self._json(409, {"error": "N01_CODE_BINDING_INVALID_OR_NOT_SAVED"}, sid, new_cookie)
            if not isinstance(data, dict):
                raise ValueError("INPUT_JSON_OBJECT_REQUIRED")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return self._json(400, {"error": str(exc)}, sid, new_cookie)
        code_sha = hashlib.sha256(inspect.getsource(
            getattr(project_adapter.adapter(),binding["python_function"])).encode("utf-8")).hexdigest()
        started = time.perf_counter()
        out, err, state = None, None, "SUCCESS"
        try:
            out = project_adapter.execute_registered(path,node_id,data)
        except (ValueError, TypeError) as exc:
            err, state = str(exc), "FAILED"
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        run_id, now = secrets.token_hex(16), datetime.now(timezone.utc).isoformat()
        with db_connect() as db:
            workspace=get_workspace(db,sid,path,node_id)
            db.execute("""INSERT INTO node01_executions (
                sid, run_id, workflow_path, node_id, kind, status, input_json, output_json,
                error, python_module, python_function, code_version, code_sha256,
                duration_ms, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, run_id, path, node_id, kind, state,
                 json.dumps(data, ensure_ascii=False), json.dumps(out, ensure_ascii=False) if out else None,
                 err, binding["python_module"], binding["python_function"],
                 binding["code_version"], code_sha, duration_ms, now))
            transfers=store_node_result(db,sid=sid,path=path,workflow=workflow,
                run_id=run_id,workflow_run_id=run_id,node_id=node_id,input_json=data,
                output_json=out,input_revision=workspace["revision"],
                code_ref=binding["python_module"]+"."+binding["python_function"],
                code_sha256=code_sha,error=err,duration_ms=duration_ms,status=state)
            db.execute("""DELETE FROM node01_executions WHERE sid=? AND workflow_path=?
                AND run_id NOT IN (SELECT run_id FROM node01_executions
                WHERE sid=? AND workflow_path=? ORDER BY created_at DESC LIMIT 80)""",
                (sid, path, sid, path))
        postgres_trace=project_database_trace(path,run_id,node_id,
            next((n["name"] for n in workflow["nodes"] if n["id"]==node_id),node_id),
            state,out,err)
        response = {
            "postgres_trace":postgres_trace,
            "run_id": run_id, "workflow": path, "node_id": node_id,
            "status": state, "input_json": data, "output_json": out, "error": err,
            "python_module": binding["python_module"],
            "python_function": binding["python_function"],
            "code_version": binding["code_version"], "code_sha256": code_sha,
            "duration_ms": duration_ms, "executed_at": now,
            "engine": "python", "tradingview_called": False, "n8n_workflow_started": False,
            "persistence": "sqlite", "prepared_transfers": transfers, "workflow_run_id": run_id
        }
        return self._json(200 if state == "SUCCESS" else 422, response, sid, new_cookie)

    def _node01_history(self):
        sid, new_cookie = self._sid()
        query = parse_qs(urlsplit(self.path).query)
        path, node_id = (query.get("workflow") or [None])[0], (query.get("node_id") or [None])[0]
        kind = project_adapter.kind_for(path)
        binding = project_adapter.binding_for(path,node_id)
        if not kind or not binding or binding.get("node_character")!="manual_collection_start":
            return self._json(403, {"error": "ONLY_WF01_N01_IS_EXECUTABLE"}, sid, new_cookie)
        with db_connect() as db:
            records = db.execute("""SELECT run_id, status, input_json, output_json, error,
                python_module, python_function, code_version, code_sha256, duration_ms, created_at
                FROM node01_executions WHERE sid=? AND workflow_path=? AND node_id=?
                ORDER BY created_at DESC LIMIT 8""", (sid, path, node_id)).fetchall()
        rows = []
        for x in records:
            item = dict(x)
            item["input_json"] = json.loads(item["input_json"])
            item["output_json"] = json.loads(item["output_json"]) if item["output_json"] else None
            rows.append(item)
        return self._json(200, {"node_id": node_id, "workflow": path, "executions": rows}, sid, new_cookie)

    def _node_history_api(self):
        sid,new_cookie=self._sid()
        q=parse_qs(urlsplit(self.path).query)
        path=(q.get("workflow") or [None])[0]
        node_id=(q.get("node_id") or [None])[0]
        try:
            file=fixture_path(path)
            with db_connect() as db:
                stored=db.execute("SELECT payload FROM snapshots WHERE sid=? AND path=?",(sid,path)).fetchone()
                workflow=json.loads(stored["payload"]) if stored else json.loads(file.read_text())
                if not any(n.get("id")==node_id for n in workflow["nodes"]):
                    return self._json(404,{"error":"NODE_NOT_IN_WORKFLOW"},sid,new_cookie)
                rows=db.execute("""SELECT run_id,workflow_run_id,node_id,status,input_json,
                    output_json,upstream_run_id,input_revision,code_ref,code_sha256,
                    error,duration_ms,created_at FROM node_runs WHERE
                    sid=? AND workflow_path=? AND node_id=?
                    ORDER BY created_at DESC LIMIT 20""",(sid,path,node_id)).fetchall()
                result=[]
                for r in rows:
                    data=dict(r)
                    data["input_json"]=json.loads(data["input_json"])
                    data["output_json"]=json.loads(data["output_json"]) if data["output_json"] else None
                    data["code_version"]=data["code_ref"]
                    result.append(data)
            return self._json(200,{"node_id":node_id,"workflow":path,"executions":result},sid,new_cookie)
        except (ValueError,TypeError) as exc:
            return self._json(400,{"error":str(exc)},sid,new_cookie)

    def _node_graph_api(self, mode):
        sid,new_cookie=self._sid()
        query=parse_qs(urlsplit(self.path).query)
        path=(query.get("workflow") or [None])[0]
        node_id=(query.get("node_id") or [None])[0]
        try:
            fixture_path(path)
            with db_connect() as db:
                if mode=="state":
                    data=latest_graph_state(db,sid,path)
                elif mode=="transfers":
                    workflow=json.loads(fixture_path(path).read_text())
                    if not any(n.get("id")==node_id for n in workflow["nodes"]):
                        return self._json(404,{"error":"NODE_NOT_IN_WORKFLOW"},sid,new_cookie)
                    data={"transfers":available_transfers(db,sid,path,node_id)}
                else:
                    raise ValueError("INVALID_NODE_GRAPH_MODE")
            return self._json(200,{"workflow":path,**data},sid,new_cookie)
        except (ValueError,TypeError) as exc:
            return self._json(400,{"error":str(exc)},sid,new_cookie)

    def _registered_node_run(self):
        sid,new_cookie=self._sid()
        if self.headers.get("X-Studio-Node-Run")!="APPROVED":
            return self._json(403,{"error":"EXPLICIT_APPROVED_ACTION_REQUIRED"},sid,new_cookie)
        if not self.headers.get("Content-Type","").startswith("application/json"):
            return self._json(415,{"error":"JSON_CONTENT_TYPE_REQUIRED"},sid,new_cookie)
        if self.headers.get("Origin"):
            origin=urlsplit(self.headers["Origin"])
            if origin.netloc!=self.headers.get("Host") or origin.scheme not in ("http","https"):
                return self._json(403,{"error":"CROSS_ORIGIN_FORBIDDEN"},sid,new_cookie)
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 2<=size<=2048:raise ValueError("REQUEST_SIZE_INVALID")
            req=json.loads(self.rfile.read(size))
            path,node_id,source_run_id=req.get("workflow"),req.get("node_id"),req.get("source_run_id")
            file=fixture_path(path)
            with db_connect() as db:
                stored=db.execute("SELECT payload FROM snapshots WHERE sid=? AND path=?",(sid,path)).fetchone()
                workflow=json.loads(stored["payload"]) if stored else json.loads(file.read_text())
            binding=project_adapter.check_node(workflow,path,node_id)
            if not binding or binding.get("node_character")=="manual_collection_start":
                return self._json(403,{"error":"PROJECT_NODE_NOT_APPROVED"},sid,new_cookie)
            with db_connect() as db:
                transfer=resolve_transfer(db,sid=sid,path=path,workflow=workflow,
                    target_node_id=node_id,source_run_id=source_run_id)
                workspace=get_workspace(db,sid,path,node_id)
            incoming=transfer["output_json"]
            override=workspace["input_json"] if workspace["revision"] else {}
            if not isinstance(incoming,dict) or not isinstance(override,dict):
                raise ValueError("NODE_INPUT_OBJECT_REQUIRED")
            # Never mutate provenance: original upstream JSON is persisted unchanged
            # in edge_transfers. The merged effective_input becomes the run input.
            effective_input={**incoming,**override}
            module=project_adapter.adapter()
            code_sha=hashlib.sha256(inspect.getsource(
                getattr(module,binding["python_function"])).encode("utf-8")).hexdigest()
        except (ValueError,KeyError,TypeError,AttributeError) as exc:
            return self._json(400,{"error":str(exc)},sid,new_cookie)
        start=time.perf_counter()
        state,error,output="SUCCESS",None,None
        try:
            output=project_adapter.execute_registered(path,node_id,effective_input)
            if binding.get("node_character")=="conditional_route":
                if not isinstance(output,dict) or "_studio_active_ports" not in output:
                    raise ValueError("CONDITIONAL_ACTIVE_PORTS_REQUIRED")
        except (ValueError,TypeError) as exc:
            state,error="FAILED",str(exc)
        duration=round((time.perf_counter()-start)*1000,3)
        run_id,now=secrets.token_hex(16),datetime.now(timezone.utc).isoformat()
        with db_connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Check the selected transfer has not been consumed by another run.
            if state=="SUCCESS":
                ready=db.execute("SELECT status FROM edge_transfers WHERE transfer_id=? AND sid=?",
                  (transfer["transfer_id"],sid)).fetchone()
                if not ready or ready["status"]!="READY":
                    db.rollback()
                    return self._json(409,{"error":"TRANSFER_ALREADY_CONSUMED"},sid,new_cookie)
            targets=store_node_result(db,sid=sid,path=path,workflow=workflow,
                run_id=run_id,workflow_run_id=transfer["workflow_run_id"],
                node_id=node_id,input_json=effective_input,output_json=output,
                upstream_run_id=source_run_id,input_revision=workspace["revision"],
                code_ref=binding["python_module"]+"."+binding["python_function"],
                code_sha256=code_sha,error=error,duration_ms=duration,status=state,
                active_source_ports=(output.get("_studio_active_ports")
                    if state=="SUCCESS" and binding.get("node_character")=="conditional_route"
                    else None))
            if state=="SUCCESS":
                consume_transfer(db,transfer["transfer_id"],run_id)
            db.commit()
        postgres_trace=project_database_trace(path,transfer["workflow_run_id"],node_id,
            next((n["name"] for n in workflow["nodes"] if n["id"]==node_id),node_id),
            state,output,error)
        return self._json(200 if state=="SUCCESS" else 422,{
            "postgres_trace":postgres_trace,
            "run_id":run_id,"workflow_run_id":transfer["workflow_run_id"],
            "workflow":path,"node_id":node_id,"status":state,
            "input_json":effective_input,"upstream_output_json":incoming,
            "upstream_run_id":source_run_id,"input_revision":workspace["revision"],
            "output_json":output,"error":error,"duration_ms":duration,
            "python_module":binding["python_module"],
            "python_function":binding["python_function"],
            "code_version":binding["code_version"],"code_sha256":code_sha,
            "prepared_transfers":targets,"executed_at":now,
            "persistence":"sqlite","tradingview_called":False,
            "next_node_executed":False},sid,new_cookie)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            return self._send(200, b"ok", "text/plain")
        if path == "/api/investment/storage/status":
            sid,new_cookie=self._sid()
            try:
                v=os.statvfs(DB_PATH.parent)
                files=[]
                for f in DB_PATH.parent.iterdir():
                    if f.is_file():
                        files.append({"kind":"sqlite" if f.suffix in (".db",".sqlite3") else "other",
                                      "name":f.name,"bytes":f.stat().st_size})
                with sqlite3.connect("file:"+str(DB_PATH)+"?mode=ro",uri=True,timeout=8) as db:
                    db.row_factory=sqlite3.Row
                    counts={}
                    for table,col in (("node_runs","length(input_json)+length(coalesce(output_json,''))"),
                                     ("edge_transfers","length(output_json)"),
                                     ("investment_pipeline_events","length(payload_json)"),
                                     ("investment_pine_payloads","length(pine_code)")):
                        try:
                            row=db.execute("SELECT count(*),coalesce(sum("+col+"),0) FROM "+table).fetchone()
                            counts[table]={"rows":row[0],"estimated_payload_bytes":row[1]}
                        except sqlite3.Error as exc:
                            counts[table]={"error":type(exc).__name__}
                    pages=db.execute("PRAGMA page_count").fetchone()[0]
                    free_pages=db.execute("PRAGMA freelist_count").fetchone()[0]
                directories=[]
                for folder in DB_PATH.parent.iterdir():
                    if folder.is_dir():
                        total=0;count=0;largest=[]
                        for root, dirs, filenames in os.walk(folder):
                            if count>10000:break
                            for filename in filenames:
                                count+=1
                                try:
                                    fp=Path(root)/filename
                                    size=fp.stat().st_size
                                    total+=size
                                    if size>2_000_000:
                                        largest.append({"name":str(fp.relative_to(DB_PATH.parent)),"bytes":size})
                                except OSError:
                                    pass
                        directories.append({"name":folder.name,"total_bytes":total,
                                            "file_count":count,
                                            "large_files":sorted(largest,key=lambda x:-x["bytes"])[:10]})
                return self._json(200,{
                    "status":"ok","volume_bytes":v.f_blocks*v.f_frsize,
                    "free_bytes":v.f_bavail*v.f_frsize,
                    "sqlite_page_count":pages,"sqlite_free_pages":free_pages,
                    "files":sorted(files,key=lambda f:f["bytes"],reverse=True)[:20],
                    "directories":sorted(directories,key=lambda x:-x["total_bytes"])[:16],
                    "tables":counts},sid,new_cookie)
            except Exception as exc:
                return self._json(503,{"error":type(exc).__name__+": "+str(exc)[:100]},sid,new_cookie)
        if path == "/api/investment/session":
            sid,new_cookie=self._sid()
            # Establish one stable HttpOnly same-origin session before the
            # browser fans out parallel API requests for workflows and traces.
            return self._json(200,{"status":"READY","session_initialized":True},sid,new_cookie)
        if path == "/api/investment/database/status":
            sid,new_cookie=self._sid()
            module=project_adapter.adapter()
            if not module or not hasattr(module,"investment_database_status"):
                return self._json(404,{"status":"NOT_CONFIGURED"},sid,new_cookie)
            return self._json(200,module.investment_database_status(),sid,new_cookie)
        if path == "/api/investment/source-exact":
            sid,new_cookie=self._sid()
            args=parse_qs(urlsplit(self.path).query)
            requested=(args.get("source_id") or [""])[0]
            version=(args.get("version_key") or [""])[0]
            sha=(args.get("source_sha256") or [""])[0]
            if not re.fullmatch(r"[0-9a-f]{64}",sha):
                return self._json(400,{"error":"EXACT_SOURCE_SHA256_REQUIRED"},sid,new_cookie)
            module=project_adapter.adapter()
            if not module or not hasattr(module,"pipeline_exact_source"):
                return self._json(404,{"error":"EXACT_SOURCE_REGISTRY_MISSING"},sid,new_cookie)
            try:
                entry=module.pipeline_exact_source(requested,version)
            except ValueError as exc:
                return self._json(422,{"error":str(exc)},sid,new_cookie)
            if entry.get("source_sha256")!=sha:
                return self._json(409,{"error":"PINNED_SOURCE_SHA256_MISMATCH"},sid,new_cookie)
            return self._json(200,entry,sid,new_cookie)
        if path == "/api/investment/sources":
            sid,new_cookie=self._sid()
            module=project_adapter.adapter()
            if not module or not hasattr(module,"pipeline_sources"):
                return self._json(404,{"error":"SOURCE_REGISTRY_NOT_AVAILABLE"},sid,new_cookie)
            return self._json(200,module.pipeline_sources(),sid,new_cookie)
        if path == "/api/investment/pipeline":
            sid,new_cookie=self._sid()
            module=project_adapter.adapter()
            if not module or not hasattr(module,"pipeline_read"):
                return self._json(404,{"error":"PIPELINE_NOT_AVAILABLE"},sid,new_cookie)
            return self._json(200,module.pipeline_read(sid),sid,new_cookie)
        if path.startswith("/api/investment/pipeline/"):
            sid,new_cookie=self._sid()
            module=project_adapter.adapter()
            run_id=path.rsplit("/",1)[-1]
            if not re.fullmatch(r"[0-9a-f]{32}",run_id):
                return self._json(400,{"error":"INVALID_RUN_ID"},sid,new_cookie)
            if not module or not hasattr(module,"pipeline_read"):
                return self._json(404,{"error":"PIPELINE_NOT_AVAILABLE"},sid,new_cookie)
            return self._json(200,module.pipeline_read(sid,run_id),sid,new_cookie)
        if path == "/api/studio/health":
            return self._json(200, {"status": "ok", "storage": "sqlite", "executionEnabled": False, "node01ExecutionEnabled": True, "nodeWorkspaceVersioned": True, "nodeUiControlsRelease": "shared-procurement-three-market-v1" if WORKFLOW_DIR=="procure-workflows" else "shared-workflow-final-result-v1", "nodeEdgeTransferEnabled": True, "projectAdapterConnected": project_adapter.adapter() is not None, "mode": "isolated-demo"})
        if path == "/api/studio/nodes/workspace":
            return self._node_workspace("GET")
        if path == "/api/studio/nodes/workspace/revisions":
            return self._node_workspace("GET",history=True)
        if path == "/api/studio/nodes/history":
            return self._node_history_api()
        if path == "/api/studio/nodes/graph-state":
            return self._node_graph_api("state")
        if path == "/api/studio/nodes/transfers":
            return self._node_graph_api("transfers")
        if path == "/api/studio/node01/executions":
            return self._node01_history()
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
        if path == "/api/studio/nodes/workspace":
            return self._node_workspace("PUT")
        if path.startswith("/api/studio/workflows/"):
            return self._workflow_request("PUT", path)
        return self._json(404, {"error": "지원하지 않는 요청"})

    def do_POST(self):
        if urlsplit(self.path).path == "/api/investment/pipeline":
            sid,new_cookie=self._sid()
            module=project_adapter.adapter()
            if not module or not hasattr(module,"pipeline_start"):
                return self._json(404,{"error":"PIPELINE_NOT_AVAILABLE"},sid,new_cookie)
            if not self.headers.get("Content-Type","").startswith("application/json"):
                return self._json(415,{"error":"JSON_REQUIRED"},sid,new_cookie)
            origin=self.headers.get("Origin")
            if origin and (urlsplit(origin).netloc!=self.headers.get("Host")
                           or urlsplit(origin).scheme not in ("http","https")):
                return self._json(403,{"error":"CROSS_ORIGIN_FORBIDDEN"},sid,new_cookie)
            try:
                size=int(self.headers.get("Content-Length","0"))
                if not 2<=size<=2048:
                    raise ValueError("PIPELINE_START_BODY_TOO_LARGE")
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict) or set(payload)-{"source_id","version_key"}:
                    raise ValueError("ONLY_EXACT_DB_SOURCE_SELECTION_ALLOWED")
                if payload and set(payload)!={"source_id","version_key"}:
                    raise ValueError("SOURCE_AND_VERSION_REQUIRED_TOGETHER")
                result=module.pipeline_start(sid,payload or None)
            except (ValueError,TypeError,json.JSONDecodeError) as exc:
                return self._json(409,{"error":str(exc)},sid,new_cookie)
            return self._json(202,result,sid,new_cookie)
        if urlsplit(self.path).path == "/api/studio/nodes/execute":
            return self._registered_node_run()
        if urlsplit(self.path).path == "/api/studio/node01/execute":
            return self._node01_run()
        return self._json(405, {"error": "워크플로 실행 비활성화 · WF01 N01 단독 실행만 지원"})

if __name__ == "__main__":
    if WORKFLOW_DIR=="stock-workflows":
        archive_verified_old_sqlite_backup()
    init_db()
    print(f"Shared Studio SQLite draft server listening on :{PORT}; full-workflow executions DISABLED; project-approved per-node execution only; workflow_dir={WORKFLOW_DIR}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
