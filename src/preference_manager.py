"""
Preference Management Module
Responsible for managing user's interest preferences using natural language memory
"""

import json
import queue
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

import config

if TYPE_CHECKING:
    from src.llm_client import LLMClient

# Maximum length for preference memory (in characters)
MAX_MEMORY_LENGTH = 2000
# Target length after compression
TARGET_MEMORY_LENGTH = 1500


@dataclass
class QueryRecord:
    """Query record"""

    timestamp: str
    topic: str
    time_range: str
    results_count: int

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "QueryRecord":
        return cls(**data)


@dataclass
class FeedbackRecord:
    """Feedback record"""

    timestamp: str
    paper_id: str
    paper_title: str
    feedback_type: str
    feedback_reason: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FeedbackRecord":
        return cls(**data)


@dataclass
class Preferences:
    """User preferences data with natural language memory"""

    # Natural language preference memory - the core of the new system
    preference_memory: str = ""

    # Pending updates to be merged into memory (for batch processing)
    pending_updates: list[str] = field(default_factory=list)

    # Query history (kept for reference)
    query_history: list[QueryRecord] = field(default_factory=list)

    # Feedback history (kept for reference)
    feedback_history: list[FeedbackRecord] = field(default_factory=list)

    # UI Language
    language: Optional[str] = None

    # Search Mode ("keyword" or "exhaustive")
    search_mode: Optional[str] = None

    # Maximum workers
    max_workers: Optional[int] = None

    # Whether to save to local
    save_to_local: Optional[bool] = None

    # Output directory for results
    output_dir: Optional[str] = None

    # Whether to save results to file
    save_results: Optional[bool] = None

    # Maximum number of papers to display
    max_display: Optional[int] = None

    # Whether to auto-generate summary for search results
    auto_summary: Optional[bool] = None

    # ArXiv categories to search
    arxiv_categories: Optional[list[str]] = None

    # Last updated time
    last_updated: str = ""

    def to_dict(self) -> dict:
        return {
            "preference_memory": self.preference_memory,
            "pending_updates": self.pending_updates,
            "query_history": [q.to_dict() for q in self.query_history],
            "feedback_history": [f.to_dict() for f in self.feedback_history],
            "language": self.language,
            "search_mode": self.search_mode,
            "max_workers": self.max_workers,
            "save_to_local": self.save_to_local,
            "output_dir": self.output_dir,
            "save_results": self.save_results,
            "max_display": self.max_display,
            "auto_summary": self.auto_summary,
            "arxiv_categories": self.arxiv_categories,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Preferences":
        # Handle migration from old format
        preference_memory = data.get("preference_memory", "")

        # If old format exists but no new memory, migrate
        if not preference_memory:
            old_parts = []
            if data.get("interested_keywords"):
                old_parts.append(
                    f"Interested in: {', '.join(data['interested_keywords'])}"
                )
            if data.get("not_interested_keywords"):
                old_parts.append(
                    f"Not interested in: {', '.join(data['not_interested_keywords'])}"
                )
            if data.get("interested_topics"):
                old_parts.append(
                    f"Interested topics: {', '.join(data['interested_topics'])}"
                )
            if data.get("not_interested_topics"):
                old_parts.append(
                    f"Topics to avoid: {', '.join(data['not_interested_topics'])}"
                )
            if data.get("custom_preferences"):
                old_parts.append(data["custom_preferences"])
            preference_memory = " ".join(old_parts)

        return cls(
            preference_memory=preference_memory,
            pending_updates=data.get("pending_updates", []),
            query_history=[
                QueryRecord.from_dict(q) for q in data.get("query_history", [])
            ],
            feedback_history=[
                FeedbackRecord.from_dict(f) for f in data.get("feedback_history", [])
            ],
            language=data.get("language"),
            search_mode=data.get("search_mode"),
            max_workers=data.get("max_workers"),
            save_to_local=data.get("save_to_local"),
            output_dir=data.get("output_dir"),
            save_results=data.get("save_results"),
            max_display=data.get("max_display"),
            auto_summary=data.get("auto_summary"),
            arxiv_categories=data.get("arxiv_categories"),
            last_updated=data.get("last_updated", ""),
        )


class PreferenceManager:
    """Preference manager with natural language memory"""

    def __init__(self, preferences_file: Optional[Path] = None):
        self.preferences_file = preferences_file or config.PREFERENCES_FILE
        self.preferences = self._load_preferences()

        # Notification queue for background operations
        self._notification_queue: queue.Queue = queue.Queue()

        # Lock for thread-safe operations
        self._lock = threading.Lock()

    def _load_preferences(self) -> Preferences:
        """Load preferences from file"""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Preferences.from_dict(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Failed to load preference file ({e})")
        return Preferences()

    def save_preferences(self):
        """Save preferences to file"""
        with self._lock:
            self.preferences.last_updated = datetime.now().isoformat()
            # Ensure directory exists before writing
            preferences_path = Path(self.preferences_file)
            preferences_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.preferences_file, "w", encoding="utf-8") as f:
                json.dump(self.preferences.to_dict(), f, ensure_ascii=False, indent=2)

    # ===== Settings =====

    def set_language(self, language: str, save: bool = True):
        self.preferences.language = language
        if save:
            self.save_preferences()

    def get_language(self) -> Optional[str]:
        return self.preferences.language

    def set_search_mode(self, mode: str, save: bool = True):
        self.preferences.search_mode = mode
        if save:
            self.save_preferences()

    def get_search_mode(self) -> Optional[str]:
        return self.preferences.search_mode

    def set_max_workers(self, count: int, save: bool = True):
        self.preferences.max_workers = count
        if save:
            self.save_preferences()

    def get_max_workers(self) -> Optional[int]:
        return self.preferences.max_workers

    def set_save_to_local(self, value: bool, save: bool = True):
        self.preferences.save_to_local = value
        if save:
            self.save_preferences()

    def get_save_to_local(self) -> Optional[bool]:
        return self.preferences.save_to_local

    def set_output_dir(self, path: str, save: bool = True):
        """Set custom output directory"""
        self.preferences.output_dir = path
        if save:
            self.save_preferences()

    def get_output_dir(self) -> Optional[str]:
        """Get custom output directory"""
        return self.preferences.output_dir

    def set_save_results(self, value: bool, save: bool = True):
        """Set whether to save results to file"""
        self.preferences.save_results = value
        if save:
            self.save_preferences()

    def get_save_results(self) -> Optional[bool]:
        """Get whether to save results to file"""
        return self.preferences.save_results

    def set_max_display(self, value: Optional[int], save: bool = True):
        """Set maximum number of papers to display (None for unlimited)"""
        self.preferences.max_display = value
        if save:
            self.save_preferences()

    def get_max_display(self) -> Optional[int]:
        """Get maximum number of papers to display"""
        return self.preferences.max_display

    def set_auto_summary(self, value: bool, save: bool = True):
        """Set whether to auto-generate summary for search results"""
        self.preferences.auto_summary = value
        if save:
            self.save_preferences()

    def get_auto_summary(self) -> Optional[bool]:
        """Get whether to auto-generate summary for search results"""
        return self.preferences.auto_summary

    def set_arxiv_categories(self, categories: list[str], save: bool = True):
        """Set arXiv categories to search"""
        self.preferences.arxiv_categories = categories
        if save:
            self.save_preferences()

    def get_arxiv_categories(self) -> Optional[list[str]]:
        """Get arXiv categories to search"""
        return self.preferences.arxiv_categories

    # ===== History Management =====

    def add_query_record(
        self, topic: str, time_range: str, results_count: int, save: bool = True
    ):
        record = QueryRecord(
            timestamp=datetime.now().isoformat(),
            topic=topic,
            time_range=time_range,
            results_count=results_count,
        )
        self.preferences.query_history.append(record)
        if len(self.preferences.query_history) > 50:
            self.preferences.query_history = self.preferences.query_history[-50:]
        if save:
            self.save_preferences()

    def add_feedback(
        self,
        paper_id: str,
        paper_title: str,
        feedback_type: str,
        feedback_reason: str,
        save: bool = True,
    ):
        record = FeedbackRecord(
            timestamp=datetime.now().isoformat(),
            paper_id=paper_id,
            paper_title=paper_title,
            feedback_type=feedback_type,
            feedback_reason=feedback_reason,
        )
        self.preferences.feedback_history.append(record)
        if len(self.preferences.feedback_history) > 100:
            self.preferences.feedback_history = self.preferences.feedback_history[-100:]
        if save:
            self.save_preferences()

    # ===== Natural Language Memory =====

    def get_preference_context(self) -> str:
        """Get preference memory as context for LLM queries"""
        if self.preferences.preference_memory:
            return f"User Preferences:\n{self.preferences.preference_memory}"
        return ""

    def get_preference_summary(self) -> str:
        """Get preference summary (alias for get_preference_context)"""
        return self.preferences.preference_memory or "No preference records found"

    def add_preference_update(self, update_text: str, save: bool = True):
        """Add a new preference update to pending list"""
        if update_text and update_text.strip():
            self.preferences.pending_updates.append(update_text.strip())
            if save:
                self.save_preferences()

    def schedule_memory_update(
        self, new_info: str, on_complete: Optional[Callable[[str], None]] = None
    ):
        """
        Schedule a memory update to run in background.

        Args:
            new_info: New information to integrate into memory
            on_complete: Callback with notification message when done
        """
        if not new_info or not new_info.strip():
            return

        self.add_preference_update(new_info, save=True)

        def _run_update():
            try:
                from src.llm_client import get_llm_client

                llm = get_llm_client()
                result = self._process_memory_update(llm)
                if on_complete and result.get("notification"):
                    on_complete(result["notification"])
            except Exception:
                pass

        thread = threading.Thread(target=_run_update, daemon=True)
        thread.start()

    def _process_memory_update(self, llm_client: "LLMClient") -> dict:
        """Process pending updates and manage memory size"""
        with self._lock:
            pending = self.preferences.pending_updates.copy()
            self.preferences.pending_updates = []

        if not pending:
            return {"status": "no_updates"}

        current_memory = self.preferences.preference_memory
        new_info = "\n".join(pending)

        lang = self.preferences.language or "en"
        lang_instruction = (
            "Provide description in Chinese (简体中文)."
            if lang == "zh"
            else "Provide description in English."
        )

        # Build prompt for memory integration
        system_prompt = f"""You are a preference memory manager. Your task is to maintain a concise natural language description of a user's research interests and preferences.

RULES:
1. Integrate new information into existing memory
2. Resolve contradictions: newer info overrides older (e.g., if user now likes RAG but memory says they don't, update to like RAG)
3. Keep the description natural and readable
4. Be concise but comprehensive
5. Focus on: topics of interest, topics to avoid, preferred paper types, research areas

{lang_instruction}
Output ONLY the updated preference description, nothing else."""

        user_prompt = f"""Current memory:
{current_memory if current_memory else "(empty)"}

New information to integrate:
{new_info}

Output the updated preference description:"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = llm_client.chat(messages, temperature=0.3)
            new_memory = response.strip()

            notification = None

            # Check if memory needs compression
            if len(new_memory) > MAX_MEMORY_LENGTH:
                compress_result = self._compress_memory(llm_client, new_memory)
                new_memory = compress_result["memory"]
                notification = compress_result.get("notification")

            self.preferences.preference_memory = new_memory
            self.save_preferences()

            return {"status": "success", "notification": notification}
        except Exception as e:
            # Restore pending updates on failure
            with self._lock:
                self.preferences.pending_updates = (
                    pending + self.preferences.pending_updates
                )
            return {"status": "error", "message": str(e)}

    def _compress_memory(self, llm_client: "LLMClient", memory: str) -> dict:
        """Compress memory to fit within limits"""
        lang = self.preferences.language or "en"
        lang_instruction = (
            "Provide output in Chinese (简体中文)."
            if lang == "zh"
            else "Provide output in English."
        )

        system_prompt = f"""You are a memory compression assistant. The user's preference memory is too long and needs to be compressed.

RULES:
1. Keep the most important and recent preferences
2. Remove redundant or less important details
3. Maintain natural language flow
4. Target length: around {TARGET_MEMORY_LENGTH} characters
5. If you must remove something significant, note what category was trimmed

{lang_instruction}

Current length: {len(memory)} characters
Target: {TARGET_MEMORY_LENGTH} characters

Output format:
COMPRESSED_MEMORY:
<the compressed memory>

REMOVED_TOPICS (if any were removed):
<brief description of what was removed, or "None">"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Memory to compress:\n{memory}"},
        ]

        try:
            response = llm_client.chat(messages, temperature=0.2)

            # Parse response
            compressed = ""
            removed = ""

            if "COMPRESSED_MEMORY:" in response:
                parts = response.split("COMPRESSED_MEMORY:", 1)[1]
                if "REMOVED_TOPICS" in parts:
                    compressed, removed_part = parts.split("REMOVED_TOPICS", 1)
                    compressed = compressed.strip()
                    if ":" in removed_part:
                        removed = removed_part.split(":", 1)[1].strip()
                else:
                    compressed = parts.strip()
            else:
                compressed = response.strip()

            notification = None
            if removed and removed.lower() != "none":
                notification = f"🗜️ Memory compressed. Removed: {removed}"
            else:
                notification = "🗜️ Memory compressed to fit size limit."

            return {"memory": compressed, "notification": notification}
        except Exception:
            # Fallback: simple truncation
            truncated = memory[:TARGET_MEMORY_LENGTH]
            return {
                "memory": truncated,
                "notification": "🗜️ Memory truncated due to size limit.",
            }

    def clear_memory(self, save: bool = True):
        """Clear preference memory"""
        self.preferences.preference_memory = ""
        self.preferences.pending_updates = []
        if save:
            self.save_preferences()

    def clear_history(self, save: bool = True):
        """Clear history records"""
        self.preferences.query_history = []
        self.preferences.feedback_history = []
        if save:
            self.save_preferences()

    def clear_all(self, save: bool = True):
        """Clear all preferences"""
        self.preferences = Preferences()
        if save:
            self.save_preferences()

    # ===== Legacy compatibility =====

    def add_interested_keyword(self, keyword: str, save: bool = True):
        """Legacy method - now adds to pending updates"""
        if keyword and keyword.strip():
            self.add_preference_update(f"User is interested in: {keyword}")

    def add_not_interested_keyword(self, keyword: str, save: bool = True):
        """Legacy method - now adds to pending updates"""
        if keyword and keyword.strip():
            self.add_preference_update(f"User is NOT interested in: {keyword}")

    def add_interested_topic(self, topic: str, save: bool = True):
        """Legacy method - now adds to pending updates"""
        if topic and topic.strip():
            self.add_preference_update(f"User is interested in topic: {topic}")

    def add_not_interested_topic(self, topic: str, save: bool = True):
        """Legacy method - now adds to pending updates"""
        if topic and topic.strip():
            self.add_preference_update(f"User wants to avoid topic: {topic}")

    def set_custom_preferences(self, description: str, save: bool = True):
        """Legacy method - now adds to pending updates"""
        if description and description.strip():
            self.add_preference_update(description)

    def schedule_background_optimization(self):
        """Process pending updates in background"""

        def _run():
            try:
                from src.llm_client import get_llm_client

                llm = get_llm_client()
                self._process_memory_update(llm)
            except Exception:
                pass

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()


# Global instance
_preference_manager: Optional[PreferenceManager] = None


def get_preference_manager() -> PreferenceManager:
    """Get global preference manager instance"""
    global _preference_manager
    if _preference_manager is None:
        _preference_manager = PreferenceManager()
    return _preference_manager
