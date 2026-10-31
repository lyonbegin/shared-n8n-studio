"""Generic, fail-closed bridge to a consumer application's approved node registry.

No project names, workflow IDs, business rules or arbitrary code execution.
A module is injected by the consuming service at deployment time.
"""
import importlib
import os

def adapter():
    name=os.environ.get("STUDIO_PROJECT_ADAPTER","").strip()
    if not name:return None
    if not name.isidentifier():raise RuntimeError("INVALID_PROJECT_ADAPTER_MODULE")
    return importlib.import_module(name)

def binding_for(workflow_path,node_id):
    a=adapter()
    return a.node_binding(workflow_path,node_id) if a else None

def kind_for(workflow_path):
    a=adapter()
    return a.WF01_MODES.get(workflow_path) if a else None

def check_node(workflow,workflow_path,node_id):
    a=adapter()
    if not a:return None
    expected=a.node_binding(workflow_path,node_id)
    expected_type=a.node_type(workflow_path,node_id)
    n=next((node for node in workflow.get("nodes",[]) if node.get("id")==node_id),None)
    if not n or not expected or n.get("type")!=expected_type:
        return None
    if n.get("parameters",{}).get("studioPython")!=expected:
        return None
    return expected

def execute_registered(workflow_path,node_id,input_json):
    a=adapter()
    if not a or not a.node_binding(workflow_path,node_id):
        raise ValueError("UNREGISTERED_PROJECT_NODE")
    return a.execute_node(workflow_path,node_id,input_json)
