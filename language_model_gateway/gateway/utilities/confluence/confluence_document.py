from dataclasses import dataclass


@dataclass
class ConfluenceDocument:
    id: str
    title: str
    url: str
    updated_at: str
    author_name: str
    content: str
