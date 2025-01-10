import dataclasses
from datetime import datetime
from typing import Optional


@dataclasses.dataclass
class GithubPullRequest:
    repo: str
    user: str
    title: str
    closed_at: Optional[datetime]
    html_url: str
    diff_url: Optional[str]
