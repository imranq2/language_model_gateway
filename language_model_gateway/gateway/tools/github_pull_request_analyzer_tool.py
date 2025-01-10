import logging
import os
from datetime import datetime
from typing import Type, Optional, List, Tuple, Literal

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from language_model_gateway.gateway.utilities.github.github_pull_request import (
    GithubPullRequest,
)
from language_model_gateway.gateway.utilities.github.github_pull_request_helper import (
    GithubPullRequestHelper,
)

logger = logging.getLogger(__name__)


class GitHubPullRequestAnalyzerAgentInput(BaseModel):
    """
    Input model for configuring GitHub Pull Request extraction and analysis.

    IMPORTANT LLM PARSING GUIDANCE:
    - When a query mentions a specific repository, extract the repository name exactly as written
    - When a query includes a GitHub username, extract it as the contributorName
    - Examples of parsing:
      * "What pull requests from imranq2 in helix.pipelines repo"
        -> repositoryName = "helix.pipelines"
        -> contributorName = "imranq2"
      * "Show pull requests for user johndoe in myorg/myrepo"
        -> repositoryName = "myorg/myrepo"
        -> contributorName = "johndoe"
      * "Pull requests in kubernetes/kubernetes by banzaicloud"
        -> repositoryName = "kubernetes/kubernetes"
        -> contributorName = "banzaicloud"

    Attributes:
        repositoryName (Optional[str]):
            Specific repository name to analyze.
            PARSING HINT: Directly use the repository name mentioned in the query.
            Can include organization prefix (e.g., "org/repo").
            Example: "helix.pipelines", "kubernetes/kubernetes"

        contributorName (Optional[str]):
            GitHub username to filter pull requests.
            PARSING HINT: Extract the GitHub username mentioned in the query.
            Example: "imranq2", "johndoe"

        # ... (rest of the attributes remain the same)
    """

    # IMPORTANT: Claude 3.5 Haiku 2024-10-22 has a bug where, when streaming, it changes parameter names to be camelCase
    # Hence use camelCase names for all parameters instead of snake_case

    repositoryName: Optional[str] = Field(
        default=None,
        description=(
            "Specific repository name to analyze. "
            "PARSING INSTRUCTION: Extract exact repository name from the query. "
        ),
    )
    contributorName: Optional[str] = Field(
        default=None,
        description=(
            "GitHub username to filter pull requests. "
            "PARSING INSTRUCTION: Extract GitHub username mentioned in the query."
        ),
    )
    minimumCreatedDate: Optional[datetime] = Field(
        default=None,
        # alias="minimumCreatedDate",
        description="Earliest date for pull request creation (inclusive)",
    )
    maximumCreatedDate: Optional[datetime] = Field(
        default=None,
        # alias="maximumCreatedDate",
        description="Latest date for pull request creation (inclusive)",
    )
    includeDetails: Optional[bool] = Field(
        default=False,
        # alias="includePullRequestDetails",
        description="Include detailed pull request information or return contributor summary",
    )


