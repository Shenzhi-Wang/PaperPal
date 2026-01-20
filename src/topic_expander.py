"""
Topic Expander Module
Expands user queries into comprehensive search keywords using LLM
"""
from typing import Optional, List
from src.llm_client import get_llm_client, LLMClient


class TopicExpander:
    """Topic expander that converts short queries to comprehensive keywords"""
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client
    
    def _get_llm_client(self) -> LLMClient:
        """Get LLM client"""
        return self.llm_client or get_llm_client()
    
    def expand(self, topic: str, language: str = "en") -> tuple[str, List[str]]:
        """
        Expand a topic into comprehensive search keywords
        
        Args:
            topic: User's topic query (e.g., "RL", "LLM", "多模态学习", "的大模型论文")
            language: Language hint ("en" or "zh")
            
        Returns:
            Tuple of (cleaned_topic, list of expanded keywords)
        """
        if not topic or not topic.strip():
            return []
        
        llm = self._get_llm_client()
        
        system_prompt = """You are an academic search assistant. Given a research topic, your task is to:
1. Clean the topic (remove filler words like "的", "论文", "papers")
2. Expand it into comprehensive search keywords

CRITICAL: First identify the CORE research subject, then expand.

Rules:
1. Clean ALL filler/time words: 最近, 过去, 找, 的, 论文, 文章, recent, past, papers, articles
2. Include the cleaned core term(s)
3. Include full forms of acronyms
4. Include related technical terms and synonyms
5. Include common variations and spellings
6. Keep keywords concise (1-4 words each)
7. Return 5-10 keywords maximum
8. Focus on distinguishing terms

Return JSON:
{
    "cleaned_topic": "<pure research subject>",
    "keywords": ["keyword1", "keyword2", ...]
}

Examples:
- "RL" → {"cleaned_topic": "RL", "keywords": ["reinforcement learning", "RL", "policy gradient", "Q-learning"]}
- "的大模型论文" → {"cleaned_topic": "大模型", "keywords": ["large language model", "LLM", "大模型"]}
- "最近多模态学习" → {"cleaned_topic": "多模态学习", "keywords": ["multimodal learning", "多模态", "vision-language", "cross-modal"]}
- "LLM" → {"cleaned_topic": "LLM", "keywords": ["large language model", "LLM", "language model", "transformer"]}
- "多模态学习" → {"cleaned_topic": "多模态学习", "keywords": ["multimodal learning", "多模态", "vision-language", "cross-modal"]}
- "transformer papers" → {"cleaned_topic": "transformer", "keywords": ["transformer", "attention mechanism", "self-attention"]}
- "recent RAG" → {"cleaned_topic": "RAG", "keywords": ["retrieval augmented generation", "RAG", "retrieval-augmented"]}
"""
        
        user_prompt = f"Topic: {topic}\nLanguage hint: {language}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        try:
            response = llm.chat_json(messages, temperature=0.3)
            cleaned_topic = response.get("cleaned_topic", topic)
            keywords = response.get("keywords", [])
            
            # Fallback: if no keywords returned, use the cleaned topic
            if not keywords:
                keywords = [cleaned_topic]
            
            return (cleaned_topic, keywords[:10])  # Limit to 10 keywords
        except (ConnectionError, PermissionError) as e:
            # Re-raise critical errors
            raise e
        except Exception as e:
            # Fallback: use original topic if expansion fails
            return (topic, [topic])
    
    def expand_with_fallback(self, topic: str, language: str = "en") -> tuple[str, List[str]]:
        """
        Expand topic with simple fallback if LLM is unavailable
        
        Args:
            topic: User's topic query
            language: Language hint
            
        Returns:
            Tuple of (cleaned_topic, list of expanded keywords)
        """
        try:
            return self.expand(topic, language)
        except (ConnectionError, PermissionError) as e:
            # Critical error: re-raise
            raise e
        except Exception as e:
            # LLM expansion failed, use topic as-is
            print(f"[Warning] LLM keyword expansion failed: {str(e)}")
            return (topic, [topic])
    


# Global instance
_topic_expander: Optional[TopicExpander] = None


def get_topic_expander() -> TopicExpander:
    """Get global topic expander instance"""
    global _topic_expander
    if _topic_expander is None:
        _topic_expander = TopicExpander()
    return _topic_expander


def expand_topic(topic: str, language: str = "en") -> tuple[str, List[str]]:
    """Helper function to expand topic"""
    expander = get_topic_expander()
    return expander.expand_with_fallback(topic, language)
