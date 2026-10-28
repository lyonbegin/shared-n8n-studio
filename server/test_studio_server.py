"""Black-box tests of the actual HTTP SQLite server (no node executor)."""
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request

HERE = Path(__file__).resolve().parent
SERVER = HERE / "studio_server.py"
NODE_A={"id":"a","name":"Manual Trigger","type":"n8n-nodes-base.manualTrigger","typeVersion":1,"parameters":{},"position":[100,200]}
NODE_B={"id":"b","name":"No Operation","type":"n8n-nodes-base.noOp","typeVersion":1,"parameters":{},"position":[400,200]}
FLOW={"name":"F01_TEST","nodes":[NODE_A,NODE_B],"connections":{"Manual Trigger":{"main":[[{"node":"No Operation","type":"main","index":0}]]}},"active":False}
ENDPOINT="api/studio/workflows/operations/F01.json"

def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        return s.getsockname()[1]

class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.root=Path(cls.temp.name)
        fixture=cls.root/"dist"/"stock-workflows"/"operations"/"F01.json"
        fixture.parent.mkdir(parents=True)
        fixture.write_text(json.dumps(FLOW))
        (cls.root/"dist"/"index.html").write_text("<!doctype html><title>Shared Studio</title>")
        cls.port=port()
        cls.env={**os.environ,"PORT":str(cls.port),"STUDIO_STATIC_ROOT":str(cls.root/"dist"),"STUDIO_DB_PATH":str(cls.root/"data"/"studio.sqlite3")}
        cls.start()
    @classmethod
    def start(cls):
        cls.proc=subprocess.Popen([sys.executable,str(SERVER)],env=cls.env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                cls.call("health")
                return
            except Exception:
                time.sleep(.05)
        raise RuntimeError("Studio HTTP server did not start")
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)
        cls.temp.cleanup()
    @classmethod
    def call(cls,path,method="GET",data=None,opener=None):
        url="http://127.0.0.1:"+str(cls.port)+"/"+path
        headers={}
        if data is not None:
            data=json.dumps(data).encode()
            headers["Content-Type"]="application/json"
        req=Request(url,data=data,method=method,headers=headers)
        try:
            resp=(opener or build_opener()).open(req,timeout=5)
        except HTTPError as e:
            resp=e
        content=resp.read()
        result=json.loads(content) if content.startswith(b"{") else content.decode()
        return resp.status,result

    def test_server_save_reload_version_conflict_and_history(self):
        cookies=http.cookiejar.CookieJar()
        browser=build_opener(HTTPCookieProcessor(cookies))
        status,first=self.call(ENDPOINT,opener=browser)
        self.assertEqual(status,200)
        self.assertEqual(first["version"],0)
        self.assertEqual(first["source"],"original")
        self.assertEqual(len(cookies),1)
        modified=json.loads(json.dumps(first["workflow"]))
        modified["nodes"][1]["position"]=[800,330]
        status,saved=self.call(ENDPOINT,"PUT",{"expectedVersion":0,"workflow":modified},browser)
        self.assertEqual(status,200)
        self.assertEqual(saved["version"],1)
        status,again=self.call(ENDPOINT,opener=browser)
        self.assertEqual(again["source"],"server")
        self.assertEqual(again["workflow"]["nodes"][1]["position"],[800,330])
        self.assertEqual(again["version"],1)
        status,conflict=self.call(ENDPOINT,"PUT",{"expectedVersion":0,"workflow":modified},browser)
        self.assertEqual(status,409)
        self.assertEqual(conflict["currentVersion"],1)
        _,history=self.call(ENDPOINT+"/versions",opener=browser)
        self.assertEqual(history["versions"][0]["version"],1)
        # A browser without this cookie must not read private drafts.
        _,fresh=self.call(ENDPOINT,opener=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar())))
        self.assertEqual(fresh["version"],0)
        # Persist across complete process restart, not only memory.
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self.start()
        _,persisted=self.call(ENDPOINT,opener=browser)
        self.assertEqual(persisted["version"],1)
        self.assertEqual(persisted["workflow"]["nodes"][1]["position"],[800,330])

    def test_invalid_graph_and_activation_are_rejected_or_sanitized(self):
        browser=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        _,first=self.call(ENDPOINT,opener=browser)
        bad=json.loads(json.dumps(first["workflow"]))
        bad["connections"]["Manual Trigger"]["main"][0][0]["node"]="missing"
        s,_=self.call(ENDPOINT,"PUT",{"expectedVersion":0,"workflow":bad},browser)
        self.assertEqual(s,400)
        good=json.loads(json.dumps(first["workflow"]))
        good["active"]=True
        s,_=self.call(ENDPOINT,"PUT",{"expectedVersion":0,"workflow":good},browser)
        self.assertEqual(s,200)
        _,value=self.call(ENDPOINT,opener=browser)
        self.assertFalse(value["workflow"]["active"])

    def test_disabled_execution_no_path_traversal_no_unsupported_api(self):
        s,_=self.call("api/studio/run",method="POST",data={"anything":"true"})
        self.assertEqual(s,405)
        s,_=self.call("api/studio/workflows/operations/..%2F..%2Fsecrets.json")
        self.assertEqual(s,404)
        s,_=self.call("api/not-existing")
        self.assertEqual(s,404)
        s,health=self.call("api/studio/health")
        self.assertEqual(s,200)
        self.assertFalse(health["executionEnabled"])
        s,page=self.call("")
        self.assertEqual(s,200)
        self.assertIn("Shared Studio",page)

if __name__=="__main__":
    unittest.main()
