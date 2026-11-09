import logging
import os
from typing import Optional

from personakit.graphrag import Neo4jGraphStore

logger = logging.getLogger("corp_intel.auditor")

_STORE: Optional[Neo4jGraphStore] = None


def _get_store() -> Neo4jGraphStore:
    global _STORE
    if _STORE is None:
        _STORE = Neo4jGraphStore(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            username=os.getenv("NEO4J_USERNAME", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123"),
        )
    return _STORE


def close_driver() -> None:
    global _STORE
    if _STORE is not None:
        _STORE.close()
        _STORE = None


class GraphAuditorAgent:
    def __init__(self):
        self.store = _get_store()

    def execute_query(self, cypher_query: str):
        result = self.store.query(cypher_query)
        if result.ok:
            return {
                "status": "success",
                "records_count": len(result.records),
                "data": result.records,
            }
        logger.warning("Cypher execution failed: %s", result.error)
        return {
            "status": "error",
            "message": result.error or "unknown error",
        }
