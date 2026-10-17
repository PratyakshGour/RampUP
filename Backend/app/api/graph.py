from fastapi import APIRouter, HTTPException, Query

from app.db import falkor

router = APIRouter(prefix="/api/graph", tags=["knowledge graph"])
ALLOWED_NODE_TYPES = {"Person", "Meeting", "Project", "System", "Decision", "Task", "Fact"}


@router.get("")
def get_graph(
    node_type: str | None = Query(default=None),
    focus: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=500),
):
    if node_type and node_type not in ALLOWED_NODE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported graph node type")
    if focus:
        rows = falkor.read(
            "MATCH (center {id: $id})-[r]-(other) "
            "RETURN startNode(r).id AS source, endNode(r).id AS target, "
            "type(r) AS relationship, properties(r) AS properties LIMIT $limit",
            {"id": focus, "limit": limit},
        )
        node_rows = falkor.read(
            "MATCH (center {id: $id}) OPTIONAL MATCH (center)-[r]-(other) "
            "RETURN center AS n, collect(DISTINCT other) AS adjacent",
            {"id": focus},
        )
    else:
        if node_type:
            node_rows = falkor.read(
                f"MATCH (n:{node_type}) RETURN n LIMIT $limit",
                {"limit": limit},
            )
            matching_nodes = node_rows
            rows = falkor.read(
                f"MATCH (a:{node_type})-[r]-(b) "
                "RETURN DISTINCT startNode(r) AS a, endNode(r) AS b, "
                "startNode(r).id AS source, endNode(r).id AS target, "
                "type(r) AS relationship, properties(r) AS properties LIMIT $limit",
                {"limit": limit},
            )
            adjacent_nodes = [
                {"n": node}
                for row in rows
                for node in (row.get("a"), row.get("b"))
                if isinstance(node, dict)
            ]
            node_rows = matching_nodes + adjacent_nodes
        else:
            node_rows = falkor.read("MATCH (n) RETURN n LIMIT $limit", {"limit": limit})
            rows = falkor.read(
                "MATCH (a)-[r]->(b) RETURN a.id AS source, b.id AS target, "
                "type(r) AS relationship, properties(r) AS properties LIMIT $limit",
                {"limit": limit},
            )

    nodes_by_id = {}
    if focus and node_rows:
        candidates = [node_rows[0].get("n"), *node_rows[0].get("adjacent", [])]
        node_rows = [{"n": node} for node in candidates if isinstance(node, dict)]
    for row in node_rows:
        node = row.get("n")
        if isinstance(node, dict) and node.get("id"):
            nodes_by_id[node["id"]] = {
                "id": node["id"],
                "type": node.get("label"),
                "data": node.get("props", {}),
            }
    nodes = list(nodes_by_id.values())
    edges = [
        {
            "id": f"{row['source']}-{row['relationship']}-{row['target']}",
            "source": row["source"],
            "target": row["target"],
            "label": row["relationship"],
            "data": row.get("properties") or {},
        }
        for row in rows
    ]
    return {"nodes": nodes, "edges": edges}


@router.get("/node/{node_id}")
def get_graph_node(node_id: str):
    rows = falkor.read("MATCH (n {id: $id}) RETURN n LIMIT 1", {"id": node_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Graph node was not found")
    node = rows[0]["n"]
    rels = falkor.read(
        "MATCH (n {id: $id})-[r]-(other) "
        "RETURN other.id AS id, labels(other) AS labels, properties(other) AS properties, "
        "type(r) AS relationship LIMIT 100",
        {"id": node_id},
    )
    return {
        "id": node.get("id"),
        "type": node.get("label"),
        "data": node.get("props", {}),
        "relationships": rels,
    }
