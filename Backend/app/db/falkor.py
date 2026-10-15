
from falkordb import FalkorDB, Node, Edge
from app.config import settings

_db = FalkorDB(
    host=settings.falkordb_host,
    port=settings.falkordb_port,
    password=settings.falkordb_password or None,
)
graph = _db.select_graph(settings.falkordb_graph)


def _convert(v):
    """Turn FalkorDB Node/Edge objects into plain dicts."""
    if isinstance(v, Node):
        return {"_type": "node", "id": v.properties.get("id", v.id),
                "label": v.labels[0] if v.labels else "Node", "props": v.properties}
    if isinstance(v, Edge):
        return {"_type": "edge", "type": v.relation, "src": v.src_node, "dst": v.dest_node,
                "props": v.properties}
    if isinstance(v, list):
        return [_convert(x) for x in v]
    return v


def run(cypher: str, params: dict | None = None) -> list[dict]:
    """Run a Cypher query and return rows as plain dicts."""
    res = graph.query(cypher, params or {})
    cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
    return [{c: _convert(val) for c, val in zip(cols, row)} for row in res.result_set]


def clear_graph() -> None:
    """Delete all nodes and edges (dev reset)."""
    graph.query("MATCH (n) DETACH DELETE n")


def ping() -> bool:
    try:
        graph.query("RETURN 1")
        return True
    except Exception:
        return False