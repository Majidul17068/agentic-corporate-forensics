import os
import shutil
import pandas as pd
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
st.markdown("""
<style>
    /* Main Layout */
    .stApp {
        background-color: #0b0f19;
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers & Text */
    h1, h2, h3 {
        color: #38bdf8 !important;
        font-weight: 700 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    
    /* Chat Container styling */
    .stChatMessage {
        border-radius: 12px;
        margin-bottom: 12px;
        padding: 16px;
        border: 1px solid #1e293b;
    }
    
    .stChatMessage[data-testid="stChatMessageUser"] {
        background-color: #1e293b !important;
    }
    
    .stChatMessage[data-testid="stChatMessageAssistant"] {
        background-color: #0f172a !important;
        border-left: 4px solid #0ea5e9;
    }

    /* Status containers */
    .stStatusWidget {
        background-color: #111827 !important;
        border: 1px solid #374151 !important;
        border-radius: 8px !important;
    }
    
    /* Glassmorphism card utility */
    .glass-card {
        background: rgba(30, 41, 59, 0.4);
        border-radius: 16px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(5px);
        -webkit-backdrop-filter: blur(5px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 20px;
        margin-bottom: 20px;
    }
    
    /* Neon badges */
    .badge {
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        display: inline-block;
        margin-bottom: 8px;
    }
    .badge-pep {
        background-color: #ef4444;
        color: #ffffff;
    }
    .badge-offshore {
        background-color: #f59e0b;
        color: #ffffff;
    }
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
                        st.success(f"✓ Ingested `{file.name}`: Created {result['nodes_inserted']} nodes and {result['relationships_inserted']} edges.")
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
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if user_prompt := st.chat_input("Enter query (e.g. Find circular transfers involving Sen. Charles Vance)"):
    with st.chat_message("user"):
        st.markdown(user_prompt)
        
    st.session_state.messages.append({"role": "user", "content": user_prompt})

    with st.status("🔍 Agents Collaborating...", expanded=True) as status:
        orchestrator = CollaborativeOrchestrator()
        
        history_list = [{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.messages[:-1]]
        
        try:
            logs = orchestrator.run_investigation(user_prompt, history_list)
            
            for log in logs:
                agent = log["agent"]
                msg = log["message"]
                data = log["data"]
                
                if agent == "Orchestrator":
                    st.write(f"💬 **Orchestrator**: {msg}")
                elif agent == "Translator":
                    st.write(f"📝 **Translator Agent**: {msg}")
                    if "cypher" in data:
                        st.code(data["cypher"], language="cypher")
                elif agent == "Auditor":
                    if "error" in data:
                        st.error(f"❌ **Auditor Agent**: {msg} - `{data['error']}`")
                    else:
                        st.write(f"💻 **Auditor Agent**: {msg}")
                        if "records_count" in data:
                            st.caption(f"Retrieved {data['records_count']} raw records.")
                elif agent == "Analyst":
                    st.write(f"🕵️‍♂️ **Forensic Analyst Agent**: {msg}")
                    if "analysis" in data:
                        with st.expander("View Analyst Assessment", expanded=False):
                            st.write(data["analysis"])
                            if data.get("red_flags"):
                                st.warning(f"Red Flags Detected: {', '.join(data['red_flags'])}")
            
            report = ""
            for log in reversed(logs):
                if log["agent"] == "Orchestrator" and "report" in log.get("data", {}):
                    report = log["data"]["report"]
                    break
                    
            status.update(label="🕵️‍♂️ Investigation Complete!", state="complete", expanded=False)
            
            with st.chat_message("assistant"):
                st.markdown(report)
            st.session_state.messages.append({"role": "assistant", "content": report})
            
        except Exception as e:
            status.update(label="❌ Investigation Failed", state="error", expanded=True)
            st.error(f"An error occurred during multi-agent collaboration: {e}")
