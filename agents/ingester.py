import logging
import os
import re
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Dict
from neo4j import GraphDatabase

logger = logging.getLogger("corp_intel.ingester")

_LABEL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_REL_TYPE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_PROPERTY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


class UnsafeIdentifierError(ValueError):
    pass


def _validate_label(label: str) -> str:
    if not isinstance(label, str) or not _LABEL_RE.match(label):
        raise UnsafeIdentifierError(
            f"Refusing to use unsafe Neo4j label {label!r} from LLM output. "
            "Labels must match ^[A-Za-z][A-Za-z0-9_]{0,63}$."
        )
    return label


def _validate_rel_type(rel_type: str) -> str:
    if not isinstance(rel_type, str) or not _REL_TYPE_RE.match(rel_type):
        raise UnsafeIdentifierError(
            f"Refusing to use unsafe Neo4j relationship type {rel_type!r} from "
            "LLM output. Relationship types must match ^[A-Z][A-Z0-9_]{0,63}$."
        )
    return rel_type


def _validate_property(prop: str) -> str:
    if not isinstance(prop, str) or not _PROPERTY_RE.match(prop):
        raise UnsafeIdentifierError(
            f"Refusing to use unsafe Neo4j property name {prop!r} from LLM "
            "output. Property names must match ^[A-Za-z_][A-Za-z0-9_]{0,63}$."
        )
    return prop


class NodeMapping(BaseModel):
    label: str = Field(description="Neo4j label for the node, e.g. Person, Company, BankAccount")
    id_column: str = Field(description="The CSV column representing the unique identifier for this node")
    id_property: str = Field(description="The Neo4j property name for this identifier, e.g. name, account_number")
    properties: Dict[str, str] = Field(
        description="Dictionary mapping other CSV columns to Neo4j properties. Key is CSV column, value is Neo4j property name."
    )


class RelationshipMapping(BaseModel):
    type: str = Field(description="The relationship type, e.g. TRANSFERRED_MONEY_TO, OWNER_OF, REGISTERED_AT")
    source_label: str = Field(description="The label of the source node")
    source_id_column: str = Field(description="The CSV column of the source node's unique identifier")
    source_id_property: str = Field(description="The Neo4j property name for the source node's identifier")
    target_label: str = Field(description="The label of the target node")
    target_id_column: str = Field(description="The CSV column of the target node's unique identifier")
    target_id_property: str = Field(description="The Neo4j property name for the target node's identifier")
    properties: Dict[str, str] = Field(
        description="Dictionary mapping other CSV columns to relationship properties. Key is CSV column, value is property name."
    )


class IngestionSpec(BaseModel):
    nodes: List[NodeMapping] = Field(description="Nodes to extract from the CSV")
    relationships: List[RelationshipMapping] = Field(description="Relationships to extract from the CSV")


