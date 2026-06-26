import os
import json
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Dict
from neo4j import GraphDatabase

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

    def ingest_csv(self, file_path: str) -> dict:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = os.path.basename(file_path)
        df = pd.read_csv(file_path)
        df = df.dropna(how='all')
        
        sample_df = df.head(3)
        
        print(f"[Ingester] Inferring schema for {file_name}...")
        spec = self._infer_schema(file_name, sample_df)

        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            driver.verify_connectivity()
        except Exception as e:
            return {
                "status": "error",
                "message": f"Could not connect to Neo4j: {e}"
            }

        nodes_created = 0
        rels_created = 0

        with driver:
            with driver.session() as session:
                for node_map in spec.nodes:
                    label = node_map.label
                    id_col = node_map.id_column
                    id_prop = node_map.id_property
                    other_props = node_map.properties

                    if id_col not in df.columns:
                        continue

                    try:
                        session.run(f"CREATE CONSTRAINT FOR (n:{label}) REQUIRE n.{id_prop} IS UNIQUE")
                    except Exception:
                        pass 

                    for _, row in df.iterrows():
                        key_val = row[id_col]
                        if pd.isna(key_val):
                            continue
                        
                        props = {id_prop: str(key_val)}
                        for csv_col, neo_prop in other_props.items():
                            if csv_col in df.columns and not pd.isna(row[csv_col]):
                                val = row[csv_col]
                                if hasattr(val, 'item'):
                                    val = val.item()
                                props[neo_prop] = val

                        query = f"""
                        MERGE (n:{label} {{{id_prop}: $key_val}})
                        SET n += $properties
                        """
                        session.run(query, key_val=str(key_val), properties=props)
                        nodes_created += 1

                for rel_map in spec.relationships:
                    rel_type = rel_map.type
                    s_label = rel_map.source_label
                    s_id_col = rel_map.source_id_column
                    s_id_prop = rel_map.source_id_property
                    t_label = rel_map.target_label
                    t_id_col = rel_map.target_id_column
                    t_id_prop = rel_map.target_id_property
                    other_props = rel_map.properties

                    if s_id_col not in df.columns or t_id_col not in df.columns:
                        continue

                    for _, row in df.iterrows():
                        s_val = row[s_id_col]
                        t_val = row[t_id_col]
                        if pd.isna(s_val) or pd.isna(t_val):
                            continue

                        props = {}
                        for csv_col, rel_prop in other_props.items():
                            if csv_col in df.columns and not pd.isna(row[csv_col]):
                                val = row[csv_col]
                                if hasattr(val, 'item'):
                                    val = val.item()
                                props[rel_prop] = val

                        query = f"""
                        MATCH (source:{s_label} {{{s_id_prop}: $s_val}})
                        MATCH (target:{t_label} {{{t_id_prop}: $t_val}})
                        MERGE (source)-[r:{rel_type}]->(target)
                        SET r += $properties
                        """
                        session.run(query, s_val=str(s_val), t_val=str(t_val), properties=props)
                        rels_created += 1

        return {
            "status": "success",
            "file": file_name,
            "nodes_inserted": nodes_created,
            "relationships_inserted": rels_created,
            "spec": spec.model_dump()
        }
