"""
Research Chat Module
Provides conversational interface for discussing and analyzing research papers
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config
from src.llm_client import LLMClient, get_llm_client
from src.outputs_analyzer import OutputsAnalyzer, ParsedPaper, get_outputs_analyzer


class ChatAction(Enum):
    """Types of actions the chat can take"""

    DISCUSS = "discuss"  # General discussion about papers
    ANALYZE_TRENDS = "analyze_trends"  # Analyze trends across papers
    FIND_CONNECTIONS = "find_connections"  # Find connections between topics
    CHECK_IDEA = "check_idea"  # Check if an idea has been explored
    SEARCH_PAPERS = "search_papers"  # Search for specific papers
    SUMMARIZE = "summarize"  # Generate a summary
    UNKNOWN = "unknown"


@dataclass
class ChatResponse:
    """Response from the research chat"""

    content: str  # The response text
    action: ChatAction  # What action was taken
    should_write: bool  # Whether to write to a file
    target_file: Optional[str]  # Target file to write to (None for new file)
    new_file_name: Optional[str]  # Suggested name for new file
    papers_referenced: List[str]  # ArXiv IDs of papers referenced
    needs_search: bool  # Whether a new search is needed
    search_query: Optional[str]  # Suggested search query if needs_search


class ResearchChat:
    """Research chat manager for discussing papers"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        outputs_analyzer: Optional[OutputsAnalyzer] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize the research chat

        Args:
            llm_client: LLM client
            outputs_analyzer: Outputs analyzer
            output_dir: Output directory
        """
        self.llm_client = llm_client
        self.outputs_analyzer = outputs_analyzer
        self.output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        self.conversation_history: List[Dict] = []
        self.context_papers: List[ParsedPaper] = []

    def _get_llm_client(self) -> LLMClient:
        """Get LLM client"""
        return self.llm_client or get_llm_client()

    def _get_outputs_analyzer(self) -> OutputsAnalyzer:
        """Get outputs analyzer"""
        return self.outputs_analyzer or get_outputs_analyzer(self.output_dir)

    def _classify_intent(self, query: str) -> Tuple[ChatAction, Dict]:
        """
        Classify the user's intent from their query

        Args:
            query: User's query

        Returns:
            Tuple of (action, extracted_info)
        """
        llm = self._get_llm_client()

        system_prompt = """You are an intent classifier for a research paper assistant.
Classify the user's query into one of these actions:
- discuss: General discussion or questions about papers
- analyze_trends: Analyze trends, patterns, or directions in research
- find_connections: Find connections or relationships between different topics
- check_idea: Check if a specific idea or approach has been explored
- search_papers: Need to search for new papers (not in existing results)
- summarize: Generate a summary or overview

Also extract relevant information from the query.

