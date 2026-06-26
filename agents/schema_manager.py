import os
import json

SCHEMA_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "schema_cache.json")

BASE_SCHEMA_DESCRIPTION = """
Available Nodes:
- Person {name: String, tax_id: String, nationality: String, role: String, is_pep: Boolean}
- Company {name: String, registration_number: String, jurisdiction: String, incorporation_date: String}
- BankAccount {account_number: String, bank_name: String, country: String}
- Address {full_address: String, country: String}

Available Relationships:
- (:Person)-[:OWNER_OF {ownership_percentage: Integer}]->(:Company)
- (:Person)-[:DIRECTOR_OF {appointed_date: String}]->(:Company)
- (:Person)-[:HAS_BANK_ACCOUNT]->(:BankAccount)
- (:Company)-[:HAS_BANK_ACCOUNT]->(:BankAccount)
- (:BankAccount)-[:TRANSFERRED_MONEY {amount: Float, currency: String, timestamp: String, transaction_id: String}]->(:BankAccount)
- (:Person)-[:REGISTERED_AT]->(:Address)
- (:Company)-[:REGISTERED_AT]->(:Address)
- (:Company)-[:SHAREHOLDER_IN {share_percentage: Integer}]->(:Company)
- (:Person)-[:BENEFICIAL_OWNER_OF {declared_date: String}]->(:Company)
- (:Person)-[:CONTROLS_VIA_PROXY {contract_id: String}]->(:Company)
"""

def get_schema_description() -> str:
    schema_str = f"=== Base Schema ===\n{BASE_SCHEMA_DESCRIPTION}\n"
    
    if os.path.exists(SCHEMA_CACHE_PATH):
        try:
            with open(SCHEMA_CACHE_PATH, "r") as f:
                uploaded_schemas = json.load(f)
            
            if uploaded_schemas:
                schema_str += "\n=== Dynamically Uploaded Schemas ===\n"
                for filename, spec in uploaded_schemas.items():
                    schema_str += f"\nFile: {filename}\nNodes:\n"
                    for node in spec.get("nodes", []):
                        props_list = [f"{v} (from CSV: {k})" for k, v in node.get("properties", {}).items()]
                        schema_str += f"- {node.get('label')} {{key: {node.get('id_property')}, properties: {props_list}}}\n"
                    
                    schema_str += "Relationships:\n"
                    for rel in spec.get("relationships", []):
                        schema_str += f"- (:{rel.get('source_label')})-[r:{rel.get('type')}]->(:{rel.get('target_label')})\n"
        except Exception as e:
            print(f"Error loading schema cache: {e}")
            
    return schema_str

def add_uploaded_schema(filename: str, spec: dict):
    uploaded_schemas = {}
    if os.path.exists(SCHEMA_CACHE_PATH):
        try:
            with open(SCHEMA_CACHE_PATH, "r") as f:
                uploaded_schemas = json.load(f)
        except Exception:
            pass
            
    uploaded_schemas[filename] = spec
    
    os.makedirs(os.path.dirname(SCHEMA_CACHE_PATH), exist_ok=True)
    with open(SCHEMA_CACHE_PATH, "w") as f:
        json.dump(uploaded_schemas, f, indent=2)
