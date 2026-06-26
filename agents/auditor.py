import os
from neo4j import GraphDatabase
from neo4j.graph import Node, Relationship, Path

class GraphAuditorAgent:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password123")

    def _serialize_value(self, val):
        if isinstance(val, Node):
            return {
                "_type": "Node",
                "id": val.id if hasattr(val, 'id') else None,
                "labels": list(val.labels),
                "properties": dict(val.items())
            }
        elif isinstance(val, Relationship):
            return {
                "_type": "Relationship",
                "id": val.id if hasattr(val, 'id') else None,
                "type": val.type,
                "start_node_id": val.start_node.id if hasattr(val.start_node, 'id') else val.nodes[0].id,
                "end_node_id": val.end_node.id if hasattr(val.end_node, 'id') else val.nodes[1].id,
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
            with GraphDatabase.driver(self.uri, auth=(self.username, self.password)) as driver:
                with driver.session() as session:
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
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
