"""
Paper data model
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Paper:
    """Paper data class"""
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    published: datetime
    updated: datetime
    pdf_url: str
    arxiv_url: str
    
    # Interest scoring related
    interest_score: float = 0.0
    interest_reason: str = ""
    
    # Metadata
    primary_category: str = ""
    
    def __post_init__(self):
        if not self.primary_category and self.categories:
            self.primary_category = self.categories[0]
    
    def to_dict(self) -> dict:
        """Convert to dictionary format"""
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "categories": self.categories,
            "published": self.published.isoformat(),
            "updated": self.updated.isoformat(),
            "pdf_url": self.pdf_url,
            "arxiv_url": self.arxiv_url,
            "interest_score": self.interest_score,
            "interest_reason": self.interest_reason,
            "primary_category": self.primary_category,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Paper":
        """Create Paper object from dictionary"""
        return cls(
            arxiv_id=data["arxiv_id"],
            title=data["title"],
            abstract=data["abstract"],
            authors=data["authors"],
            categories=data["categories"],
            published=datetime.fromisoformat(data["published"]),
            updated=datetime.fromisoformat(data["updated"]),
            pdf_url=data["pdf_url"],
            arxiv_url=data["arxiv_url"],
            interest_score=data.get("interest_score", 0.0),
            interest_reason=data.get("interest_reason", ""),
            primary_category=data.get("primary_category", ""),
        )
    
    def short_summary(self) -> str:
        """Return a short summary of the paper"""
        authors_str = ", ".join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += f" et al. ({len(self.authors)} authors)"
        return f"[{self.arxiv_id}] {self.title}\n  Authors: {authors_str}\n  Categories: {', '.join(self.categories)}"
