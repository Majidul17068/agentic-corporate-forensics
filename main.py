import os
import argparse
from dotenv import load_dotenv
from agents.orchestrator import CollaborativeOrchestrator

load_dotenv()

def check_env():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        print("\n[!] Warning: GEMINI_API_KEY is not set or is still the default placeholder in .env.")
        print("    Please set your GEMINI_API_KEY in the .env file to enable Gemini translation and reporting.\n")

def run_pipeline(query: str):
    print(f"\n{'='*60}")
    print(f"Starting Multi-Agent GraphRAG Pipeline (CLI Mode)")
    print(f"User Query: '{query}'")
    print(f"{'='*60}")

    orchestrator = CollaborativeOrchestrator()
    try:
        logs = orchestrator.run_investigation(query)
        
        print("\n--- Agent Trace Logs ---")
        for log in logs:
            agent = log["agent"]
            msg = log["message"]
            data = log["data"]
            print(f"[{agent}] {msg}")
            if agent == "Translator" and "cypher" in data:
                print(f"  > Proposed Cypher: {data['cypher']}")
            elif agent == "Auditor" and "error" in data:
                print(f"  > [ERROR] {data['error']}")
            elif agent == "Auditor" and "records_count" in data:
                print(f"  > Records count: {data['records_count']}")
            elif agent == "Analyst" and "analysis" in data:
                print(f"  > Analysis summary: {data['analysis'][:120]}...")
                if data.get("red_flags"):
                    print(f"  > [RED FLAGS] {data['red_flags']}")
            elif agent == "Orchestrator" and "report" in data:
                print(f"\n{'='*60}")
                print(f"FINAL BRIEFING REPORT")
                print(f"{'='*60}\n")
                print(data["report"])
    except Exception as e:
        print(f"Investigation failed: {e}")

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Corporate Intelligence & Fraud Detection (GraphRAG)")
    parser.add_argument("--query", type=str, help="The natural language query to search for connections")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive CLI mode")
    args = parser.parse_args()

    check_env()

    if args.query:
        run_pipeline(args.query)
    elif args.interactive:
        print("\nWelcome to the Multi-Agent Corporate Intelligence CLI!")
        print("Type 'exit' or 'quit' to stop.\n")
        while True:
            try:
                query = input("\nEnter search query (e.g. 'Is there a connection between Sen. Charles Vance and Cayman Islands?'): ")
                if query.strip().lower() in ["exit", "quit"]:
                    break
                if not query.strip():
                    continue
                run_pipeline(query)
            except KeyboardInterrupt:
                break
    else:
        default_query = "Search for any circular payment transfers or loops involving Senator Charles Vance"
        run_pipeline(default_query)

if __name__ == "__main__":
    main()
