from functools import lru_cache
from typing import Any

from falkordb import Edge, FalkorDB, Node

from app.config import settings


@lru_cache(maxsize=1)
def _graph():
    database = FalkorDB(
        host=settings.falkordb_host,
        port=settings.falkordb_port,
        password=settings.falkordb_password or None,
    )
    return database.select_graph(settings.falkordb_graph)


def _convert(value: Any) -> Any:
    if isinstance(value, Node):
        return {
            "_type": "node",
            "id": value.properties.get("id", value.id),
            "label": value.labels[0] if value.labels else "Node",
            "props": value.properties,
        }
    if isinstance(value, Edge):
        return {
            "_type": "edge",
            "type": value.relation,
            "src": value.src_node,
            "dst": value.dest_node,
            "props": value.properties,
        }
    if isinstance(value, list):
        return [_convert(item) for item in value]
    if isinstance(value, dict):
        return {key: _convert(item) for key, item in value.items()}
    return value


def run(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = _graph().query(cypher, params or {})
    return _rows(result)


def read(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result = _graph().ro_query(cypher, params or {})
    return _rows(result)


def _rows(result) -> list[dict[str, Any]]:
    columns = [
        header[1] if isinstance(header, (list, tuple)) else header
        for header in result.header
    ]
    return [
        {column: _convert(value) for column, value in zip(columns, row)}
        for row in result.result_set
    ]


def ping() -> bool:
    try:
        read("RETURN 1 AS healthy")
        return True
    except Exception:
        return False
