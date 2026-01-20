"""
Outputs Analyzer Module
Responsible for reading and parsing existing markdown result files
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import config


@dataclass
class ParsedPaper:
    """Parsed paper from markdown file"""
    title: str
    score: float
    arxiv_id: str
    published: str
    authors: List[str]
    categories: List[str]
    link: str
    score_reason: str
    abstract: str
    source_file: str  # Which md file this paper comes from
    topic: str  # Topic from the source file


@dataclass 
class ParsedResultFile:
    """Parsed result markdown file"""
    filepath: Path
    date: str
    topic: str
    count: int
    papers: List[ParsedPaper] = field(default_factory=list)
    
    @property
    def filename(self) -> str:
        return self.filepath.name


class OutputsAnalyzer:
    """Analyzer for outputs directory"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize the analyzer
        
        Args:
            output_dir: Output directory path
        """
        self.output_dir = output_dir or config.DEFAULT_OUTPUT_DIR
        self._cached_files: Dict[str, ParsedResultFile] = {}
        self._cache_timestamp: Optional[datetime] = None
    
    def list_result_files(self) -> List[Path]:
        """List all result markdown files in the output directory"""
        if not self.output_dir.exists():
            return []
        
        files = list(self.output_dir.glob("results_*.md"))
        # Sort by modification time, newest first
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return files
    
    def get_file_summaries(self) -> List[Dict]:
        """Get summary info for all result files"""
        summaries = []
        for filepath in self.list_result_files():
            try:
                parsed = self._parse_file_header(filepath)
                summaries.append({
                    "filename": filepath.name,
                    "filepath": str(filepath),
                    "date": parsed.get("date", "Unknown"),
                    "topic": parsed.get("topic", "Unknown"),
                    "count": parsed.get("count", 0),
                    "mtime": datetime.fromtimestamp(filepath.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
            except Exception:
                continue
        return summaries
    
    def _parse_file_header(self, filepath: Path) -> Dict:
        """Parse just the header of a markdown file"""
        result = {"date": "", "topic": "", "count": 0}
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read(2000)  # Read only first 2000 chars for header
        
        # Parse header info
        # Handle both English and Chinese headers
        date_match = re.search(r'\*\*(?:Date|日期)\*\*:\s*(.+)', content)
        if date_match:
            result["date"] = date_match.group(1).strip()
        
        topic_match = re.search(r'\*\*(?:Topic|主题)\*\*:\s*(.+)', content)
        if topic_match:
            result["topic"] = topic_match.group(1).strip()
        
        count_match = re.search(r'\*\*(?:Count|数量)\*\*:\s*(\d+)', content)
        if count_match:
            result["count"] = int(count_match.group(1))
        
        return result
    
    def parse_result_file(self, filepath: Path, max_papers: Optional[int] = None) -> ParsedResultFile:
        """
        Parse a result markdown file fully
        
        Args:
            filepath: Path to the markdown file
            max_papers: Maximum number of papers to parse (None for all)
            
        Returns:
            ParsedResultFile object
        """
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Parse header
        header = self._parse_file_header(filepath)
        
        result = ParsedResultFile(
            filepath=filepath,
            date=header.get("date", ""),
            topic=header.get("topic", ""),
            count=header.get("count", 0),
            papers=[]
        )
        
        # Split by paper sections (## N. Title)
        paper_sections = re.split(r'\n## \d+\.\s+', content)[1:]  # Skip header
        
        if max_papers:
            paper_sections = paper_sections[:max_papers]
        
        for section in paper_sections:
            paper = self._parse_paper_section(section, filepath, result.topic)
            if paper:
                result.papers.append(paper)
        
        return result
    
    def _parse_paper_section(self, section: str, source_file: Path, topic: str) -> Optional[ParsedPaper]:
        """Parse a single paper section"""
        lines = section.strip().split("\n")
        if not lines:
            return None
        
        title = lines[0].strip()
        
        # Extract fields
        score = 0.0
        arxiv_id = ""
        published = ""
        authors = []
        categories = []
        link = ""
        score_reason = ""
        abstract = ""
        
        # Handle both English and Chinese field names
        score_match = re.search(r'\*\*(?:Score|评分)\*\*:\s*([\d.]+)', section)
        if score_match:
            score = float(score_match.group(1))
        
        arxiv_match = re.search(r'\*\*ArXiv ID\*\*:\s*(\S+)', section)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
        
        pub_match = re.search(r'\*\*(?:Published|发布)\*\*:\s*(\S+)', section)
        if pub_match:
            published = pub_match.group(1)
        
        authors_match = re.search(r'\*\*(?:Authors|作者)\*\*:\s*(.+)', section)
        if authors_match:
            authors = [a.strip() for a in authors_match.group(1).split(",")]
        
        cat_match = re.search(r'\*\*(?:Categories|类别)\*\*:\s*(.+)', section)
        if cat_match:
            categories = [c.strip() for c in cat_match.group(1).split(",")]
        
        link_match = re.search(r'\*\*(?:Link|链接)\*\*:\s*(\S+)', section)
        if link_match:
            link = link_match.group(1)
        
        # Extract score reason
        reason_match = re.search(r'###\s*(?:Scoring Reason|评分原因)\s*\n(.+?)(?=\n###|\n---|\Z)', section, re.DOTALL)
        if reason_match:
            score_reason = reason_match.group(1).strip()
        
        # Extract abstract
        abstract_match = re.search(r'###\s*(?:Abstract|摘要)\s*\n(.+?)(?=\n###|\n---|\Z)', section, re.DOTALL)
        if abstract_match:
            abstract = abstract_match.group(1).strip()
        
        return ParsedPaper(
            title=title,
            score=score,
            arxiv_id=arxiv_id,
            published=published,
            authors=authors,
            categories=categories,
            link=link,
            score_reason=score_reason,
            abstract=abstract,
            source_file=source_file.name,
            topic=topic,
        )
    
    def load_all_papers(self, max_papers_per_file: Optional[int] = None) -> List[ParsedPaper]:
        """
        Load all papers from all result files
        
        Args:
            max_papers_per_file: Maximum papers to load per file
            
        Returns:
            List of all parsed papers
        """
        all_papers = []
        for filepath in self.list_result_files():
            try:
                result = self.parse_result_file(filepath, max_papers=max_papers_per_file)
                all_papers.extend(result.papers)
            except Exception:
                continue
        return all_papers
    
    def get_all_topics(self) -> List[str]:
        """Get all unique topics from result files"""
        topics = set()
        for filepath in self.list_result_files():
            try:
                header = self._parse_file_header(filepath)
                topic = header.get("topic", "")
                if topic:
                    topics.add(topic)
            except Exception:
                continue
        return list(topics)
    
    def search_papers(
        self,
        query: str,
        max_results: int = 20,
        search_in: str = "all",  # "title", "abstract", "all"
    ) -> List[ParsedPaper]:
        """
        Search papers across all result files
        
        Args:
            query: Search query
            max_results: Maximum results to return
            search_in: Where to search ("title", "abstract", "all")
            
        Returns:
            List of matching papers
        """
        query_lower = query.lower()
        all_papers = self.load_all_papers()
        
        matches = []
        for paper in all_papers:
            text_to_search = ""
            if search_in in ["title", "all"]:
                text_to_search += paper.title.lower() + " "
            if search_in in ["abstract", "all"]:
                text_to_search += paper.abstract.lower() + " "
            
            if query_lower in text_to_search:
                matches.append(paper)
                if len(matches) >= max_results:
                    break
        
        return matches
    
    def get_papers_by_topic(self, topic: str) -> List[ParsedPaper]:
        """Get all papers for a specific topic"""
        papers = []
        for filepath in self.list_result_files():
            try:
                header = self._parse_file_header(filepath)
                if topic.lower() in header.get("topic", "").lower():
                    result = self.parse_result_file(filepath)
                    papers.extend(result.papers)
            except Exception:
                continue
        return papers
    
    def build_context_for_llm(
        self,
        files: Optional[List[str]] = None,
        max_papers_per_file: int = 10,
        include_abstracts: bool = False,
    ) -> str:
        """
        Build a context string for LLM from result files
        
        Args:
            files: Specific files to include (None for all)
            max_papers_per_file: Max papers to include per file
            include_abstracts: Whether to include paper abstracts
            
        Returns:
            Context string for LLM
        """
        context_parts = []
        
        file_list = self.list_result_files()
        if files:
            file_list = [f for f in file_list if f.name in files]
        
        for filepath in file_list:
            try:
                result = self.parse_result_file(filepath, max_papers=max_papers_per_file)
                
                file_context = f"\n### File: {result.filename}\n"
                file_context += f"- Topic: {result.topic}\n"
                file_context += f"- Date: {result.date}\n"
                file_context += f"- Total Papers: {result.count}\n\n"
                file_context += "Papers:\n"
                
                for i, paper in enumerate(result.papers, 1):
                    file_context += f"\n{i}. **{paper.title}** (Score: {paper.score})\n"
                    file_context += f"   - ArXiv: {paper.arxiv_id}, Published: {paper.published}\n"
                    file_context += f"   - Categories: {', '.join(paper.categories)}\n"
                    if include_abstracts and paper.abstract:
                        # Truncate abstract
                        abstract_preview = paper.abstract[:300] + "..." if len(paper.abstract) > 300 else paper.abstract
                        file_context += f"   - Abstract: {abstract_preview}\n"
                
                context_parts.append(file_context)
            except Exception:
                continue
        
        return "\n".join(context_parts)
    
    def find_related_files(self, topic: str) -> List[Tuple[Path, float]]:
        """
        Find files related to a topic with relevance scores
        
        Args:
            topic: Topic to search for
            
        Returns:
            List of (filepath, relevance_score) tuples
        """
        topic_lower = topic.lower()
        topic_words = set(topic_lower.split())
        
        results = []
        for filepath in self.list_result_files():
            try:
                header = self._parse_file_header(filepath)
                file_topic = header.get("topic", "").lower()
                file_topic_words = set(file_topic.split())
                
                # Calculate relevance score
                if topic_lower in file_topic:
                    score = 1.0
                else:
                    # Jaccard similarity
                    intersection = len(topic_words & file_topic_words)
                    union = len(topic_words | file_topic_words)
                    score = intersection / union if union > 0 else 0.0
                
                if score > 0:
                    results.append((filepath, score))
            except Exception:
                continue
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# Global instance
_outputs_analyzer: Optional[OutputsAnalyzer] = None


def get_outputs_analyzer(output_dir: Optional[Path] = None) -> OutputsAnalyzer:
    """Get global outputs analyzer instance"""
    global _outputs_analyzer
    if _outputs_analyzer is None or (output_dir and _outputs_analyzer.output_dir != output_dir):
        _outputs_analyzer = OutputsAnalyzer(output_dir)
    return _outputs_analyzer
