"""Project-neutral persistence and exact edge transfer of successful node output.

The graph definition is the authority; the UI is never trusted for connection
validation. A transfer only becomes READY after its source run succeeds.
"""
import json
import sqlite3
from datetime import datetime, timezone

def init_node_run_db(db: sqlite3.Connection):
    db.execute("""CREATE TABLE IF NOT EXISTS node_runs (
      sid TEXT NOT NULL, run_id TEXT PRIMARY KEY, workflow_path TEXT NOT NULL,
      workflow_run_id TEXT NOT NULL, node_id TEXT NOT NULL, status TEXT NOT NULL,
      input_json TEXT NOT NULL, output_json TEXT, upstream_run_id TEXT,
      input_revision INTEGER NOT NULL, code_ref TEXT NOT NULL, code_sha256 TEXT NOT NULL,
      error TEXT, duration_ms REAL NOT NULL, created_at TEXT NOT NULL
    )""")
    db.execute("""CREATE INDEX IF NOT EXISTS idx_node_runs_lookup ON
      node_runs(sid,workflow_path,node_id,created_at DESC)""")
    db.execute("""CREATE TABLE IF NOT EXISTS edge_transfers (
      sid TEXT NOT NULL, transfer_id TEXT PRIMARY KEY, workflow_path TEXT NOT NULL,
      workflow_run_id TEXT NOT NULL, edge_key TEXT NOT NULL,
      source_node_id TEXT NOT NULL, source_run_id TEXT NOT NULL,
      target_node_id TEXT NOT NULL, source_port INTEGER NOT NULL,
      target_port INTEGER NOT NULL, output_json TEXT NOT NULL,
      status TEXT NOT NULL, consumed_by_run_id TEXT, created_at TEXT NOT NULL,
      UNIQUE(sid,source_run_id,edge_key)
    )""")
    db.execute("""CREATE INDEX IF NOT EXISTS idx_edge_ready ON
      edge_transfers(sid,workflow_path,target_node_id,created_at DESC)""")

def graph_targets(workflow, node_id):
    nodes = workflow["nodes"]
    by_id = {n["id"]:n for n in nodes}
    by_name={n["name"]:n for n in nodes}
    node=by_id.get(node_id)
    if not node: raise ValueError("NODE_NOT_IN_WORKFLOW")
    out=[]
    for kind, port_lists in workflow.get("connections",{}).get(node["name"],{}).items():
        for source_port,targets in enumerate(port_lists):
            for idx,target in enumerate(targets):
                other=by_name.get(target["node"])
                if not other:raise ValueError("INVALID_GRAPH_TARGET")
                target_port=target.get("index",0)
                out.append({
                    "edge_key": f"{node_id}:{kind}:{source_port}:{idx}:{other['id']}:{target_port}",
                    "source_node_id":node_id,"target_node_id":other["id"],
                    "source_port":source_port,"target_port":target_port,
                })
    return out

