import os
import shutil
import time
import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase

from agents.ingester import DatasetIngesterAgent
from agents.orchestrator import CollaborativeOrchestrator
from agents.schema_manager import get_schema_description, add_uploaded_schema

load_dotenv()

st.set_page_config(
    page_title="Multi-Agent Corporate Intelligence (GraphRAG)",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

AGENT_AVATARS = {
    "Orchestrator": "💬",
    "Translator": "📝",
    "Auditor": "💻",
    "Analyst": "🕵️",
}
AGENT_COLORS = {
    "Orchestrator": "#7dd3fc",
    "Translator": "#a78bfa",
    "Auditor": "#fbbf24",
    "Analyst": "#f87171",
}

st.markdown("""
<style>
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 8px;
        padding: 14px 16px;
        border: 1px solid #1e293b;
    }
    .stChatMessage[data-testid="stChatMessageUser"] {
        background-color: #1e293b !important;
    }
    .stChatMessage[data-testid="stChatMessageAssistant"] {
        background-color: #0f172a !important;
        border-left: 4px solid #0ea5e9;
    }
    .agent-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
    }
    .pill-orchestrator { background-color: rgba(125, 211, 252, 0.15); color: #7dd3fc; border: 1px solid rgba(125, 211, 252, 0.4); }
    .pill-translator   { background-color: rgba(167, 139, 250, 0.15); color: #a78bfa; border: 1px solid rgba(167, 139, 250, 0.4); }
    .pill-auditor      { background-color: rgba(251, 191, 36, 0.15);  color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.4); }
    .pill-analyst      { background-color: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.4); }
    .pill-final        { background-color: rgba(14, 165, 233, 0.15);  color: #0ea5e9; border: 1px solid rgba(14, 165, 233, 0.4); }
</style>
""", unsafe_allow_html=True)


def check_connections():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password123")
    api_key = os.getenv("GEMINI_API_KEY")

    neo4j_connected = False
    try:
        driver = GraphDatabase.driver(uri, auth=(username, password))
        driver.verify_connectivity()
        driver.close()
        neo4j_connected = True
    except Exception:
        pass

    gemini_configured = bool(api_key and api_key != "your_gemini_api_key_here" and api_key.strip() != "")
    return neo4j_connected, gemini_configured


def render_message(message: dict):
    role = message.get("role")
    if role == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
        return

    if role == "assistant":
        with st.chat_message("assistant"):
            st.markdown(
                '<span class="agent-pill pill-final">📋 Final Briefing</span>',
                unsafe_allow_html=True,
            )
            st.markdown(message["content"])
        return

    if role == "agent":
        agent = message.get("agent", "Agent")
        avatar = AGENT_AVATARS.get(agent, "🤖")
        with st.chat_message(agent.lower(), avatar=avatar):
            pill_class = f"pill-{agent.lower()}"
            st.markdown(
                f'<span class="agent-pill {pill_class}">{avatar} {agent} Agent</span>',
                unsafe_allow_html=True,
            )
            st.markdown(message["content"])
            data = message.get("data", {}) or {}
            if "cypher" in data and data["cypher"]:
                st.code(data["cypher"], language="cypher")
            if "error" in data and data["error"]:
                st.error(f"Cypher error: `{data['error']}`")
            if "records_count" in data:
                st.caption(f"📊 Retrieved {data['records_count']} record(s).")
            if "analysis" in data and data["analysis"]:
                with st.expander("View Analyst Assessment"):
                    st.write(data["analysis"])
                    if data.get("red_flags"):
                        st.warning(
                            "🚩 Red flags detected: " + ", ".join(data["red_flags"])
                        )
            if "iteration" in data:
                st.caption(f"🔁 Iteration #{data['iteration']}")


def log_to_message(log: dict) -> dict | None:
    agent = log.get("agent", "")
    msg = log.get("message", "")
    data = log.get("data", {}) or {}

    if agent == "Orchestrator" and "report" in data:
        return {"role": "assistant", "content": data["report"]}

    if not msg:
        return None

    return {
        "role": "agent",
        "agent": agent,
        "content": msg,
        "data": data,
    }


with st.sidebar:
    st.markdown("## 🕵️‍♂️ GraphRAG Control Panel")
    st.markdown("Configure datasets, inspect graph schemas, and track connections.")

    st.markdown("---")

    neo4j_ok, gemini_ok = check_connections()

    col1, col2 = st.columns(2)
    with col1:
        if neo4j_ok:
            st.success("🔌 Neo4j: OK")
        else:
            st.error("🔌 Neo4j: Error")
    with col2:
        if gemini_ok:
            st.success("🤖 Gemini: OK")
        else:
            st.error("🤖 Gemini: Key Missing")

    if not neo4j_ok or not gemini_ok:
        st.info("💡 Adjust connection variables in your `.env` file.")

    st.markdown("---")

    st.markdown("### 📊 Active Database Schema")
    schema_desc = get_schema_description()
    with st.expander("Show Schema Details", expanded=False):
        st.text(schema_desc)

    st.markdown("---")

    st.markdown("### 📥 Upload Your Dataset")
    st.markdown("Upload CSV logs of entities/transactions. Gemini will dynamically infer the node schema and edge definitions.")

    uploaded_files = st.file_uploader(
        "Select one or more CSV files",
        type=["csv"],
        accept_multiple_files=True
    )

    if uploaded_files:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)

        if st.button("🚀 Process & Ingest Files", use_container_width=True):
            ingester = DatasetIngesterAgent()
            progress_bar = st.progress(0)

            for idx, file in enumerate(uploaded_files):
                st.write(f"Analyzing `{file.name}`...")
                temp_path = os.path.join(temp_dir, file.name)

                with open(temp_path, "wb") as f:
                    shutil.copyfileobj(file, f)

                try:
                    result = ingester.ingest_csv(temp_path)
                    if result["status"] == "success":
                        add_uploaded_schema(file.name, result["spec"])
                        st.success(
                            f"✓ Ingested `{file.name}`: {result['nodes_inserted']} new nodes "
                            f"({result.get('nodes_processed', 0)} rows processed), "
                            f"{result['relationships_inserted']} new relationships."
                        )
                    else:
                        st.error(f"✗ Error: {result['message']}")
                except Exception as e:
                    st.error(f"✗ Exception in `{file.name}`: {e}")
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                progress_bar.progress((idx + 1) / len(uploaded_files))

            st.rerun()

    st.markdown("### ⚙️ DB Actions")
    if st.button("🧹 Clear Database & Cache", type="secondary", use_container_width=True):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        username = os.getenv("NEO4J_USERNAME", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password123")
        try:
            driver = GraphDatabase.driver(uri, auth=(username, password))
            with driver:
                with driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")

            cache_path = os.path.join(os.path.dirname(__file__), "schema_cache.json")
            if os.path.exists(cache_path):
                os.remove(cache_path)

            st.success("Database and schemas wiped!")
            st.rerun()
        except Exception as e:
            st.error(f"Clear failed: {e}")

st.title("Multi-Agent Corporate Intelligence & Fraud Detection")
st.markdown("Query transactional graphs or audit uploaded files for secrecy loops and hidden PEP relationships.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    render_message(message)

if user_prompt := st.chat_input("Enter query (e.g. Find circular transfers involving Sen. Charles Vance)"):
    user_msg = {"role": "user", "content": user_prompt}
    st.session_state.messages.append(user_msg)
    render_message(user_msg)

    history_list = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] in ("user", "assistant")
        and m is not user_msg
    ]

    spinner_slot = st.empty()
    spinner_slot.info("🔍 Agents collaborating — this typically takes 10–30 seconds...")

    try:
        orchestrator = CollaborativeOrchestrator()
        logs = orchestrator.run_investigation(user_prompt, history_list)
        spinner_slot.empty()

        for log in logs:
            msg_obj = log_to_message(log)
            if msg_obj is None:
                continue
            st.session_state.messages.append(msg_obj)
            render_message(msg_obj)
            time.sleep(0.35 if msg_obj["role"] == "agent" else 0)
    except Exception as e:
        spinner_slot.empty()
        st.error(f"An error occurred during multi-agent collaboration: {e}")
