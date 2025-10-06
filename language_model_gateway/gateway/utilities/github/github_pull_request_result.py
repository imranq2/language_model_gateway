import dataclasses
from typing import List, Optional

from language_model_gateway.gateway.utilities.github.github_pull_request import (
    GithubPullRequest,
)


@dataclasses.dataclass
class GithubPullRequestResult:
    pull_requests: List[GithubPullRequest]
    query: str
    error: Optional[str]
