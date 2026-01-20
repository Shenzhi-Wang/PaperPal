"""
Interest Scoring Module
Responsible for evaluating matching degree between papers and user interests
"""
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.paper import Paper
from src.llm_client import get_llm_client, LLMClient
from src.preference_manager import get_preference_manager, PreferenceManager
import config


class InterestScorer:
    """Interest Scorer"""
    
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        preference_manager: Optional[PreferenceManager] = None,
    ):
        """
        Initialize the scorer
        
        Args:
            llm_client: LLM client
            preference_manager: Preference manager
        """
        self.llm_client = llm_client
        self.preference_manager = preference_manager
    
    def _get_llm_client(self) -> LLMClient:
        """Get LLM client"""
        return self.llm_client or get_llm_client()
    
    def _get_preference_manager(self) -> PreferenceManager:
        """Get preference manager"""
        return self.preference_manager or get_preference_manager()
    
    def score_paper(
        self,
        paper: Paper,
        topic: Optional[str] = None,
        use_preferences: bool = True,
        lang: str = "en",
    ) -> Paper:
        """
        Score a single paper
        
        Args:
            paper: Paper object
            topic: User-specified interest topic
            use_preferences: Whether to use historical preferences
            lang: Preferred language for the reasoning ("en" or "zh")
            
        Returns:
            Paper object with score
        """
        llm = self._get_llm_client()
        pref_manager = self._get_preference_manager()
        
        # Build preference context
        preference_context = ""
        if use_preferences:
            preference_context = pref_manager.get_preference_summary()
        
        # Build prompts
        system_prompt = self._build_system_prompt(topic, preference_context, lang)
        user_prompt = self._build_user_prompt(paper)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            response = llm.chat_json(messages, temperature=0.3)
            paper.interest_score = float(response.get("score", 5.0))
            paper.interest_reason = response.get("reason", "")
        except (ConnectionError, PermissionError) as e:
            # Re-raise connection or permission errors to be handled by the caller
            raise e
        except Exception as e:
            paper.interest_score = 5.0
            paper.interest_reason = f"Scoring failed: {str(e)}"
        
        return paper
    
    def score_papers(
        self,
        papers: list[Paper],
        topic: Optional[str] = None,
        use_preferences: bool = True,
        max_workers: Optional[int] = None,
        progress_callback: Optional[callable] = None,
        lang: str = "en",
    ) -> list[Paper]:
        """
        Score papers in parallel
        
        Args:
            papers: List of papers
            topic: User-specified interest topic
            use_preferences: Whether to use historical preferences
            max_workers: Maximum parallel workers
            progress_callback: Progress callback function
            lang: Preferred language for reasoning
            
        Returns:
            List of papers with scores
        """
        scored_papers = []
        workers = max_workers or config.MAX_WORKERS
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    self.score_paper, paper, topic, use_preferences, lang
                ): paper
                for paper in papers
            }
            
            for i, future in enumerate(as_completed(futures)):
                try:
                    scored_paper = future.result()
                    scored_papers.append(scored_paper)
                except (ConnectionError, PermissionError) as e:
                    # Critical error: shutdown executor and re-raise
                    executor.shutdown(wait=False)
                    raise e
                except Exception as e:
                    original_paper = futures[future]
                    original_paper.interest_score = 5.0
                    original_paper.interest_reason = f"Scoring error: {str(e)}"
                    scored_papers.append(original_paper)
                
                if progress_callback:
                    progress_callback(i + 1, len(papers))
        
        return scored_papers

    def filter_papers_by_title(
        self,
        papers: list[Paper],
        topic: str,
        batch_size: int = 20,
        progress_callback: Optional[callable] = None,
        max_workers: Optional[int] = None,
    ) -> list[Paper]:
        """
        Coarse filter papers by title using LLM (loose matching).
        
        Args:
            papers: List of papers
            topic: User topic to match
            batch_size: Number of titles per LLM call
            progress_callback: Optional callback function(current, total)
            max_workers: Max threads
            
        Returns:
            Filtered list of papers
        """
        if not papers or not topic:
            return papers

        llm = self._get_llm_client()
        kept_indices = set()
        workers = max_workers or config.MAX_WORKERS

        system_prompt = """You are a paper screening assistant.
Given a topic and a list of paper titles, select the titles that are likely relevant.
Be inclusive: prefer to keep borderline cases rather than exclude them.

Return JSON:
{
  "keep_indices": [1, 2, 5, ...]  // 1-based indices from the provided list
}
"""

        def process_batch(start_idx):
            batch = papers[start_idx:start_idx + batch_size]
            titles_text = "\n".join(
                [f"{i+1}. {p.title}" for i, p in enumerate(batch)]
            )
            user_prompt = f"Topic: {topic}\n\nTitles:\n{titles_text}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            try:
                response = llm.chat_json(messages, temperature=0.2)
                indices = response.get("keep_indices", [])
                batch_kept = []
                for idx in indices:
                    if isinstance(idx, int) and 1 <= idx <= len(batch):
                        batch_kept.append(start_idx + idx - 1)
                return batch_kept
            except Exception:
                # Fallback: keep all titles in this batch if LLM fails
                return list(range(start_idx, start_idx + len(batch)))

        # Use ThreadPoolExecutor for parallel batch processing
        starts = list(range(0, len(papers), batch_size))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_start = {
                executor.submit(process_batch, start): start for start in starts
            }
            
            processed_count = 0
            for future in as_completed(future_to_start):
                batch_kept = future.result()
                for idx in batch_kept:
                    kept_indices.add(idx)
                
                processed_count += batch_size
                if progress_callback:
                    progress_callback(min(processed_count, len(papers)), len(papers))

        return [papers[i] for i in sorted(kept_indices)]
    
    def score_papers_batch(
        self,
        papers: list[Paper],
        topic: Optional[str] = None,
        use_preferences: bool = True,
        batch_size: int = 10,
        progress_callback: Optional[callable] = None,
        lang: str = "en",
    ) -> list[Paper]:
        """
        Score papers in batches (one API call for multiple papers)
        
        Args:
            papers: List of papers
            topic: User-specified interest topic
            use_preferences: Whether to use historical preferences
            batch_size: Batch size
            progress_callback: Progress callback function
            lang: Preferred language for reasoning
            
        Returns:
            List of papers with scores
        """
        llm = self._get_llm_client()
        pref_manager = self._get_preference_manager()
        
        # Build preference context
        preference_context = ""
        if use_preferences:
            preference_context = pref_manager.get_preference_summary()
        
        scored_papers = []
        total_batches = (len(papers) + batch_size - 1) // batch_size
        
        for batch_idx in range(0, len(papers), batch_size):
            batch = papers[batch_idx:batch_idx + batch_size]
            
            # Build batch scoring prompts
            system_prompt = self._build_batch_system_prompt(topic, preference_context, lang)
            user_prompt = self._build_batch_user_prompt(batch)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            
            try:
                response = llm.chat_json(messages, temperature=0.3, max_tokens=4000)
                scores = response.get("scores", [])
                
                for i, paper in enumerate(batch):
                    if i < len(scores):
                        paper.interest_score = float(scores[i].get("score", 5.0))
                        paper.interest_reason = scores[i].get("reason", "")
                    else:
                        paper.interest_score = 5.0
                        paper.interest_reason = "No score returned"
                    scored_papers.append(paper)
            except (ConnectionError, PermissionError) as e:
                # Re-raise critical errors
                raise e
            except Exception as e:
                for paper in batch:
                    paper.interest_score = 5.0
                    paper.interest_reason = f"Batch scoring failed: {str(e)}"
                    scored_papers.append(paper)
            
            if progress_callback:
                current_batch = batch_idx // batch_size + 1
                progress_callback(current_batch, total_batches)
        
        return scored_papers
    
    def _build_system_prompt(self, topic: Optional[str], preference_context: str, lang: str = "en") -> str:
        """Build system prompt"""
        lang_instruction = (
            "Provide explanation in Chinese (简体中文)."
            if lang == "zh"
            else "Provide explanation in English."
        )
        
        prompt = f"""You are an expert AI research paper evaluator. Your task is to evaluate the attractiveness of a paper to a user based on their interest preferences.

Scoring Criteria (0-10):
- 9-10: Perfect fit, a must-read for the user.
- 7-8: Relevant and worth paying attention to.
- 5-6: Some relevance, can be used as a reference.
- 3-4: Low relevance, not a primary focus.
- 0-2: Irrelevant or explicitly stated as not interested.

Please return the scoring result in JSON format:
{{
    "score": <float 0-10>,
    "reason": "<short explanation in { 'Chinese' if lang == 'zh' else 'English' }>"
}}

{lang_instruction}
"""
        
        if topic:
            prompt += f"\n\nUser's current focus topic: {topic}"
        
        if preference_context and preference_context != "No preference records found":
            prompt += f"\n\nUser's historical preferences:\n{preference_context}"
        
        return prompt
    
    def _build_user_prompt(self, paper: Paper) -> str:
        """Build user prompt"""
        return f"""Please evaluate the following paper:

Title: {paper.title}

Abstract: {paper.abstract}

Categories: {', '.join(paper.categories)}

Authors: {', '.join(paper.authors[:5])}{'...' if len(paper.authors) > 5 else ''}
"""
    
    def _build_batch_system_prompt(self, topic: Optional[str], preference_context: str, lang: str = "en") -> str:
        """Build batch scoring system prompt"""
        lang_instruction = (
            "Provide explanations in Chinese (简体中文)."
            if lang == "zh"
            else "Provide explanations in English."
        )
        
        prompt = f"""You are an expert AI research paper evaluator. Your task is to evaluate the attractiveness of multiple papers to a user based on their interest preferences.

Scoring Criteria (0-10):
- 9-10: Perfect fit, a must-read for the user.
- 7-8: Relevant and worth paying attention to.
- 5-6: Some relevance, can be used as a reference.
- 3-4: Low relevance, not a primary focus.
- 0-2: Irrelevant or explicitly stated as not interested.

Please return the scoring results for all papers in JSON format:
{{
    "scores": [
        {{"id": "<paper_index>", "score": <float 0-10>, "reason": "<short explanation in { 'Chinese' if lang == 'zh' else 'English' }>"}},
        ...
    ]
}}

{lang_instruction}
"""
        
        if topic:
            prompt += f"\n\nUser's current focus topic: {topic}"
        
        if preference_context and preference_context != "No preference records found":
            prompt += f"\n\nUser's historical preferences:\n{preference_context}"
        
        return prompt
    
    def _build_batch_user_prompt(self, papers: list[Paper]) -> str:
        """Build batch user prompt"""
        parts = ["Please evaluate the following papers:\n"]
        
        for i, paper in enumerate(papers, 1):
            parts.append(f"""
---
Paper {i}:
Title: {paper.title}
Abstract: {paper.abstract[:500]}{'...' if len(paper.abstract) > 500 else ''}
Categories: {', '.join(paper.categories)}
---
""")
        
        return "\n".join(parts)
    
    def parse_feedback(self, feedback_text: str, papers: list[Paper]) -> list[dict]:
        """
        Parse user's natural language feedback
        
        Args:
            feedback_text: User's feedback text
            papers: Current list of papers
            
        Returns:
            Parsed feedback dictionary
        """
        llm = self._get_llm_client()
        
        # Build paper list description
        paper_list = "\n".join([
            f"{i+1}. [{p.arxiv_id}] {p.title}"
            for i, p in enumerate(papers)
        ])
        
        system_prompt = """You are a feedback parsing assistant. Users will describe their thoughts on certain papers.
Please parse the user's feedback, identifying the paper indices they mentioned and the corresponding feedback type and reason.

Feedback Types:
- not_interested: Not interested
- interested: Interested
- neutral: Neutral

Please return in JSON format:
{
    "feedbacks": [
        {
            "paper_index": <int index starting from 1>,
            "feedback_type": "<feedback_type>",
            "reason": "<reason in English>"
        },
        ...
    ],
    "general_feedback": "<overall feedback description, if any>",
    "extracted_keywords": {
        "interested": ["<interested keywords in English>"],
        "not_interested": ["<not interested keywords in English>"]
    }
}
"""
        
        user_prompt = f"""Current Paper List:
{paper_list}

User Feedback: {feedback_text}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            response = llm.chat_json(messages, temperature=0.3)
            return response
        except Exception as e:
            return {"feedbacks": [], "general_feedback": str(e), "extracted_keywords": {}}


def sort_papers_by_interest(papers: list[Paper], descending: bool = True) -> list[Paper]:
    """Sort papers by interest score"""
    return sorted(papers, key=lambda p: p.interest_score, reverse=descending)


def filter_papers_by_threshold(
    papers: list[Paper],
    threshold: float = config.INTEREST_THRESHOLD,
) -> list[Paper]:
    """Filter papers below threshold"""
    return [p for p in papers if p.interest_score >= threshold]
