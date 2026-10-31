"""Generic N01->N02 / N02->N03 edge transfer regression tests; no stock dependency."""
import json
import secrets
import sqlite3
import unittest
from node_run_store import (init_node_run_db,store_node_result,resolve_transfer,
   consume_transfer,available_transfers,latest_graph_state)

FLOW={"nodes":[{"id":"a","name":"Start"},{"id":"b","name":"Prepare"},{"id":"c","name":"Fetch"}],
  "connections":{"Start":{"main":[[{"node":"Prepare","index":0}]]},
                 "Prepare":{"main":[[{"node":"Fetch","index":0}]]}}}

def connect():
    db=sqlite3.connect(":memory:")
    db.row_factory=sqlite3.Row
    init_node_run_db(db)
    return db

def persist(db,sid,node,run_id,out,workflow_run_id=None,upstream_run_id=None,status="SUCCESS"):
    return store_node_result(db,sid=sid,path="operations/X.json",workflow=FLOW,
      run_id=run_id,workflow_run_id=workflow_run_id or run_id,
      node_id=node,input_json={"input":"original"},output_json=out,
      upstream_run_id=upstream_run_id,code_ref="approved.adapter",
      code_sha256="a"*64,status=status)

class TestEdgeTransfer(unittest.TestCase):
    def test_entire_json_is_preserved_and_exact_run_provenance(self):
        db=connect()
        original={"kind":"strategy","page":1,"max_pages":3,
                  "flags":{"no_trade":True},"items":[{"source":"X","version":"1"}]}
        transfers=persist(db,"browser-a","a","run-01",original)
        self.assertEqual(len(transfers),1)
        self.assertEqual(transfers[0]["target_node_id"],"b")
        rows=available_transfers(db,"browser-a","operations/X.json","b")
        self.assertEqual(rows[0]["output_json"],original)
        result=resolve_transfer(db,sid="browser-a",path="operations/X.json",
            workflow=FLOW,target_node_id="b",source_run_id="run-01")
        self.assertEqual(result["output_json"],original)
        enriched={**result["output_json"],"page_size":50}
        transfers2=persist(db,"browser-a","b","run-02",enriched,"run-01","run-01")
        consume_transfer(db,result["transfer_id"],"run-02")
        self.assertEqual(transfers2[0]["target_node_id"],"c")
        self.assertEqual(available_transfers(db,"browser-a","operations/X.json","b")[0]["status"],"CONSUMED")
        self.assertEqual(available_transfers(db,"browser-a","operations/X.json","c")[0]["output_json"]["page_size"],50)
        original_a=db.execute("SELECT output_json FROM node_runs WHERE run_id='run-01'").fetchone()
        self.assertEqual(json.loads(original_a["output_json"]),original)
        st=latest_graph_state(db,"browser-a","operations/X.json")
        self.assertEqual({n["node_id"] for n in st["nodes"]},{"a","b"})
        self.assertEqual([e["status"] for e in st["edges"]],["CONSUMED","READY"])
        db.close()

    def test_cross_browser_cross_run_and_disconnected_source_blocked(self):
        db=connect()
        persist(db,"browser-a","a","run1",{"ok":True})
        with self.assertRaisesRegex(ValueError,"CONNECTED_UPSTREAM_RUN_NOT_READY"):
            resolve_transfer(db,sid="browser-b",path="operations/X.json",
               workflow=FLOW,target_node_id="b",source_run_id="run1")
        with self.assertRaisesRegex(ValueError,"CONNECTED_UPSTREAM_RUN_NOT_READY"):
            resolve_transfer(db,sid="browser-a",path="operations/X.json",
               workflow=FLOW,target_node_id="c",source_run_id="run1")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"UNIQUE"):
            persist(db,"browser-a","a","run1",{"ok":True})
        db.close()

    def test_failed_node_has_no_transfer_and_replay_blocked(self):
        db=connect()
        self.assertEqual(persist(db,"sid","a","fail1",None,status="FAILED"),[])
        self.assertEqual(available_transfers(db,"sid","operations/X.json","b"),[])
        persist(db,"sid","a","ok1",{"name":"ok"})
        result=resolve_transfer(db,sid="sid",path="operations/X.json",
            workflow=FLOW,target_node_id="b",source_run_id="ok1")
        consume_transfer(db,result["transfer_id"],"next")
        with self.assertRaisesRegex(ValueError,"CONNECTED_UPSTREAM_RUN_NOT_READY"):
            resolve_transfer(db,sid="sid",path="operations/X.json",
                workflow=FLOW,target_node_id="b",source_run_id="ok1")
        db.close()

if __name__=="__main__":unittest.main()
