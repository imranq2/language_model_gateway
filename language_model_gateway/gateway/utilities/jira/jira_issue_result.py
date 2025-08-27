import dataclasses
from typing import List, Optional

from language_model_gateway.gateway.utilities.jira.jira_issue import JiraIssue


@dataclasses.dataclass
class JiraIssueResult:
    issues: List[JiraIssue]
    query: str
    error: Optional[str]
