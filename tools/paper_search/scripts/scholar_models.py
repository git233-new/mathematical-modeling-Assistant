"""Shared paper data models for the search adapters."""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Paper:
    title: str
    authors: List[str]
    publication_year: Optional[int]
    cited_by_count: int
    doi: Optional[str]
    abstract: Optional[str]
    source: str = "openalex"
    venue: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    first_page: Optional[str] = None
    last_page: Optional[str] = None
    url: Optional[str] = None

    @property
    def pages(self) -> Optional[str]:
        if self.first_page and self.last_page:
            return f"{self.first_page}-{self.last_page}"
        return self.first_page or self.last_page

    def to_dict(self) -> Dict:
        return {
            "title": self.title, "authors": self.authors,
            "publication_year": self.publication_year,
            "cited_by_count": self.cited_by_count, "doi": self.doi,
            "abstract": self.abstract, "venue": self.venue,
            "volume": self.volume, "issue": self.issue, "pages": self.pages,
            "url": self.url,
        }
