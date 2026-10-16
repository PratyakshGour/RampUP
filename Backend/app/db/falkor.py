from typing import Any
from falkordb import FalkorDB, Node, Edge
from app.config import settings


class _LazyGraph:
    """Lazy proxy so importing the module does not crash when FalkorDB is offline."""
    def __init__(self):
        self._graph = None

    def _get_graph(self):
        if self._graph is None:
            db = FalkorDB(
                host=settings.falkordb_host,
                port=settings.falkordb_port,
                password=settings.falkordb_password or None,
            )
            self._graph = db.select_graph(settings.falkordb_graph)
        return self._graph

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get_graph(), name)


graph = _LazyGraph()


def _convert(v):
    """Turn FalkorDB Node/Edge objects into plain dicts."""
    if isinstance(v, Node):
        label = "Node"
        if isinstance(v.labels, list) and v.labels:
            label = v.labels[0]
        elif isinstance(v.labels, str) and v.labels:
            label = v.labels
        return {
            "_type": "node",
            "id": v.properties.get("id", v.id),
            "label": label,
            "props": v.properties or {},
        }
    if isinstance(v, Edge):
        src = v.src_node.properties.get("id", v.src_node.id) if isinstance(v.src_node, Node) else v.src_node
        dst = v.dest_node.properties.get("id", v.dest_node.id) if isinstance(v.dest_node, Node) else v.dest_node
        return {
            "_type": "edge",
            "type": v.relation,
            "src": str(src) if src is not None else "",
            "dst": str(dst) if dst is not None else "",
            "props": v.properties or {},
        }
    if isinstance(v, list):
        return [_convert(x) for x in v]
    return v


def run(cypher: str, params: dict | None = None) -> list[dict]:
    """Run a Cypher query and return rows as plain dicts."""
    res = graph.query(cypher, params or {})
    header = getattr(res, "header", None) or []
    cols = [h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else h for h in header]
    result_set = getattr(res, "result_set", None) or []
    return [{str(c): _convert(val) for c, val in zip(cols, row)} for row in result_set]


def clear_graph() -> None:
    """Delete all nodes and edges (dev reset)."""
    graph.query("MATCH (n) DETACH DELETE n")


def ping() -> bool:
    try:
        graph.query("RETURN 1")
        return True
    except Exception:
        return False