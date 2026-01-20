"""
Query Parser Module
Parses natural language queries to extract time range and topics
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from src.llm_client import get_llm_client, LLMClient
from src.time_parser import TimeParser


@dataclass
class ParsedQuery:
    """Parsed query result"""
    time_range: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    topic: Optional[str] = None
    has_time: bool = False
    has_topic: bool = False
    original_query: str = ""
    

class QueryParser:
    """Natural language query parser"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client
        self.time_parser = TimeParser()
    
    def _get_llm_client(self) -> LLMClient:
        """Get LLM client"""
        return self.llm_client or get_llm_client()
    
    def parse(self, query: str, history: list[str] = None) -> ParsedQuery:
        """
        Parse natural language query with context from history
        
        Args:
            query: User's natural language query
            history: List of previous queries in the conversation
            
        Returns:
            ParsedQuery object with extracted information
        """
        llm = self._get_llm_client()
        
        # Get current date for context
        now = datetime.now()
        current_date_str = now.strftime('%Y-%m-%d')
        current_day_str = now.strftime('%A')
        
        system_prompt = f"""You are an intelligent query parser for academic paper search. 
Today's date is: {current_date_str} ({current_day_str}).

Your task is to extract THREE separate pieces:
1. TIME: The original temporal expression (e.g., "最近三天", "last week").
2. START/END DATES: Calculate the exact dates based on "Today's date" in YYYY-MM-DD format.
3. TOPIC: Pure research subject (remove ALL non-research words).

🔴 CRITICAL FOR DATES:
- "today" -> start and end are both today's date ({current_date_str}).
- "last 3 days" or "过去三天" -> end is today, start is 2 days ago.
- "last week" or "最近一周" -> start is 7 days ago, end is today.
- "yesterday" -> start and end are both yesterday's date.
- If only a month is mentioned, use the full month range.

🔴 CRITICAL FOR CONTEXT:
- If the current query is incomplete (e.g., just "那最近三天呢" or "换成强化学习"), use the CONTEXT from previous queries to fill in missing pieces.

Return JSON:
{{
    "time_range": "<time expression or null>",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "topic": "<pure research keywords or null>",
    "has_time": <bool>,
    "has_topic": <bool>
}}
"""
        
        user_prompt = ""
        if history:
            user_prompt += "Context (previous queries):\n"
            for h in history:
                user_prompt += f"- {h}\n"
            user_prompt += "\n"
        
        user_prompt += f"Current query to parse: {query}" if query.strip() else "Empty query"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            response = llm.chat_json(messages, temperature=0.1)
            return ParsedQuery(
                time_range=response.get("time_range"),
                start_date=response.get("start_date"),
                end_date=response.get("end_date"),
                topic=response.get("topic"),
                has_time=response.get("has_time", False),
                has_topic=response.get("has_topic", False),
                original_query=query,
            )
        except (ConnectionError, PermissionError) as e:
            raise e
        except Exception as e:
            print(f"[Warning] LLM query parsing failed: {str(e)}")
            return ParsedQuery(original_query=query)


def parse_query(query: str) -> ParsedQuery:
    """Helper function to parse query"""
    parser = QueryParser()
    return parser.parse(query)
