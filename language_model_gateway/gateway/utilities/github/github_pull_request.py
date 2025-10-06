import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass
class GithubPullRequest:
    pull_request_number: str
    repo: str
    user: str
    title: str
    created_at: Optional[datetime]
    closed_at: Optional[datetime]
    updated_at: Optional[datetime]
    html_url: str
    diff_url: Optional[str]
    state: Optional[str]
    body: Optional[str]
