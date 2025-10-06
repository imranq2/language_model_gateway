from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfluenceSearchResult:
    id: str
    title: str
    url: str
    updated_at: Optional[str] = None
    excerpt: Optional[str] = None