class DatasetIngesterAgent:
    def __init__(self):
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash"
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password123")

    def _infer_schema(self, file_name: str, sample_df: pd.DataFrame) -> IngestionSpec:
        sample_json = sample_df.to_json(orient="records", double_precision=2)

        prompt = f"""
You are a Database Ingestion Agent. Your job is to analyze the structure of an uploaded CSV file and decide how to map its columns to a Neo4j Graph Database schema (Nodes and Relationships) for forensic auditing.

File name: {file_name}
CSV sample data (first 3 rows in JSON format):
{sample_json}

Task:
Generate a structured JSON schema mapping details.
- Identify the core entities (Nodes) in each row (e.g. Sender, Receiver, Company, Account, Country).
- Identify how these entities connect (Relationships) (e.g. TRANSFERRED_TO, OWNER_OF, REGISTERED_AT).
- Make sure to map a unique key column for every node.
"""

        from agents.llm_helper import call_gemini_with_retry
        response = call_gemini_with_retry(
            self.client,
            "models.generate_content",
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=IngestionSpec,
                temperature=0.1
            )
        )

        return IngestionSpec.model_validate_json(response.text.strip())

    def validate_spec(self, spec: IngestionSpec) -> None:
        for nm in spec.nodes:
            _validate_label(nm.label)
            _validate_property(nm.id_property)
            for neo_prop in nm.properties.values():
                _validate_property(neo_prop)
        for rm in spec.relationships:
            _validate_rel_type(rm.type)
            _validate_label(rm.source_label)
            _validate_label(rm.target_label)
            _validate_property(rm.source_id_property)
            _validate_property(rm.target_id_property)
            for rel_prop in rm.properties.values():
                _validate_property(rel_prop)

    @staticmethod
    def _build_rows(df: pd.DataFrame, key_col: str, neo_id_prop: str,
                    column_to_property: Dict[str, str]) -> List[dict]:
        rows: List[dict] = []
        for _, row in df.iterrows():
            key_val = row[key_col]
            if pd.isna(key_val):
                continue
            props = {neo_id_prop: str(key_val)}
            for csv_col, neo_prop in column_to_property.items():
                if csv_col in df.columns and not pd.isna(row[csv_col]):
                    val = row[csv_col]
                    if hasattr(val, "item"):
                        val = val.item()
                    props[neo_prop] = val
            rows.append({"key": str(key_val), "props": props})
        return rows

    @staticmethod
    def _build_rel_rows(df: pd.DataFrame, s_col: str, t_col: str,
                        column_to_property: Dict[str, str]) -> List[dict]:
        rows: List[dict] = []
        for _, row in df.iterrows():
            s_val = row[s_col]
            t_val = row[t_col]
            if pd.isna(s_val) or pd.isna(t_val):
                continue
            props: dict = {}
            for csv_col, rel_prop in column_to_property.items():
                if csv_col in df.columns and not pd.isna(row[csv_col]):
                    val = row[csv_col]
                    if hasattr(val, "item"):
                        val = val.item()
                    props[rel_prop] = val
            rows.append({"s": str(s_val), "t": str(t_val), "props": props})
        return rows

    def ingest_csv(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        df = pd.read_csv(file_path)
        df = df.dropna(how="all")

        sample_df = df.head(3)

        logger.info("Inferring schema for %s", file_name)
        spec = self._infer_schema(file_name, sample_df)

        try:
            self.validate_spec(spec)
        except UnsafeIdentifierError as exc:
            logger.warning("Rejected unsafe schema from LLM: %s", exc)
            return {"status": "error", "message": str(exc)}

        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            driver.verify_connectivity()
        except Exception as exc:
            return {"status": "error", "message": f"Could not connect to Neo4j: {exc}"}

        nodes_created = 0
        nodes_merged = 0
        rels_created = 0
        rels_merged = 0

        with driver:
            with driver.session() as session:
                for nm in spec.nodes:
                    if nm.id_column not in df.columns:
                        continue
                    constraint = (
                        f"CREATE CONSTRAINT IF NOT EXISTS "
                        f"FOR (n:{nm.label}) REQUIRE n.`{nm.id_property}` IS UNIQUE"
                    )
                    try:
                        session.run(constraint)
                    except Exception as exc:
                        logger.debug(
                            "Constraint creation skipped for %s.%s: %s",
                            nm.label, nm.id_property, exc,
                        )

                def _ingest_tx(tx):
                    nonlocal nodes_created, nodes_merged, rels_created, rels_merged

                    for nm in spec.nodes:
                        if nm.id_column not in df.columns:
                            continue
                        rows = self._build_rows(
                            df, nm.id_column, nm.id_property, nm.properties
                        )
                        if not rows:
                            continue
                        query = (
                            "UNWIND $rows AS row "
                            f"MERGE (n:{nm.label} {{`{nm.id_property}`: row.key}}) "
                            "SET n += row.props"
                        )
                        summary = tx.run(query, rows=rows).consume()
                        nodes_created += summary.counters.nodes_created
                        nodes_merged += len(rows)

                    for rm in spec.relationships:
                        if (rm.source_id_column not in df.columns
                                or rm.target_id_column not in df.columns):
                            continue
                        rows = self._build_rel_rows(
                            df, rm.source_id_column, rm.target_id_column, rm.properties
                        )
                        if not rows:
                            continue
                        query = (
                            "UNWIND $rows AS row "
                            f"MATCH (source:{rm.source_label} "
                            f"{{`{rm.source_id_property}`: row.s}}) "
                            f"MATCH (target:{rm.target_label} "
                            f"{{`{rm.target_id_property}`: row.t}}) "
                            f"MERGE (source)-[r:{rm.type}]->(target) "
                            "SET r += row.props"
                        )
                        summary = tx.run(query, rows=rows).consume()
                        rels_created += summary.counters.relationships_created
                        rels_merged += len(rows)

                session.execute_write(_ingest_tx)

        logger.info(
            "Ingested %s: nodes new=%d processed=%d, rels new=%d processed=%d",
            file_name, nodes_created, nodes_merged, rels_created, rels_merged,
        )
        return {
            "status": "success",
            "file": file_name,
            "nodes_inserted": nodes_created,
            "nodes_processed": nodes_merged,
            "relationships_inserted": rels_created,
            "relationships_processed": rels_merged,
            "spec": spec.model_dump(),
        }