Return JSON:
{
    "action": "<action_type>",
    "topics": ["<relevant topics>"],
    "specific_idea": "<specific idea if check_idea>",
    "time_frame": "<time frame mentioned if any>",
    "needs_new_search": <boolean>,
    "search_query": "<suggested search query if needs new search>"
}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]

        try:
            result = llm.chat_json(messages, temperature=0.3)
            action_str = result.get("action", "discuss")
            action = (
                ChatAction(action_str)
                if action_str in [a.value for a in ChatAction]
                else ChatAction.DISCUSS
            )
            return action, result
        except Exception:
            return ChatAction.DISCUSS, {}

    def _decide_write_target(
        self,
        query: str,
        response_content: str,
        topics: List[str],
        referenced_files: List[str],
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Decide whether and where to write the response

        Args:
            query: Original user query
            response_content: The generated response
            topics: Topics discussed
            referenced_files: Files that were referenced

        Returns:
            Tuple of (should_write, target_file, new_file_name)
        """
        llm = self._get_llm_client()
        analyzer = self._get_outputs_analyzer()

        # Get list of existing files
        file_summaries = analyzer.get_file_summaries()
        files_info = "\n".join(
            [
                f"- {f['filename']}: Topic: {f['topic']}, Date: {f['date']}"
                for f in file_summaries[:10]
            ]
        )

        system_prompt = """You are helping decide where to save a research discussion.

Given the user's query, the response, and the list of existing files, decide:
1. Whether the response should be saved to a file
2. If saving, whether to append to an existing file or create a new one

Rules:
- If the discussion is within the scope of ONE existing file's topic, append to that file
- If the discussion spans multiple files/topics OR involves new search results, create a new file
- If the user explicitly specifies a file, use that file
- If it's just a quick question/answer, don't save

Return JSON:
{
    "should_write": <boolean>,
    "write_to_existing": <boolean>,
    "target_file": "<filename if writing to existing>",
    "new_file_name": "<suggested filename if creating new>",
    "reason": "<brief reason>"
}
"""

        user_prompt = f"""User Query: {query}

Referenced Files: {', '.join(referenced_files) if referenced_files else 'None'}

Existing Files:
{files_info}

Topics Discussed: {', '.join(topics)}

Response Length: {len(response_content)} characters
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = llm.chat_json(messages, temperature=0.3)
            should_write = result.get("should_write", False)
            write_to_existing = result.get("write_to_existing", False)
            target_file = result.get("target_file") if write_to_existing else None
            new_file_name = (
                result.get("new_file_name") if not write_to_existing else None
            )

            return should_write, target_file, new_file_name
        except Exception:
            return False, None, None

    def chat(
        self,
        query: str,
        include_files: Optional[List[str]] = None,
        lang: str = "en",
    ) -> ChatResponse:
        """
        Process a chat query about research papers

        Args:
            query: User's query
            include_files: Specific files to include in context
            lang: Language for response ("en" or "zh")

        Returns:
            ChatResponse object
        """
        llm = self._get_llm_client()
        analyzer = self._get_outputs_analyzer()

        # Classify intent
        action, intent_info = self._classify_intent(query)
        topics = intent_info.get("topics", [])
        needs_search = intent_info.get("needs_new_search", False)
        search_query = intent_info.get("search_query")

        # Build context from papers
        if include_files:
            context = analyzer.build_context_for_llm(
                files=include_files,
                max_papers_per_file=15,
                include_abstracts=True,
            )
            referenced_files = include_files
        else:
            # Auto-select relevant files based on topics
            context = analyzer.build_context_for_llm(
                max_papers_per_file=10,
                include_abstracts=True,
            )
            referenced_files = [f.name for f in analyzer.list_result_files()[:5]]

        # Build the prompt based on action
        system_prompt = self._build_system_prompt(action, lang)

        # Add conversation history
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self.conversation_history[-6:]:  # Keep last 6 messages
            messages.append(msg)

        # Add current query with context
        user_prompt = f"""Research Papers Context:
{context}

User Query: {query}

Please respond based on the papers in the context. If the query cannot be fully answered with the existing papers, suggest what additional search might be needed."""

        messages.append({"role": "user", "content": user_prompt})

        try:
            response = llm.chat(messages, temperature=0.7, max_tokens=4000)

            # Update conversation history
            self.conversation_history.append({"role": "user", "content": query})
            self.conversation_history.append({"role": "assistant", "content": response})

            # Decide write target
            should_write, target_file, new_file_name = self._decide_write_target(
                query, response, topics, referenced_files
            )

            # Extract referenced paper IDs
            arxiv_pattern = r"\b(\d{4}\.\d{4,5}(?:v\d+)?)\b"
            papers_referenced = list(set(re.findall(arxiv_pattern, response)))

            return ChatResponse(
                content=response,
                action=action,
                should_write=should_write,
                target_file=target_file,
                new_file_name=new_file_name,
                papers_referenced=papers_referenced,
                needs_search=needs_search,
                search_query=search_query,
            )
        except Exception as e:
            return ChatResponse(
                content=f"Error processing query: {str(e)}",
                action=ChatAction.UNKNOWN,
                should_write=False,
                target_file=None,
                new_file_name=None,
                papers_referenced=[],
                needs_search=False,
                search_query=None,
            )

    def _build_system_prompt(self, action: ChatAction, lang: str) -> str:
        """Build system prompt based on action type"""
        base_prompt = """You are an expert AI research assistant helping analyze and discuss academic papers.
You have access to the user's collected research papers from arXiv searches.

Your capabilities:
- Analyze trends and patterns across papers
- Find connections between different research topics
- Check if specific ideas have been explored
- Summarize research directions
- Answer questions about the papers

Guidelines:
- Be specific and cite paper titles or ArXiv IDs when relevant
- If the existing papers don't cover a topic, say so clearly
- Suggest new searches when the existing papers are insufficient
"""

        if lang == "zh":
            base_prompt += "\n\nPlease respond in Chinese (简体中文)."

        action_prompts = {
            ChatAction.DISCUSS: "\nFocus on providing informative discussion about the papers.",
            ChatAction.ANALYZE_TRENDS: "\nFocus on identifying trends, patterns, and research directions. Look for common themes, emerging approaches, and shifts in focus.",
            ChatAction.FIND_CONNECTIONS: "\nFocus on finding connections and relationships between different topics or papers. Identify how different research areas relate to each other.",
            ChatAction.CHECK_IDEA: "\nFocus on checking if the specific idea has been explored. Look for similar approaches, related work, and gaps that remain.",
            ChatAction.SEARCH_PAPERS: "\nHelp the user understand what to search for and suggest specific search queries.",
            ChatAction.SUMMARIZE: "\nProvide a comprehensive yet concise summary of the research papers.",
        }

        return base_prompt + action_prompts.get(action, "")

    def generate_summary(
        self,
        papers: List[ParsedPaper],
        topic: str,
        lang: str = "en",
        max_papers: int = 20,
    ) -> str:
        """
        Generate a summary/overview of papers

        Args:
            papers: List of papers to summarize
            topic: Topic of the papers
            lang: Language for summary
            max_papers: Maximum papers to include

        Returns:
            Summary text
        """
        llm = self._get_llm_client()

        # Sort by score and take top papers
        sorted_papers = sorted(papers, key=lambda p: p.score, reverse=True)[:max_papers]

        # Build paper context
        papers_context = ""
        for i, paper in enumerate(sorted_papers, 1):
            papers_context += f"""
{i}. **{paper.title}** (Score: {paper.score})
   ArXiv: {paper.arxiv_id}
   Abstract: {paper.abstract[:400]}...
"""

        lang_instruction = (
            "Respond in Chinese (简体中文)." if lang == "zh" else "Respond in English."
        )

        system_prompt = f"""You are an expert at writing research paper summaries.
Write a concise yet comprehensive summary of the following papers on "{topic}".

The summary should:
1. Provide an overview of the main research themes and directions
2. Highlight the most significant or innovative papers
3. Identify common approaches and methodologies
4. Note any emerging trends or open problems
5. Be well-structured with clear sections

{lang_instruction}
"""

        user_prompt = f"""Papers to summarize:
{papers_context}

Write a summary (approximately 500-800 words) that a researcher could read to quickly understand the state of this topic."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            summary = llm.chat(messages, temperature=0.5, max_tokens=2000)
            # Remove hard line breaks that are not paragraph breaks to improve terminal rendering
            return self._unwrap_text(summary)
        except Exception as e:
            return f"Error generating summary: {str(e)}"

    def _unwrap_text(self, text: str) -> str:
        """
        Merge lines that are separated by a single newline,
        preserving double newlines (paragraph breaks).
        """
        if not text:
            return ""

        # Split by double newlines to protect paragraph structure
        paragraphs = text.split("\n\n")
        unwrapped_paragraphs = []

        for p in paragraphs:
            # Replace single newlines within a paragraph with a space
            # But only if the line doesn't look like a list item or header
            lines = p.split("\n")
            new_lines = []
            current_line = ""

            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    continue

                # If it's a list item, header, or blockquote, don't merge it
                if re.match(r"^(\d+\.|[\-\*\+]|#|>)", line_stripped):
                    if current_line:
                        new_lines.append(current_line)
                    new_lines.append(line_stripped)
                    current_line = ""
                else:
                    if current_line:
                        # Add space between English words, but not between CJK characters
                        last_char = current_line[-1]
                        first_char = line_stripped[0]

                        # CJK character range check
                        def is_cjk(c):
                            return ord(c) >= 0x4E00 and ord(c) <= 0x9FFF

                        if is_cjk(last_char) and is_cjk(first_char):
                            current_line += line_stripped
                        else:
                            current_line += " " + line_stripped
                    else:
                        current_line = line_stripped

            if current_line:
                new_lines.append(current_line)

            unwrapped_paragraphs.append("\n".join(new_lines))

        return "\n\n".join(unwrapped_paragraphs)

    def write_to_file(
        self,
        content: str,
        target_file: Optional[str] = None,
        new_file_name: Optional[str] = None,
        section_title: Optional[str] = None,
    ) -> Path:
        """
        Write content to a file

        Args:
            content: Content to write
            target_file: Existing file to append to
            new_file_name: Name for new file
            section_title: Title for the new section

        Returns:
            Path to the written file
        """
        if target_file:
            # Append to existing file
            filepath = Path(os.path.join(str(self.output_dir), target_file))
            # Ensure directory exists before writing
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n\n---\n\n")
                if section_title:
                    f.write(f"## {section_title}\n\n")
                f.write(f"*Added: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")
                f.write(content)
            return filepath
        else:
            # Create new file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if new_file_name:
                # Sanitize filename
                safe_name = "".join(
                    c if c.isalnum() or c in "._-" else "_" for c in new_file_name
                )
                filename = f"chat_{safe_name}_{timestamp}.md"
            else:
                filename = f"chat_discussion_{timestamp}.md"

            filepath = Path(os.path.join(str(self.output_dir), filename))
            # Ensure directory exists before writing
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Research Discussion\n\n")
                f.write(
                    f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )
                f.write("---\n\n")
                if section_title:
                    f.write(f"## {section_title}\n\n")
                f.write(content)

            return filepath

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.context_papers = []


# Global instance
_research_chat: Optional[ResearchChat] = None


def get_research_chat(output_dir: Optional[Path] = None) -> ResearchChat:
    """Get global research chat instance"""
    global _research_chat
    if _research_chat is None or (
        output_dir and _research_chat.output_dir != output_dir
    ):
        _research_chat = ResearchChat(output_dir=output_dir)
    return _research_chat
