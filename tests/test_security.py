from __future__ import annotations

import pytest

from agents.ingester import (
    IngestionSpec,
    NodeMapping,
    RelationshipMapping,
    UnsafeIdentifierError,
    _validate_label,
    _validate_property,
    _validate_rel_type,
    DatasetIngesterAgent,
)


def _make_spec(node_label: str = "Person",
               node_id_prop: str = "name",
               rel_type: str = "OWNER_OF") -> IngestionSpec:
    return IngestionSpec(
        nodes=[
            NodeMapping(
                label=node_label,
                id_column="name_col",
                id_property=node_id_prop,
                properties={"jurisdiction_col": "jurisdiction"},
            ),
            NodeMapping(
                label="Company",
                id_column="reg_col",
                id_property="registration_number",
                properties={},
            ),
        ],
        relationships=[
            RelationshipMapping(
                type=rel_type,
                source_label=node_label,
                source_id_column="name_col",
                source_id_property=node_id_prop,
                target_label="Company",
                target_id_column="reg_col",
                target_id_property="registration_number",
                properties={"pct_col": "percentage"},
            )
        ],
    )


@pytest.mark.parametrize("label", ["Person", "BankAccount", "Address1", "myLabel_v2"])
def test_validate_label_accepts_legit_labels(label):
    assert _validate_label(label) == label


@pytest.mark.parametrize("label", [
    "Person) DETACH DELETE n /*",
    "Person`;DELETE",
    "Person OR 1=1",
    "Person--",
    "1Numeric",
    "",
    None,
    "Person; MATCH (x) DELETE x",
    "Person Name With Space",
    "P" * 100,
])
def test_validate_label_rejects_unsafe(label):
    with pytest.raises(UnsafeIdentifierError):
        _validate_label(label)


@pytest.mark.parametrize("rt", ["OWNER_OF", "TRANSFERRED_MONEY_TO", "REGISTERED_AT", "HAS_BANK_ACCOUNT"])
def test_validate_rel_type_accepts_screaming_snake(rt):
    assert _validate_rel_type(rt) == rt


@pytest.mark.parametrize("rt", [
    "owner_of",
    "OWNER OF",
    "OWNER-OF",
    "OWNER]-(x)-[",
    "",
    "1_OWNS",
    None,
])
def test_validate_rel_type_rejects_unsafe(rt):
    with pytest.raises(UnsafeIdentifierError):
        _validate_rel_type(rt)


@pytest.mark.parametrize("prop", ["name", "tax_id", "registration_number", "_internal", "amount"])
def test_validate_property_accepts_snake_case(prop):
    assert _validate_property(prop) == prop


@pytest.mark.parametrize("prop", [
    "name`;DROP",
    "name OR 1=1",
    "1starts_with_digit",
    "name-with-dash",
    "name with space",
    "",
    None,
])
def test_validate_property_rejects_unsafe(prop):
    with pytest.raises(UnsafeIdentifierError):
        _validate_property(prop)


def test_validate_spec_rejects_injected_label():
    agent = DatasetIngesterAgent.__new__(DatasetIngesterAgent)
    spec = _make_spec(node_label="Person) DETACH DELETE n /*")
    with pytest.raises(UnsafeIdentifierError):
        agent.validate_spec(spec)


def test_validate_spec_rejects_injected_rel_type():
    agent = DatasetIngesterAgent.__new__(DatasetIngesterAgent)
    spec = _make_spec(rel_type="OWNER_OF]-(n) DELETE n /*")
    with pytest.raises(UnsafeIdentifierError):
        agent.validate_spec(spec)


def test_validate_spec_rejects_injected_property_name():
    agent = DatasetIngesterAgent.__new__(DatasetIngesterAgent)
    spec = _make_spec(node_id_prop="name`;DROP")
    with pytest.raises(UnsafeIdentifierError):
        agent.validate_spec(spec)


def test_validate_spec_passes_clean_input():
    agent = DatasetIngesterAgent.__new__(DatasetIngesterAgent)
    spec = _make_spec()
    agent.validate_spec(spec)
