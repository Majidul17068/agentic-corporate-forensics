import re
from google import genai
from google.genai import types

class CypherTranslatorAgent:
    def __init__(self):
        self.client = genai.Client()
        self.model_name = "gemini-2.5-flash"

    def translate(self, user_query: str, schema_description: str, conversation_history: list = None) -> str:
        history_str = ""
        if conversation_history:
            history_str = "\nConversation History:\n" + "\n".join(
                [f"{msg['role'].upper()}: {msg['content']}" for msg in conversation_history[-6:]]
            )

        prompt = f"""
You are a Cypher Translator Agent. Your job is to translate a user query into a Neo4j Cypher query.
You must use the following dynamic database schema to construct your queries.

Dynamic Neo4j Schema:
{schema_description}
{history_str}

User Query: "{user_query}"

Important Guidelines for Fuzzy/Robust Matching:
1. **Fuzzy Name Matching**: Always use case-insensitive `CONTAINS` when searching for names or text (e.g., use `toLower(p.name) CONTAINS toLower("Charles Vance")` or `toLower(p.name) CONTAINS "vance"`). Do NOT use exact equality `=` for names unless specifically instructed, as titles (e.g., "Sen. ", "Minister ") might be prefixed in the database.
2. **Avoid Hardcoded Role Filters**: Do not hardcode filters like `p.role = "Senator"` unless the query specifically wants to find only people with that exact role. If a user asks about "Senator Charles Vance", look for a person whose name contains "Charles Vance".
3. Output ONLY the Cypher query. Do not include markdown headers or greetings.
4. If returning a path, name it (e.g. `MATCH p = (a)-[*]->(b) RETURN p`).
5. Keep the queries simple, correct, and optimized for Neo4j.
6. Limit results (e.g., `LIMIT 25`) to prevent returning too many rows if the query is broad.
7. Wrap the Cypher block in ```cypher ... ``` code tags.
"""
        
        from agents.llm_helper import call_gemini_with_retry
        response = call_gemini_with_retry(
            self.client,
            "models.generate_content",
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1
            )
        )
        
        text = response.text.strip()
        match = re.search(r"```(?:cypher|neo4j)?\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        return text