def store_node_result(db, *, sid, path, workflow, run_id, workflow_run_id,
                      node_id, input_json, output_json, upstream_run_id=None,
                      input_revision=0, code_ref="", code_sha256="", error=None,
                      duration_ms=0, status="SUCCESS"):
    if status=="SUCCESS" and not isinstance(output_json,dict):
        raise ValueError("NODE_OUTPUT_MUST_BE_OBJECT")
    now=datetime.now(timezone.utc).isoformat()
    db.execute("""INSERT INTO node_runs(sid,run_id,workflow_path,workflow_run_id,node_id,
      status,input_json,output_json,upstream_run_id,input_revision,code_ref,code_sha256,
      error,duration_ms,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (sid,run_id,path,workflow_run_id,node_id,status,
       json.dumps(input_json,ensure_ascii=False),
       json.dumps(output_json,ensure_ascii=False) if output_json is not None else None,
       upstream_run_id,input_revision,code_ref,code_sha256,error,duration_ms,now))
    transfers=[]
    if status=="SUCCESS":
        import secrets
        for edge in graph_targets(workflow,node_id):
            transfer_id=secrets.token_hex(16)
            db.execute("""INSERT INTO edge_transfers(sid,transfer_id,workflow_path,
              workflow_run_id,edge_key,source_node_id,source_run_id,target_node_id,
              source_port,target_port,output_json,status,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (sid,transfer_id,path,workflow_run_id,edge["edge_key"],
               node_id,run_id,edge["target_node_id"],edge["source_port"],
               edge["target_port"],json.dumps(output_json,ensure_ascii=False),
               "READY",now))
            transfers.append({**edge,"transfer_id":transfer_id,"status":"READY"})
    return transfers

def available_transfers(db,sid,path,target_node_id):
    rows=db.execute("""SELECT transfer_id,workflow_run_id,source_node_id,
       source_run_id,target_node_id,source_port,target_port,output_json,status,
       created_at FROM edge_transfers
       WHERE sid=? AND workflow_path=? AND target_node_id=? ORDER BY created_at DESC LIMIT 20""",
       (sid,path,target_node_id)).fetchall()
    return [{**dict(r),"output_json":json.loads(r["output_json"])} for r in rows]

def resolve_transfer(db, *, sid,path,workflow,target_node_id,source_run_id):
    if not source_run_id or not isinstance(source_run_id,str):
        raise ValueError("UPSTREAM_RUN_ID_REQUIRED")
    row=db.execute("""SELECT * FROM edge_transfers
       WHERE sid=? AND workflow_path=? AND target_node_id=?
         AND source_run_id=? AND status='READY'""",
         (sid,path,target_node_id,source_run_id)).fetchone()
    if not row:raise ValueError("CONNECTED_UPSTREAM_RUN_NOT_READY")
    parent=db.execute("""SELECT * FROM node_runs WHERE
       sid=? AND workflow_path=? AND run_id=? AND status='SUCCESS'""",
       (sid,path,source_run_id)).fetchone()
    if not parent:raise ValueError("UPSTREAM_NOT_SUCCESSFUL")
    legal={e["edge_key"] for e in graph_targets(workflow,parent["node_id"])
           if e["target_node_id"]==target_node_id}
    if row["edge_key"] not in legal:raise ValueError("GRAPH_CONNECTION_CHANGED")
    return {"transfer_id":row["transfer_id"],
       "workflow_run_id":row["workflow_run_id"],
       "source_node_id":row["source_node_id"],
       "source_run_id":source_run_id,
       "target_node_id":target_node_id,
       "output_json":json.loads(row["output_json"])}

def consume_transfer(db,transfer_id,target_run_id):
    updated=db.execute("""UPDATE edge_transfers SET status='CONSUMED',
      consumed_by_run_id=? WHERE transfer_id=? AND status='READY'""",
      (target_run_id,transfer_id))
    if updated.rowcount!=1:raise ValueError("TRANSFER_ALREADY_CONSUMED")

def latest_graph_state(db,sid,path):
    rows=db.execute("""SELECT node_id,run_id,status,output_json,duration_ms,created_at
       FROM node_runs WHERE sid=? AND workflow_path=? ORDER BY created_at DESC LIMIT 150""",
       (sid,path)).fetchall()
    latest={}
    for r in rows:
        if r["node_id"] not in latest:
            latest[r["node_id"]]={"node_id":r["node_id"],"run_id":r["run_id"],
               "status":r["status"],"duration_ms":r["duration_ms"],"created_at":r["created_at"]}
    edges=db.execute("""SELECT edge_key,source_node_id,source_run_id,target_node_id,
       status,consumed_by_run_id,created_at FROM edge_transfers
       WHERE sid=? AND workflow_path=? ORDER BY created_at DESC LIMIT 150""",
       (sid,path)).fetchall()
    return {"nodes":list(latest.values()),"edges":[dict(r) for r in edges]}
