# Demo Guide — Multi-Agent Corporate Fraud Detection (GraphRAG)

## Run it

```bash
cd <repo>
source venv/bin/activate
streamlit run app.py
```
Opens at http://localhost:8501

**Re-seed the demo data any time (safe to re-run — it clears + rebuilds):**
```bash
./venv/bin/python seed_data.py
```

## Database

Neo4j AuraDB (cloud). All credentials live in `.env`, which is gitignored —
copy `.env.example` and fill it in.

NOTE: an Aura instance uses its instance id as BOTH the username and the
database name, not `neo4j`. Set `NEO4J_DATABASE` accordingly; `seed_data.py`
reads it.

Keep local and cloud configurations as `.env.*` files beside `.env`. Those are
gitignored too — never commit one, and never record a password here.

**Aura Free pauses after ~72h idle.** Before any demo: run the seed script (it proves the
connection works). If Aura is down, `cp .env.local.bak .env` and re-seed to run fully offline.

## The 4 planted fraud patterns (verified detectable)

### 1. Circular laundering loop — PEP
`Sen. Charles Vance` (Politically Exposed Person) owns 95% of **Vance Holdings Ltd** (Panama).
Money cycles: **Panama $500,000 -> Cayman $475,000 -> USA $250,000 -> back to Panama**.
Classic round-tripping through secrecy jurisdictions; value shrinks each hop (skimming).

### 2. Hidden beneficial ownership via nominee — PEP
`Minister Sophia Alster` is beneficial owner of **Apex Global Solutions Ltd** (BVI), but the
visible 99% shareholder is **Nominee Corporate Services Ltd** — which she controls via a proxy
contract (`PRX-9981`). Both companies share the same BVI address. Ownership deliberately obscured.

### 3. Conflict of interest / self-dealing
`Marcus Sterling` is a **director of Public Infrastructure Corp** and **100% owner of Sterling
Supplier Corp**. Public Infrastructure paid Sterling Supplier **GBP 1,500,000**. Undisclosed
related-party transaction.

### 4. Structuring / smurfing (AML)
**12 deposits of EUR 9,100–9,900 each** (all just under the 10,000 reporting threshold) from
12 disposable feeder accounts into `Costa Import Export SL` (owned by `Helena Vasquez`),
then a single **EUR 112,000 sweep out to the Panama account**. Total structured: ~EUR 113,700.

## Which dataset to use

**Main demo -> the graph already seeded in Aura.** Nothing to upload. Just run the app and ask
the questions below.

Optional extras in `datasets/` to show the CSV upload / schema-inference feature:

| File | Size | Use |
|---|---|---|
| `company_registry.csv` + `transaction_logs.csv` | 8 + 9 rows | Small mirrors of the same fraud story. Good for demoing the Ingester agent inferring nodes/edges from raw CSV. |
| `SAML-D-subset.csv` | **1,000 rows** | Public **SAML-D anti-money-laundering benchmark**. Has ground-truth labels: **103 confirmed laundering transactions** across 10 typologies — Structuring (49), Smurfing (10), Layered Fan-In (10), Cash Withdrawal (8), Behavioural Change (11), Scatter-Gather (6), Layered Fan-Out (5), Cycle (2), Fan-In (2). |

**Why SAML-D is the strongest closer:** because it is labelled, you can show the agents finding
laundering and then verify against ground truth — proof the answers are correct, not just plausible.

## Demo script — questions to ask the agents

1. **"Search for circular payment flows or money laundering loops involving Senator Charles Vance"**
   -> traces the Panama/Cayman/US cycle, flags the PEP + secrecy jurisdictions.

2. **"Who is the real beneficial owner of Apex Global Solutions Ltd, and are nominee companies involved?"**
   -> unwinds the nominee layer to Minister Sophia Alster.

3. **"Find conflicts of interest where a director of a company also owns a supplier receiving payments"**
   -> surfaces Marcus Sterling / GBP 1.5M.

4. **"Are there any structuring or smurfing patterns — many small deposits just under the reporting threshold?"**
   -> surfaces the 12 x ~EUR 9.5k deposits into Costa Import Export SL.

5. **"List all politically exposed persons connected to companies in offshore secrecy jurisdictions"**
   -> Vance (Panama) + Alster (BVI, two links).

## Talking points while it runs

- The **Translator** agent reads the live schema and writes Cypher — no hardcoded queries.
- The **Auditor** executes it; on a Cypher syntax error it feeds the error back for self-correction.
- The **Forensic Analyst** inspects results, flags red indicators (PEP, shell jurisdictions,
  cyclic funds) and can request follow-up queries — so it's iterative investigation, not one shot.
- The **Orchestrator** synthesizes the final report.
- Graph beats tables here: the fraud IS the *path* (3-hop cycle, nominee layer), which is
  expensive in SQL and natural in Cypher.

## Backup plan (do this before the demo)

Take screenshots / a short screen recording of each of the 5 questions answering correctly.
If the network or the Gemini API misbehaves live, you still have proof it works.
