"""Project-neutral, SQLite-backed, versioned node input and execution drafts.

No arbitrary Python evaluation or outbound HTTP; code and URL are immutable
configuration drafts, reviewed/promoted by each project's approved runner.
"""
import json
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit

MAX_WORKSPACE_BYTES = 48_000
EXECUTION_DRAFT_FIELDS = {
    "kind", "http_method", "api_url", "python_module", "python_function",
    "python_code", "notes",
}
KIND = {"none", "http", "python", "n8n"}
METHOD = {"GET", "POST", "PUT", "PATCH", "DELETE"}

def init_workspace_db(conn: sqlite3.Connection):
    conn.execute("""CREATE TABLE IF NOT EXISTS node_workspaces (
        sid TEXT NOT NULL, workflow_path TEXT NOT NULL, node_id TEXT NOT NULL,
        revision INTEGER NOT NULL, input_json TEXT NOT NULL,
        execution_draft TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (sid,workflow_path,node_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS node_workspace_revisions (
        sid TEXT NOT NULL, workflow_path TEXT NOT NULL, node_id TEXT NOT NULL,
        revision INTEGER NOT NULL, input_json TEXT NOT NULL,
        execution_draft TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (sid,workflow_path,node_id,revision)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_node_workspace_audit
        ON node_workspace_revisions(sid,workflow_path,node_id,revision DESC)""")

def validate_workspace_input(value):
    if not isinstance(value, dict):
        raise ValueError("INPUT_JSON_OBJECT_REQUIRED")
    if len(json.dumps(value, ensure_ascii=False).encode()) > MAX_WORKSPACE_BYTES:
        raise ValueError("INPUT_TOO_LARGE")
    return value

def validate_execution_draft(value):
    if not isinstance(value, dict) or set(value) - EXECUTION_DRAFT_FIELDS:
        raise ValueError("INVALID_EXECUTION_DRAFT")
    kind = value.get("kind", "none")
    if kind not in KIND:
        raise ValueError("INVALID_EXECUTION_KIND")
    out = {"kind": kind}
    for field in EXECUTION_DRAFT_FIELDS - {"kind"}:
        v = value.get(field, "")
        if not isinstance(v, str):
            raise ValueError("NON_STRING_EXECUTION_FIELD: " + field)
        limit = 16000 if field == "python_code" else 5000 if field == "notes" else 2048
        if len(v) > limit:
            raise ValueError("EXECUTION_FIELD_TOO_LARGE: " + field)
        out[field] = v
    if kind == "http" and out["api_url"] and not out["api_url"].startswith("={{"):
        url = urlsplit(out["api_url"])
        if url.scheme not in ("https", "http") or not url.netloc or url.username or url.password:
            raise ValueError("INVALID_API_URL")
    if out["http_method"] and out["http_method"] not in METHOD:
        raise ValueError("INVALID_HTTP_METHOD")
    if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_WORKSPACE_BYTES:
        raise ValueError("EXECUTION_DRAFT_TOO_LARGE")
    return out

def get_workspace(db, sid, path, node_id):
    row = db.execute("""SELECT revision,input_json,execution_draft,updated_at
        FROM node_workspaces WHERE sid=? AND workflow_path=? AND node_id=?""",
        (sid,path,node_id)).fetchone()
    if not row:
        return {"revision":0,"input_json":{},"execution_draft":{"kind":"none"},
                "updated_at":None,"code_execution_approved":False}
    return {
        "revision":row["revision"],"input_json":json.loads(row["input_json"]),
        "execution_draft":json.loads(row["execution_draft"]),"updated_at":row["updated_at"],
        "code_execution_approved":False,
    }

def update_workspace(db, sid, path, node_id, expected_revision, input_json, execution_draft):
    if isinstance(expected_revision,bool) or not isinstance(expected_revision,int) or expected_revision<0:
        raise ValueError("EXPECTED_REVISION_REQUIRED")
    clean_input = validate_workspace_input(input_json)
    clean_draft = validate_execution_draft(execution_draft)
    in_text = json.dumps(clean_input,ensure_ascii=False,separators=(",",":"))
    ex_text = json.dumps(clean_draft,ensure_ascii=False,separators=(",",":"))
    now = datetime.now(timezone.utc).isoformat()
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT revision FROM node_workspaces WHERE sid=? AND workflow_path=? AND node_id=?",
                     (sid,path,node_id)).fetchone()
    current = int(row["revision"]) if row else 0
    if expected_revision != current:
        db.rollback()
        return None, current
    rev = current+1
    db.execute("""INSERT INTO node_workspaces(sid,workflow_path,node_id,revision,input_json,execution_draft,updated_at)
        VALUES(?,?,?,?,?,?,?) ON CONFLICT(sid,workflow_path,node_id) DO UPDATE SET
        revision=excluded.revision,input_json=excluded.input_json,execution_draft=excluded.execution_draft,
        updated_at=excluded.updated_at""",(sid,path,node_id,rev,in_text,ex_text,now))
    db.execute("""INSERT INTO node_workspace_revisions
        (sid,workflow_path,node_id,revision,input_json,execution_draft,updated_at)
        VALUES (?,?,?,?,?,?,?)""",(sid,path,node_id,rev,in_text,ex_text,now))
    db.commit()
    return {"revision":rev,"input_json":clean_input,"execution_draft":clean_draft,
            "updated_at":now,"code_execution_approved":False}, None

def list_workspace_revisions(db,sid,path,node_id):
    rows=db.execute("""SELECT revision,input_json,execution_draft,updated_at
       FROM node_workspace_revisions WHERE sid=? AND workflow_path=? AND node_id=?
       ORDER BY revision DESC LIMIT 50""",(sid,path,node_id)).fetchall()
    return [{"revision":r["revision"],"input_json":json.loads(r["input_json"]),
             "execution_draft":json.loads(r["execution_draft"]),"updated_at":r["updated_at"]}
            for r in rows]
