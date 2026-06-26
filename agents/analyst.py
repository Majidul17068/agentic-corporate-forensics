import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional

class AnalystEvaluation(BaseModel):
    analysis: str = Field(description="The detailed forensic analysis of the records returned so far.")
    red_flags: List[str] = Field(description="List of suspicious activity indicators found (if any).")
    requires_further_query: bool = Field(description="True if we need to query more data from the graph to fully answer or trace connections.")
    recommended_query: Optional[str] = Field(description="The natural language query describing what to search next (e.g. 'Search for who owns the bank account that received this transfer')")
    investigation_complete: bool = Field(description="True if we have enough information to form a conclusive finding, or if no connections exist.")

class ForensicAnalystAgent:
    def __init__(self):
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash"

    def analyze(self, user_query: str, last_cypher: str, graph_data: dict, schema_description: str) -> AnalystEvaluation:
        data_str = json.dumps(graph_data, indent=2)

        prompt = f"""
You are a Forensic Analyst Agent specializing in financial crimes, offshore secrecy, and corporate auditing.
Your task is to analyze the data retrieved from the graph database and determine if there are indicators of fraud or conflict of interest.
You must also decide whether we need to query the database further to follow paths, or if the investigation is complete.

Original User Query: "{user_query}"
Last Cypher Executed: "{last_cypher}"
Retrieved Data:
{data_str}

Database Schema Context:
{schema_description}

Guidelines for Analysis:
1. Examine relationships: Check if nodes connect through intermediate bank accounts, nominee companies, or shared addresses.
2. Flag offshore risks: Jurisdictions like Panama, BVI, Cayman Islands, Seychelles are red flags for shell companies.
3. Look for circular patterns: E.g., money moving from Entity A to Entity B to Entity C and back to Entity A.
4. Evaluate PEPs: Note if Politically Exposed Persons own companies or receive transfers.
5. Decide if more steps are needed: If you find a transfer or owner, do you need to trace who is behind them? If so, set `requires_further_query = true` and describe the `recommended_query` in natural language.
"""

        from agents.llm_helper import call_gemini_with_retry
        response = call_gemini_with_retry(
            self.client,
            "models.generate_content",
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AnalystEvaluation,
                temperature=0.1
            )
        )
        
        return AnalystEvaluation.model_validate_json(response.text.strip())
