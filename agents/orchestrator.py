import os
from google import genai
from google.genai import types
from agents.translator import CypherTranslatorAgent
from agents.auditor import GraphAuditorAgent
from agents.analyst import ForensicAnalystAgent
from agents.schema_manager import get_schema_description

class CollaborativeOrchestrator:
    def __init__(self):
        self.translator = CypherTranslatorAgent()
        self.auditor = GraphAuditorAgent()
        self.analyst = ForensicAnalystAgent()
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash"

    def run_investigation(self, user_query: str, chat_history: list = None) -> list:
        logs = []
        schema_desc = get_schema_description()
        
        logs.append({
            "agent": "Orchestrator",
            "message": f"Starting investigation on query: '{user_query}'",
            "data": {"schema": schema_desc}
        })

        current_query = user_query
        max_turns = 3
        turn = 0
        all_retrieved_data = []

        while turn < max_turns:
            turn += 1
            logs.append({
                "agent": "Orchestrator",
                "message": f"--- Investigation Iteration {turn} ---",
                "data": {"iteration": turn}
            })

            logs.append({
                "agent": "Translator",
                "message": f"Translating question to Neo4j Cypher query...",
                "data": {"target_question": current_query}
            })
            
            cypher = self.translator.translate(current_query, schema_desc, chat_history)
            
            logs.append({
                "agent": "Translator",
                "message": f"Proposed Cypher Query.",
                "data": {"cypher": cypher}
            })

            auditor_result = self.auditor.execute_query(cypher)
            
            if auditor_result["status"] == "error":
                logs.append({
                    "agent": "Auditor",
                    "message": f"Cypher Execution Error! Notifying Translator for fix.",
                    "data": {"error": auditor_result["message"]}
                })
                
                correction_prompt = f"The previous Cypher query failed with this error: {auditor_result['message']}. Please fix the query."
                cypher = self.translator.translate(correction_prompt, schema_desc)
                
                logs.append({
                    "agent": "Translator",
                    "message": f"Proposed corrected Cypher Query.",
                    "data": {"cypher": cypher}
                })
                
                auditor_result = self.auditor.execute_query(cypher)

            if auditor_result["status"] == "error":
                logs.append({
                    "agent": "Auditor",
                    "message": f"Failed to execute query after correction. Aborting iteration.",
                    "data": {"error": auditor_result["message"]}
                })
                break

            records_count = auditor_result["records_count"]
            logs.append({
                "agent": "Auditor",
                "message": f"Successfully executed query. Retrieved {records_count} records.",
                "data": {
                    "records_count": records_count,
                    "records_preview": auditor_result["data"][:3]
                }
            })

            if records_count > 0:
                all_retrieved_data.extend(auditor_result["data"])

            logs.append({
                "agent": "Analyst",
                "message": "Analyzing graph records for compliance risks and indicators of fraud...",
                "data": {}
            })

            analyst_eval = self.analyst.analyze(
                user_query=user_query,
                last_cypher=cypher,
                graph_data=auditor_result["data"],
                schema_description=schema_desc
            )

            logs.append({
                "agent": "Analyst",
                "message": "Completed analysis evaluation.",
                "data": {
                    "analysis": analyst_eval.analysis,
                    "red_flags": analyst_eval.red_flags,
                    "requires_further_query": analyst_eval.requires_further_query,
                    "recommended_query": analyst_eval.recommended_query,
                    "investigation_complete": analyst_eval.investigation_complete
                }
            })

            if analyst_eval.investigation_complete or not analyst_eval.requires_further_query:
                logs.append({
                    "agent": "Orchestrator",
                    "message": "Analyst has concluded the investigation.",
                    "data": {}
                })
                break
            else:
                current_query = analyst_eval.recommended_query
                logs.append({
                    "agent": "Orchestrator",
                    "message": f"Analyst requested further query: '{current_query}'",
                    "data": {}
                })

        logs.append({
            "agent": "Orchestrator",
            "message": "Synthesizing full investigation trace and compiling final response...",
            "data": {}
        })

        synthesis_prompt = f"""
You are the Lead Investigator. Synthesize the findings of the agents into a clean, concise chat response for the user.
The user asked: "{user_query}"

Here is the accumulated information from the graph traversal and analysis:
{all_retrieved_data}

Write a direct, professional response answering their question and explicitly highlighting:
- The exact paths/connections found.
- Any compliance issues, fraud indicators, or red flags (e.g. offshore shells, circular transactions, PEP involvement).
- If no results were found, politely state that no matching connections were detected in the current dataset.

Keep it structured, clear, and direct.
"""
        from agents.llm_helper import call_gemini_with_retry
        response = call_gemini_with_retry(
            self.client,
            "models.generate_content",
            model=self.model_name,
            contents=synthesis_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )

        logs.append({
            "agent": "Orchestrator",
            "message": "Briefing compiled.",
            "data": {"report": response.text.strip()}
        })

        return logs
