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
        self.assertEqual({e["target_node_id"]:e["status"] for e in st["edges"]},{"b":"CONSUMED","c":"READY"})
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

    def test_if_only_selected_output_is_transferred(self):
        graph={"nodes":[{"id":"if","name":"Decision"},
                        {"id":"yes","name":"If True"},{"id":"no","name":"If False"}],
          "connections":{"Decision":{"main":[
             [{"node":"If True","index":0}],
             [{"node":"If False","index":0}]]}}}
        db=connect()
        paths=store_node_result(db,sid="sid",path="operations/IF.json",
          workflow=graph,run_id="if-1",workflow_run_id="flow-1",node_id="if",
          input_json={"has_candidate":True},
          output_json={"has_candidate":True,"_studio_active_ports":[0]},
          active_source_ports=[0])
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0]["source_port"],0)
        self.assertEqual(paths[0]["target_node_id"],"yes")
        self.assertEqual(available_transfers(db,"sid","operations/IF.json","no"),[])
        self.assertEqual(len(available_transfers(db,"sid","operations/IF.json","yes")),1)
        paths2=store_node_result(db,sid="sid",path="operations/IF.json",
          workflow=graph,run_id="if-2",workflow_run_id="flow-2",node_id="if",
          input_json={"has_candidate":False},
          output_json={"has_candidate":False,"_studio_active_ports":[1]},
          active_source_ports=[1])
        self.assertEqual([p["target_node_id"] for p in paths2],["no"])
        with self.assertRaisesRegex(ValueError,"ACTIVE_SOURCE_PORT_NOT_CONNECTED"):
            store_node_result(db,sid="sid",path="operations/IF.json",
               workflow=graph,run_id="bad",workflow_run_id="bad",node_id="if",
               input_json={},output_json={},active_source_ports=[2])
        db.close()

if __name__=="__main__":unittest.main()
