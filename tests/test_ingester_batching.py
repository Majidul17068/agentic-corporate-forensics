from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import pytest

from agents.ingester import DatasetIngesterAgent, NodeMapping, RelationshipMapping


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"sender": "ACC-001", "receiver": "ACC-002", "amount": 1000.0, "bank": "Bank A"},
            {"sender": "ACC-002", "receiver": "ACC-003", "amount": 500.0, "bank": "Bank B"},
            {"sender": "ACC-001", "receiver": "ACC-003", "amount": 250.0, "bank": "Bank A"},
            {"sender": None, "receiver": "ACC-099", "amount": 99.0, "bank": "Bank X"},
        ]
    )


def test_build_rows_drops_rows_with_missing_key(sample_df: pd.DataFrame):
    rows = DatasetIngesterAgent._build_rows(
        sample_df, key_col="sender", neo_id_prop="account_number",
        column_to_property={"bank": "bank_name"},
    )
    assert len(rows) == 3
    keys = [r["key"] for r in rows]
    assert keys == ["ACC-001", "ACC-002", "ACC-001"]


def test_build_rows_includes_properties(sample_df: pd.DataFrame):
    rows = DatasetIngesterAgent._build_rows(
        sample_df, key_col="sender", neo_id_prop="account_number",
        column_to_property={"bank": "bank_name"},
    )
    assert rows[0]["props"] == {"account_number": "ACC-001", "bank_name": "Bank A"}


def test_build_rows_skips_missing_property_values():
    df = pd.DataFrame([{"id": "X1", "name": "alpha"}, {"id": "X2", "name": None}])
    rows = DatasetIngesterAgent._build_rows(
        df, key_col="id", neo_id_prop="id", column_to_property={"name": "name"}
    )
    assert rows[0]["props"] == {"id": "X1", "name": "alpha"}
    assert rows[1]["props"] == {"id": "X2"}


def test_build_rel_rows_drops_rows_with_missing_either_side(sample_df: pd.DataFrame):
    rows = DatasetIngesterAgent._build_rel_rows(
        sample_df, s_col="sender", t_col="receiver",
        column_to_property={"amount": "amount"},
    )
    assert len(rows) == 3
    pairs = [(r["s"], r["t"]) for r in rows]
    assert ("ACC-001", "ACC-002") in pairs
    assert ("ACC-002", "ACC-003") in pairs
    assert all(s is not None for s, _ in pairs)


def test_build_rel_rows_includes_relationship_properties(sample_df: pd.DataFrame):
    rows = DatasetIngesterAgent._build_rel_rows(
        sample_df, s_col="sender", t_col="receiver",
        column_to_property={"amount": "amount"},
    )
    assert rows[0]["props"] == {"amount": 1000.0}


class _StubCounters:
    def __init__(self, nodes_created: int = 0, relationships_created: int = 0):
        self.nodes_created = nodes_created
        self.relationships_created = relationships_created


class _StubSummary:
    def __init__(self, counters: _StubCounters):
        self.counters = counters


class _StubResult:
    def __init__(self, counters: _StubCounters):
        self._counters = counters

    def consume(self) -> _StubSummary:
        return _StubSummary(self._counters)


class _StubTx:
    def __init__(self):
        self.run_calls: List[Dict[str, Any]] = []
        self._next_counters = _StubCounters()

    def queue_result(self, *, nodes_created: int = 0, relationships_created: int = 0):
        self._next_counters = _StubCounters(nodes_created, relationships_created)

    def run(self, cypher: str, **kwargs):
        self.run_calls.append({"cypher": cypher, "kwargs": kwargs})
        return _StubResult(self._next_counters)


def test_unwind_batches_one_call_per_node_label(sample_df: pd.DataFrame):
    tx = _StubTx()
    nm = NodeMapping(
        label="Account", id_column="sender", id_property="account_number",
        properties={"bank": "bank_name"},
    )
    rows = DatasetIngesterAgent._build_rows(sample_df, nm.id_column, nm.id_property, nm.properties)
    tx.queue_result(nodes_created=len(rows))
    tx.run(
        f"UNWIND $rows AS row MERGE (n:{nm.label} {{`{nm.id_property}`: row.key}}) SET n += row.props",
        rows=rows,
    )
    assert len(tx.run_calls) == 1
    assert "UNWIND $rows AS row" in tx.run_calls[0]["cypher"]
    assert tx.run_calls[0]["kwargs"]["rows"] == rows


def test_unwind_batches_one_call_per_relationship_type(sample_df: pd.DataFrame):
    tx = _StubTx()
    rm = RelationshipMapping(
        type="TRANSFERRED_TO",
        source_label="Account", source_id_column="sender", source_id_property="account_number",
        target_label="Account", target_id_column="receiver", target_id_property="account_number",
        properties={"amount": "amount"},
    )
    rows = DatasetIngesterAgent._build_rel_rows(
        sample_df, rm.source_id_column, rm.target_id_column, rm.properties
    )
    tx.queue_result(relationships_created=len(rows))
    tx.run(
        f"UNWIND $rows AS row "
        f"MATCH (source:{rm.source_label} {{`{rm.source_id_property}`: row.s}}) "
        f"MATCH (target:{rm.target_label} {{`{rm.target_id_property}`: row.t}}) "
        f"MERGE (source)-[r:{rm.type}]->(target) SET r += row.props",
        rows=rows,
    )
    assert len(tx.run_calls) == 1
    assert "MERGE (source)-[r:TRANSFERRED_TO]->(target)" in tx.run_calls[0]["cypher"]
