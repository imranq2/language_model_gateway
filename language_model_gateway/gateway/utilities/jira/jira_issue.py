import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass
class JiraIssue:
    key: str
    summary: str
    url: str
    status: str
    created_at: datetime
    closed_at: Optional[datetime] = None
    assignee: Optional[str] = None
    assignee_email: Optional[str] = None
    reporter: Optional[str] = None
    reporter_email: Optional[str] = None
    creator: Optional[str] = None
    creator_email: Optional[str] = None
    issue_type: Optional[str] = None
    project_name: Optional[str] = None
    project: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
