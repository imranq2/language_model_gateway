import logging
import os
from typing import Type, Optional, Tuple, Literal

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from language_model_gateway.gateway.utilities.github.github_pull_request_helper import (
    GithubPullRequestHelper,
)

logger = logging.getLogger(__name__)


class GitHubPullRequestDiffAgentDiffInput(BaseModel):
    """Input model for GitHub Pull Request extraction tool."""

    url: str = Field(
        ...,
        title="Pull Request URL",
        description="URL of the GitHub pull request to analyze",
    )


class GitHubPullRequestDiffTool(BaseTool):
    """
    LangChain-compatible tool for extracting and analyzing GitHub pull requests.
    """

    name: str = "github_pull_request_diff"
    description: str = "Provides a diff of a GitHub pull request given its URL"

    args_schema: Type[BaseModel] = GitHubPullRequestDiffAgentDiffInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    access_token: Optional[str]

    def _run(
        self,
        url: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Synchronous version of the tool (falls back to async implementation).

        Raises:
            NotImplementedError: Always raises to enforce async usage
        """
        raise NotImplementedError("Use async version of this tool")

    async def _arun(
        self,
        url: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Asynchronous version of the GitHub Pull Request extraction tool.

        Returns:
            Tuple of pull request analysis text and artifact description
        """

        assert self.access_token, "GitHub access token is required"

        assert url, "Pull request URL is required"

        try:
            # Initialize GitHub Pull Request Helper
            github_organization = os.environ.get("GITHUB_ORGANIZATION_NAME")
            assert (
                github_organization
            ), "GITHUB_ORGANIZATION_NAME environment variable is not set"

            gh_helper = GithubPullRequestHelper(
                org_name=github_organization, access_token=self.access_token
            )

            diff_content: str = await gh_helper.get_pr_diff_content(pr_url=url)
            # Create artifact description
            artifact = f"GitHubPullRequestDiffAgent: Downloaded diff for {url}"

            return diff_content, artifact

        except Exception as e:
            error_msg = f"Error analyzing GitHub pull requests: {str(e)}"
            error_artifact = "GitHubPullRequestDiffAgent: Analysis failed"
            logger.error(error_msg)
            return error_msg, error_artifact
