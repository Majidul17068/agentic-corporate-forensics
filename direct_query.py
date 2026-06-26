import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

def run_cypher(query: str, description: str):
    print(f"\n==================================================")
    print(f"🔍 Running: {description}")
    print(f"==================================================")
    try:
        with GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD)) as driver:
            with driver.session() as session:
                result = session.run(query)
                records = list(result)
                print(f"Result: {len(records)} records found.")
                for idx, record in enumerate(records[:10]):
                    print(f"\n[Record {idx+1}]")
                    for key, val in record.items():
                        print(f"  {key}: {val}")
                if len(records) > 10:
                    print(f"\n... and {len(records) - 10} more records.")
    except Exception as e:
        print(f"Error running query: {e}")

def main():
    print(f"Connecting to Neo4j at {URI}...")
    
    while True:
        print("\n--- Direct Forensic Graph Query Menu ---")
        print("1. Find Circular money laundering loops involving Senator Charles Vance")
        print("2. Find nominee companies & beneficial owners (Minister Sophia Alster)")
        print("3. Find conflicts of interest (Marcus Sterling & Supplier)")
        print("4. [SAML-D] Find Structuring/Smurfing transactions")
        print("5. [SAML-D] Find Cross-border laundering transactions")
        print("6. Exit")
        
        choice = input("\nEnter choice (1-6): ").strip()
        
        if choice == "1":
            query = """
            MATCH (senator:Person)
            WHERE toLower(senator.name) CONTAINS "charles vance"
            MATCH (senator)-[:HAS_BANK_ACCOUNT]->(personal:BankAccount)
            MATCH p = (personal)-[:TRANSFERRED_MONEY*2..4]->(personal)
            RETURN [n in nodes(p) | n.name] as PathNames, 
                   [n in nodes(p) | coalesce(n.name, n.account_number)] as PathDetails,
                   [r in relationships(p) | r.amount] as Amounts
            """
            run_cypher(query, "Charles Vance circular money laundering loops")
            
        elif choice == "2":
            query = """
            MATCH (pep:Person)-[:BENEFICIAL_OWNER_OF]->(shell:Company)
            OPTIONAL MATCH (nominee:Company)-[:SHAREHOLDER_IN]->(shell)
            OPTIONAL MATCH (pep)-[:CONTROLS_VIA_PROXY]->(nominee)
            RETURN pep.name as Politician, 
                   shell.name as ShellCompany, 
                   shell.jurisdiction as ShellJurisdiction, 
                   nominee.name as NomineeCompany,
                   nominee.jurisdiction as NomineeJurisdiction
            """
            run_cypher(query, "Offshore nominee structures and beneficial owners")
            
        elif choice == "3":
            query = """
            MATCH (dir:Person)-[:DIRECTOR_OF]->(c1:Company)-[:HAS_BANK_ACCOUNT]->(b1:BankAccount)
            MATCH (dir)-[:OWNER_OF]->(c2:Company)-[:HAS_BANK_ACCOUNT]->(b2:BankAccount)
            MATCH (b1)-[t:TRANSFERRED_MONEY]->(b2)
            RETURN dir.name as Director,
                   c1.name as MainCompany,
                   c2.name as SupplierCompanyOwnedByDirector,
                   t.amount as TransferAmount,
                   t.currency as Currency
            """
            run_cypher(query, "Corporate conflicts of interest and contractor transfers")
            
        elif choice == "4":
            query = """
            MATCH (sender)-[r:TRANSFERRED_MONEY]->(receiver)
            WHERE toLower(r.laundering_type) IN ['structuring', 'smurfing']
            RETURN coalesce(sender.name, sender.account_number) as Sender,
                   coalesce(receiver.name, receiver.account_number) as Receiver,
                   r.amount as Amount,
                   r.laundering_type as LaunderingType,
                   r.payment_type as PaymentType
            LIMIT 10
            """
            run_cypher(query, "Structuring or Smurfing transactions in SAML-D")
            
        elif choice == "5":
            query = """
            MATCH (sender)-[r:TRANSFERRED_MONEY]->(receiver)
            WHERE r.sender_bank_location <> r.receiver_bank_location AND r.is_laundering = 1
            RETURN coalesce(sender.name, sender.account_number) as Sender,
                   coalesce(receiver.name, receiver.account_number) as Receiver,
                   r.amount as Amount,
                   r.sender_bank_location as FromCountry,
                   r.receiver_bank_location as ToCountry,
                   r.laundering_type as Type
            LIMIT 10
            """
            run_cypher(query, "Cross-border money laundering transactions in SAML-D")
            
        elif choice == "6":
            print("Exiting...")
            break
        else:
            print("Invalid choice, please enter 1-6.")

if __name__ == "__main__":
    main()
