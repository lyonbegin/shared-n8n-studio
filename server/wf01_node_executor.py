"""WF-01 N01 only: real Python input contract for a manual collection start.

No TradingView, network, filesystem or n8n operations. This is a manually
selected one-node execution adapter, not a full n8n workflow execution engine.
"""

def execute_node01(input_json: dict, *, workflow_kind: str) -> dict:
    """Validate a requested collection kind and return the bounded N01 config."""
    if not isinstance(input_json, dict):
        raise ValueError("INPUT_JSON_OBJECT_REQUIRED")
    if workflow_kind not in ("strategy", "library"):
        raise ValueError("UNSUPPORTED_WORKFLOW_KIND")
    allowed = {"ui_selection", "requested_detail_limit", "max_pages"}
    if not {"ui_selection", "requested_detail_limit"}.issubset(input_json) or (set(input_json) - allowed):
        raise ValueError("INPUT_FIELDS_MISMATCH: ui_selection, requested_detail_limit")
    if input_json["ui_selection"] != workflow_kind:
        raise ValueError("COLLECTION_KIND_MISMATCH")
    limit = input_json["requested_detail_limit"]
    if isinstance(limit, bool) or not isinstance(limit, int) or limit != 1:
        raise ValueError("DETAIL_LIMIT_MUST_EQUAL_ONE")
    max_pages = input_json.get("max_pages", 3)
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or not 1 <= max_pages <= 3:
        raise ValueError("MAX_PAGES_MUST_BE_1_TO_3")
    return {
        "kind": workflow_kind,
        "page": 1,
        "max_pages": max_pages,
        "max_detail_success": 1,
        "sort": "recent_extended",
        "execution_mode": "ONE_NODE_ONLY",
        "tradingview_requested": False,
        "next_node_executed": False,
    }
