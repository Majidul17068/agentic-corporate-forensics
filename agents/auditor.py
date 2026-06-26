import logging
import os
from typing import Optional
from neo4j import Driver, GraphDatabase
from neo4j.graph import Node, Relationship, Path

logger = logging.getLogger("corp_intel.auditor")

_DRIVER: Optional[Driver] = None


def _get_driver() -> Driver:
    global _DRIVER
    if _DRIVER is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
        _DRIVER = GraphDatabase.driver(uri, auth=(username, password))
    return _DRIVER


def close_driver() -> None:
    global _DRIVER
    if _DRIVER is not None:
        _DRIVER.close()
        _DRIVER = None


class GraphAuditorAgent:
    def __init__(self):
        self.driver = _get_driver()

    def _serialize_value(self, val):
        if isinstance(val, Node):
            return {
                "_type": "Node",
                "id": val.element_id if hasattr(val, "element_id") else None,
                "labels": list(val.labels),
                "properties": dict(val.items())
            }
        elif isinstance(val, Relationship):
            return {
                "_type": "Relationship",
                "id": val.element_id if hasattr(val, "element_id") else None,
                "type": val.type,
                "start_node_id": (
                    val.start_node.element_id
                    if val.start_node is not None and hasattr(val.start_node, "element_id")
                    else None
                ),
                "end_node_id": (
                    val.end_node.element_id
                    if val.end_node is not None and hasattr(val.end_node, "element_id")
                    else None
                ),
                "properties": dict(val.items())
            }
        elif isinstance(val, Path):
            return {
                "_type": "Path",
                "nodes": [self._serialize_value(n) for n in val.nodes],
                "relationships": [self._serialize_value(r) for r in val.relationships]
            }
        elif isinstance(val, list):
            return [self._serialize_value(item) for item in val]
        elif isinstance(val, dict):
            return {k: self._serialize_value(v) for k, v in val.items()}
        else:
            return val

    def execute_query(self, cypher_query: str):
        try:
            with self.driver.session() as session:
                result = session.run(cypher_query)
                records = []
                for record in result:
                    record_dict = {}
                    for key, value in record.items():
                        record_dict[key] = self._serialize_value(value)
                    records.append(record_dict)

                return {
                    "status": "success",
                    "records_count": len(records),
                    "data": records
                }
        except Exception as exc:
            logger.warning("Cypher execution failed: %s", exc)
            return {
                "status": "error",
                "message": str(exc)
            }