class GitHubPullRequestAnalyzerTool(BaseTool):
    """
    A LangChain-compatible tool for comprehensive GitHub pull request analysis.

    This tool provides advanced capabilities for extracting and analyzing
    pull request data from a GitHub organization. It supports:
    - Filtering pull requests by repository, date range, and contributor
    - Generating summary reports of pull request activity
    - Retrieving detailed pull request information

    Key Features:
    - Asynchronous pull request retrieval
    - Configurable analysis scope
    - Detailed or summarized reporting
    - Error handling and logging

    Requires:
    - GitHub access token
    - GITHUB_ORGANIZATION_NAME environment variable

    Example Usage:
    ```python
    tool = GitHubPullRequestAnalyzerTool(access_token='your_github_token')
    results, artifact = await tool._arun(
        repositoryName='my-project',
        minimumCreatedDate=datetime(2023, 1, 1),
        includeDetails=True
    )
    ```
    """

    name: str = "github_pull_request_analyzer"
    description: str = (
        "Advanced GitHub pull request analysis tool. "
        "USAGE TIPS: "
        "- Specify repository with 'in [repo]' "
        "- Specify contributor with username "
        "- Example queries: "
        "'Pull requests in kubernetes/kubernetes', "
        "'PRs from johndoe in myorg/myrepo', "
        "'What pull requests from imranq2 in helix.pipelines repo'"
    )

    args_schema: Type[BaseModel] = GitHubPullRequestAnalyzerAgentInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    access_token: Optional[str]

    # noinspection PyPep8Naming
    def _run(
        self,
        repositoryName: Optional[str] = None,
        minimumCreatedDate: Optional[datetime] = None,
        maximumCreatedDate: Optional[datetime] = None,
        contributorName: Optional[str] = None,
        includeDetails: Optional[bool] = None,
    ) -> Tuple[str, str]:
        """
        Synchronous version of the tool (falls back to async implementation).

        Raises:
            NotImplementedError: Always raises to enforce async usage
        """
        raise NotImplementedError("Use async version of this tool")

    # noinspection PyPep8Naming
    async def _arun(
        self,
        repositoryName: Optional[str] = None,
        minimumCreatedDate: Optional[datetime] = None,
        maximumCreatedDate: Optional[datetime] = None,
        contributorName: Optional[str] = None,
        includeDetails: Optional[bool] = None,
    ) -> Tuple[str, str]:
        """
        Asynchronous version of the GitHub Pull Request extraction tool.

        Returns:
            Tuple of pull request analysis text and artifact description
        """

        assert self.access_token, "GitHub access token is required"

        logger.info(
            "GitHubPullRequestAnalyzerAgent:"
            + f" {repositoryName=}, {minimumCreatedDate=}, {maximumCreatedDate=}"
            + f", {contributorName=}, {includeDetails=}"
        )

        log_prefix: str = (
            "GitHubPullRequestAnalyzerAgent:"
            + f" {repositoryName=}, {minimumCreatedDate=}, {maximumCreatedDate=}"
            + f", {contributorName=}, {includeDetails=}"
        )

        try:
            # Initialize GitHub Pull Request Helper
            github_organization = os.environ.get("GITHUB_ORGANIZATION_NAME")
            assert (
                github_organization
            ), "GITHUB_ORGANIZATION_NAME environment variable is not set"

            gh_helper = GithubPullRequestHelper(
                org_name=github_organization, access_token=self.access_token
            )

            # Retrieve closed pull requests
            max_repos: int = int(os.environ.get("GITHUB_MAXIMUM_REPOS", 100))
            max_pull_requests: int = int(
                os.environ.get("GITHUB_MAXIMUM_PULL_REQUESTS_PER_REPO", 100)
            )
            closed_prs: List[GithubPullRequest] = await gh_helper.retrieve_closed_prs(
                max_repos=max_repos,
                max_pull_requests=max_pull_requests,
                min_created_at=minimumCreatedDate,
                max_created_at=maximumCreatedDate,
                include_merged=True,
                repo_name=repositoryName,
            )

            full_text: str
            if includeDetails:
                full_text = ""
                for pr in closed_prs:
                    full_text += f"PR: {pr.title} by {pr.user} closed on {pr.closed_at} - {pr.html_url}\n"
            else:
                # Summarize pull requests by engineer
                pr_summary = gh_helper.summarize_prs_by_engineer(
                    pull_requests=closed_prs
                )

                # Generate detailed text report
                report_lines = [
                    "Pull Requests by Contributor:",
                ]

                for engineer, info in pr_summary.items():
                    report_lines.append(f"{engineer}: {info.pull_request_count}")

                full_text = "\n".join(report_lines)

            # Create artifact description
            artifact = log_prefix + f", Analyzed {len(closed_prs)} closed PRs"

            return full_text, artifact

        except Exception as e:
            error_msg = f"Error analyzing GitHub pull requests: {str(e)}"
            error_artifact = log_prefix + " Analysis Failed"
            logger.error(error_msg)
            return error_msg, error_artifact
