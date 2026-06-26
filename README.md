# Multi-Agent Corporate Intelligence & Fraud Detection (GraphRAG)

An agentic GraphRAG system designed to audit complex corporate networks, offshore secrecy jurisdictions, and transaction graphs to uncover hidden conflicts of interest, shell company ownerships, and money laundering paths. 

This project features:
1.  **Dynamic Dataset Uploader**: Upload any transactional or corporate CSV dataset. An Ingestion Agent uses Gemini to automatically infer node types, keys, and edge relationships, writing them dynamically into Neo4j.
2.  **Collaborative Agent-to-Agent Chat UI**: A beautiful Streamlit dashboard where specialized agents (Translator, Auditor, Analyst, and Orchestrator) debate and collaborate in real time, displaying their progress in an interactive trace before outputting the final report.
3.  **Local Test Datasets**: Comes pre-packaged with sample datasets to instantly test the ingestion quality and agent diagnostics.

---

## Agentic Collaboration Architecture

Rather than a linear pipeline, the chat console initiates a cooperative agent workspace:

```
                  ┌──────────────────────┐
                  │      User Query      │
                  └──────────┬───────────┘
                             │
                             ▼
               ┌───────────────────────────┐
               │    Orchestrator Agent     │ <── Initiates & guides investigation
               └──────┬──────────────▲─────┘
                      │              │
        Translate NL  │              │ Return Analysis &
        to Cypher     ▼              │ Next Query Requests
               ┌──────────────┐     ┌──────────────┐
               │  Translator  │     │   Forensic   │
               │    Agent     │     │   Analyst    │
               └──────┬───────┘     └──────────────┘
                      │ Cypher             ▲
                      ▼                    │ Inspect Path Data
               ┌──────────────┐            │ & Check Red Flags
               │Graph Auditor │────────────┘
               │    Agent     │
               └──────────────┘
                    Neo4j DB
```

1.  **Orchestrator**: Manages conversation history, triggers iterations, and synthesizes the final report.
2.  **Translator**: Inspects the active database schema (base + dynamically uploaded schemas) to write Cypher queries matching the user's inquiry.
3.  **Auditor**: Connects to Neo4j to execute Cypher queries. If a query has a syntax error, it returns details to the Translator for self-correction.
4.  **Forensic Analyst**: Analyzes retrieved records. It flags red indicators (PEPs, shell registries, cyclic funds) and requests follow-up queries if the path needs further tracing.

---

## Project Structure

```
corporate-intelligence-graphrag/
├── agents/                  # Multi-Agent framework
│   ├── ingester.py          # Schema inference & CSV loading
│   ├── translator.py        # Schema-aware Cypher generator
│   ├── auditor.py           # Neo4j query execution & serialization
│   ├── analyst.py           # Forensic risk assessment & path discovery
│   ├── schema_manager.py    # Combines static & dynamic graph schemas
│   └── orchestrator.py      # Main collaborative agent-to-agent runner
├── datasets/                # Sample CSV datasets for testing
│   ├── company_registry.csv
│   └── transaction_logs.csv
├── app.py                   # Streamlit Web App Interface
├── main.py                  # Command Line Interface (CLI mode)
├── seed_data.py             # Optional base database seeder
├── requirements.txt         # Project dependencies
├── docker-compose.yml       # Local Neo4j container launcher
└── README.md
```

---

## Setup Instructions

### 1. Prerequisite: Neo4j Setup
Choose between:
*   **Neo4j AuraDB (Recommended & Free Cloud)**: Go to [Neo4j Aura](https://neo4j.com/product/auradb/) and spin up a free instance. Take note of the connection URI (starts with `neo4j+s://`), the username (`neo4j`), and the password generated.
*   **Neo4j Desktop**: Install Neo4j Desktop locally and create a local database.
*   **Docker** (If available): Start a local Neo4j container:
    ```bash
    docker compose up -d
    ```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your details:
```bash
cp .env.example .env
```
Open `.env` and update:
```env
NEO4J_URI=bolt://localhost:7687  # Update if using AuraDB (e.g. neo4j+s://...)
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123      # Update with your database password
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Setup Python Virtual Environment & Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## How to Run & Test Quality

### 1. Start the Streamlit Web Application
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

### 2. Test Custom Upload Ingestion
*   In the sidebar under **Upload Your Dataset**, drag and drop the files located in the [datasets/](file:///Users/majidmurad/Desktop/research-lab/corporate-intelligence-graphrag/datasets) folder:
    *   [company_registry.csv](file:///Users/majidmurad/Desktop/research-lab/corporate-intelligence-graphrag/datasets/company_registry.csv)
    *   [transaction_logs.csv](file:///Users/majidmurad/Desktop/research-lab/corporate-intelligence-graphrag/datasets/transaction_logs.csv)
*   Click **Process & Ingest Files**. The Ingestion Agent will parse the columns, upload the nodes/edges, and display the new schema details.

### 3. Start Chatting with the Agent Team
In the chat input, ask questions to trace loops and flag fraud:
*   *Query*: `"Search for circular payment flows or loops involving Senator Charles Vance"`
*   *Query*: `"Who is the beneficial owner of Apex Global Solutions Ltd, and are there nominee companies involved?"`
*   *Query*: `"Find any conflicts of interest where a director of a company also owns the supplier company receiving funds"`

The agents will display their step-by-step thinking process in the collapsible status trace on-screen!
