import dataclasses
from typing import Optional, List


@dataclasses.dataclass
class GithubPullRequestPerContributorInfo:
    contributor: Optional[str]
    pull_request_count: int
    repos: Optional[List[str]]
