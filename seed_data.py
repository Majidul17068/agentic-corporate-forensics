import os
import random
from datetime import datetime
from neo4j import GraphDatabase
from faker import Faker
from dotenv import load_dotenv

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")

fake = Faker()

def get_driver():
    try:
        driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
        driver.verify_connectivity()
        return driver
    except Exception as e:
        print(f"\n[!] Error connecting to Neo4j at {URI}.")
        print("    Ensure your Neo4j service is running (e.g. run 'docker-compose up -d').")
        print(f"    Details: {e}\n")
        raise e

def clear_database(session):
    print("Clearing database...")
    session.run("MATCH (n) DETACH DELETE n")

def create_constraints(session):
    print("Creating database constraints...")
    try:
        session.run("CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE")
        session.run("CREATE CONSTRAINT company_reg IF NOT EXISTS FOR (c:Company) REQUIRE c.registration_number IS UNIQUE")
        session.run("CREATE CONSTRAINT account_num IF NOT EXISTS FOR (b:BankAccount) REQUIRE b.account_number IS UNIQUE")
        session.run("CREATE CONSTRAINT address_full IF NOT EXISTS FOR (a:Address) REQUIRE a.full_address IS UNIQUE")
    except Exception as e:
        print(f"Constraint creation warning (some versions may require different syntax): {e}")

def seed_standard_data(session, num_people=30, num_companies=15):
    print(f"Seeding {num_people} Person nodes and {num_companies} Company nodes...")
    
    addresses = []
    for _ in range(15):
        addr = fake.address().replace('\n', ', ')
        country = fake.country()
        session.run(
            "CREATE (a:Address {full_address: $full_address, country: $country})",
            full_address=addr, country=country
        )
        addresses.append(addr)

    people_names = []
    for _ in range(num_people):
        name = fake.name()
        is_pep = random.random() < 0.1
        nationality = fake.country()
        role = "Politician" if is_pep else random.choice(["Executive", "Lawyer", "Accountant", "Entrepreneur"])
        session.run(
            """
            CREATE (p:Person {
                name: $name,
                tax_id: $tax_id,
                nationality: $nationality,
                role: $role,
                is_pep: $is_pep
            })
            """,
            name=name, tax_id=fake.ssn(), nationality=nationality, role=role, is_pep=is_pep
        )
        people_names.append(name)

    company_names = []
    for _ in range(num_companies):
        name = fake.company()
        reg_num = fake.uuid4()[:8].upper()
        jurisdiction = random.choice(["United States", "United Kingdom", "Germany", "Panama", "Cayman Islands", "BVI"])
        inc_date = fake.date_between(start_date='-15y', end_date='today').isoformat()
        session.run(
            """
            CREATE (c:Company {
                name: $name,
                registration_number: $reg_num,
                jurisdiction: $jurisdiction,
                incorporation_date: $inc_date
            })
            """,
            name=name, reg_num=reg_num, jurisdiction=jurisdiction, inc_date=inc_date
        )
        company_names.append(name)

        session.run(
            """
            MATCH (c:Company {name: $c_name}), (a:Address {full_address: $address})
            CREATE (c)-[:REGISTERED_AT]->(a)
            """,
            c_name=name, address=random.choice(addresses)
        )

    for p_name in people_names:
        if random.random() < 0.4:
            c_name = random.choice(company_names)
            session.run(
                """
                MATCH (p:Person {name: $p_name}), (c:Company {name: $c_name})
                CREATE (p)-[:DIRECTOR_OF {appointed_date: $date}]->(c)
                """,
                p_name=p_name, c_name=c_name, date=fake.date_between(start_date='-5y', end_date='today').isoformat()
            )
        
        if random.random() < 0.3:
            c_name = random.choice(company_names)
            session.run(
                """
                MATCH (p:Person {name: $p_name}), (c:Company {name: $c_name})
                CREATE (p)-[:OWNER_OF {ownership_percentage: $pct}]->(c)
                """,
                p_name=p_name, c_name=c_name, pct=random.randint(10, 100)
            )

    for i in range(len(company_names) // 2):
        c1 = company_names[i]
        c2 = random.choice(company_names)
        if c1 != c2:
            session.run(
                """
                MATCH (c1:Company {name: $c1}), (c2:Company {name: $c2})
                CREATE (c1)-[:SHAREHOLDER_IN {share_percentage: $pct}]->(c2)
                """,
                c1=c1, c2=c2, pct=random.randint(5, 49)
            )

    print("Seeding Bank Accounts and Transactions...")
    accounts = []
    for p_name in random.sample(people_names, k=num_people // 2):
        acc_num = fake.iban()
        bank_name = fake.bank()
        country = fake.country()
        session.run(
            """
            MATCH (p:Person {name: $p_name})
            CREATE (b:BankAccount {account_number: $acc_num, bank_name: $bank_name, country: $country})
            CREATE (p)-[:HAS_BANK_ACCOUNT]->(b)
            """,
            p_name=p_name, acc_num=acc_num, bank_name=bank_name, country=country
        )
        accounts.append(acc_num)

    for c_name in random.sample(company_names, k=num_companies // 2):
        acc_num = fake.iban()
        bank_name = fake.bank()
        country = fake.country()
        session.run(
            """
            MATCH (c:Company {name: $c_name})
            CREATE (b:BankAccount {account_number: $acc_num, bank_name: $bank_name, country: $country})
            CREATE (c)-[:HAS_BANK_ACCOUNT]->(b)
            """,
            c_name=c_name, acc_num=acc_num, bank_name=bank_name, country=country
        )
        accounts.append(acc_num)

    for _ in range(40):
        acc_from = random.choice(accounts)
        acc_to = random.choice(accounts)
        if acc_from != acc_to:
            session.run(
                """
                MATCH (b1:BankAccount {account_number: $from_acc}), (b2:BankAccount {account_number: $to_acc})
                CREATE (b1)-[:TRANSFERRED_MONEY {
                    amount: $amount,
                    currency: "USD",
                    timestamp: $time,
                    transaction_id: $tx_id
                }]->(b2)
                """,
                from_acc=acc_from, to_acc=acc_to,
                amount=round(random.uniform(500, 25000), 2),
                time=fake.date_time_between(start_date='-1y', end_date='now').isoformat(),
                tx_id=fake.uuid4()[:12]
            )

def inject_fraud_patterns(session):
    print("Injecting custom fraud networks / suspicious patterns...")
    
    print(" -> Injecting Pattern 1: Circular transfer loop involving Senator Charles Vance")
    
    session.run("CREATE (p:Person {name: 'Sen. Charles Vance', tax_id: '111-222-3333', nationality: 'United States', role: 'Politician', is_pep: true})")
    session.run("CREATE (c1:Company {name: 'Vance Holdings Ltd', registration_number: 'PAN-998822', jurisdiction: 'Panama', incorporation_date: '2023-04-12'})")
    session.run("CREATE (c2:Company {name: 'Aurora Consultant Services', registration_number: 'CAY-112233', jurisdiction: 'Cayman Islands', incorporation_date: '2024-01-15'})")
    
    session.run("CREATE (a1:Address {full_address: '10 Edificio Balboa, Panama City, Panama', country: 'Panama'})")
    session.run("CREATE (a2:Address {full_address: 'Suite 400, Harbour Centre, George Town, Cayman Islands', country: 'Cayman Islands'})")
    session.run("MATCH (c:Company {name: 'Vance Holdings Ltd'}), (a:Address {full_address: '10 Edificio Balboa, Panama City, Panama'}) CREATE (c)-[:REGISTERED_AT]->(a)")
    session.run("MATCH (c:Company {name: 'Aurora Consultant Services'}), (a:Address {full_address: 'Suite 400, Harbour Centre, George Town, Cayman Islands'}) CREATE (c)-[:REGISTERED_AT]->(a)")
    
    session.run("MATCH (p:Person {name: 'Sen. Charles Vance'}), (c:Company {name: 'Vance Holdings Ltd'}) CREATE (p)-[:OWNER_OF {ownership_percentage: 95}]->(c)")
    
    session.run("CREATE (b1:BankAccount {account_number: 'PAN-BANK-8899', bank_name: 'Banco de Panama', country: 'Panama'})")
    session.run("CREATE (b2:BankAccount {account_number: 'CAY-BANK-1122', bank_name: 'Cayman Merchant Bank', country: 'Cayman Islands'})")
    session.run("CREATE (b3:BankAccount {account_number: 'US-BANK-5566', bank_name: 'Freedom Bank USA', country: 'United States'})")
    
    session.run("MATCH (c:Company {name: 'Vance Holdings Ltd'}), (b:BankAccount {account_number: 'PAN-BANK-8899'}) CREATE (c)-[:HAS_BANK_ACCOUNT]->(b)")
    session.run("MATCH (c:Company {name: 'Aurora Consultant Services'}), (b:BankAccount {account_number: 'CAY-BANK-1122'}) CREATE (c)-[:HAS_BANK_ACCOUNT]->(b)")
    session.run("MATCH (p:Person {name: 'Sen. Charles Vance'}), (b:BankAccount {account_number: 'US-BANK-5566'}) CREATE (p)-[:HAS_BANK_ACCOUNT]->(b)")
    
    session.run("""
        MATCH (b1:BankAccount {account_number: 'PAN-BANK-8899'}), (b2:BankAccount {account_number: 'CAY-BANK-1122'})
        CREATE (b1)-[:TRANSFERRED_MONEY {amount: 500000.00, currency: 'USD', timestamp: '2025-10-10T14:30:00', transaction_id: 'TX-CIRC-001'}]->(b2)
    """)
    session.run("""
        MATCH (b1:BankAccount {account_number: 'CAY-BANK-1122'}), (b2:BankAccount {account_number: 'US-BANK-5566'})
        CREATE (b1)-[:TRANSFERRED_MONEY {amount: 475000.00, currency: 'USD', timestamp: '2025-10-12T09:15:00', transaction_id: 'TX-CIRC-002'}]->(b2)
    """)
    session.run("""
        MATCH (b1:BankAccount {account_number: 'US-BANK-5566'}), (b2:BankAccount {account_number: 'PAN-BANK-8899'})
        CREATE (b1)-[:TRANSFERRED_MONEY {amount: 250000.00, currency: 'USD', timestamp: '2025-11-01T11:00:00', transaction_id: 'TX-CIRC-003'}]->(b2)
    """)

    print(" -> Injecting Pattern 2: Hidden shell company beneficiary involving Minister Sophia Alster")
    
    session.run("CREATE (p:Person {name: 'Minister Sophia Alster', tax_id: '777-888-9999', nationality: 'Germany', role: 'Politician', is_pep: true})")
    session.run("CREATE (c_shell:Company {name: 'Apex Global Solutions Ltd', registration_number: 'BVI-883391', jurisdiction: 'British Virgin Islands', incorporation_date: '2022-08-19'})")
    session.run("CREATE (c_nominee:Company {name: 'Nominee Corporate Services Ltd', registration_number: 'BVI-992211', jurisdiction: 'British Virgin Islands', incorporation_date: '2018-02-10'})")
    session.run("CREATE (a_bvi:Address {full_address: 'Level 2, Coastal Building, Wickhams Cay, Road Town', country: 'British Virgin Islands'})")
    
    session.run("MATCH (c:Company {name: 'Apex Global Solutions Ltd'}), (a:Address {full_address: 'Level 2, Coastal Building, Wickhams Cay, Road Town'}) CREATE (c)-[:REGISTERED_AT]->(a)")
    session.run("MATCH (c:Company {name: 'Nominee Corporate Services Ltd'}), (a:Address {full_address: 'Level 2, Coastal Building, Wickhams Cay, Road Town'}) CREATE (c)-[:REGISTERED_AT]->(a)")
    
    session.run("MATCH (c1:Company {name: 'Nominee Corporate Services Ltd'}), (c2:Company {name: 'Apex Global Solutions Ltd'}) CREATE (c1)-[:SHAREHOLDER_IN {share_percentage: 99}]->(c2)")
    session.run("MATCH (p:Person {name: 'Minister Sophia Alster'}), (c:Company {name: 'Apex Global Solutions Ltd'}) CREATE (p)-[:BENEFICIAL_OWNER_OF {declared_date: '2022-08-20'}]->(c)")
    session.run("MATCH (p:Person {name: 'Minister Sophia Alster'}), (c:Company {name: 'Nominee Corporate Services Ltd'}) CREATE (p)-[:CONTROLS_VIA_PROXY {contract_id: 'PRX-9981'}]->(c)")

    print(" -> Injecting Pattern 3: Conflict of interest involving Marcus Sterling and Public Infrastructure Corp")
    
    session.run("CREATE (p:Person {name: 'Marcus Sterling', tax_id: '555-444-3333', nationality: 'United Kingdom', role: 'Executive', is_pep: false})")
    session.run("CREATE (c_pub:Company {name: 'Public Infrastructure Corp', registration_number: 'UK-772211', jurisdiction: 'United Kingdom', incorporation_date: '2015-06-30'})")
    session.run("CREATE (c_sup:Company {name: 'Sterling Supplier Corp', registration_number: 'UK-994411', jurisdiction: 'United Kingdom', incorporation_date: '2024-02-01'})")
    
    session.run("MATCH (p:Person {name: 'Marcus Sterling'}), (c:Company {name: 'Public Infrastructure Corp'}) CREATE (p)-[:DIRECTOR_OF {appointed_date: '2020-01-01'}]->(c)")
    session.run("MATCH (p:Person {name: 'Marcus Sterling'}), (c:Company {name: 'Sterling Supplier Corp'}) CREATE (p)-[:OWNER_OF {ownership_percentage: 100}]->(c)")
    
    session.run("CREATE (b_pub:BankAccount {account_number: 'UK-PUB-BANK', bank_name: 'Royal Bank of London', country: 'United Kingdom'})")
    session.run("CREATE (b_sup:BankAccount {account_number: 'UK-SUP-BANK', bank_name: 'Royal Bank of London', country: 'United Kingdom'})")
    
    session.run("MATCH (c:Company {name: 'Public Infrastructure Corp'}), (b:BankAccount {account_number: 'UK-PUB-BANK'}) CREATE (c)-[:HAS_BANK_ACCOUNT]->(b)")
    session.run("MATCH (c:Company {name: 'Sterling Supplier Corp'}), (b:BankAccount {account_number: 'UK-SUP-BANK'}) CREATE (c)-[:HAS_BANK_ACCOUNT]->(b)")
    
    session.run("""
        MATCH (b1:BankAccount {account_number: 'UK-PUB-BANK'}), (b2:BankAccount {account_number: 'UK-SUP-BANK'})
        CREATE (b1)-[:TRANSFERRED_MONEY {amount: 1500000.00, currency: 'GBP', timestamp: '2025-05-15T10:00:00', transaction_id: 'TX-CONFL-101'}]->(b2)
    """)

def main():
    print("Connecting to Neo4j database to seed mock corporate data...")
    try:
        driver = get_driver()
    except Exception:
        return
        
    with driver:
        with driver.session() as session:
            clear_database(session)
            create_constraints(session)
            seed_standard_data(session)
            inject_fraud_patterns(session)
            print("\nDatabase seeded successfully!")

if __name__ == "__main__":
    main()
