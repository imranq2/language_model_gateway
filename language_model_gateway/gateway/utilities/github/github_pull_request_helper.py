import asyncio
import logging
import re
from datetime import datetime
from logging import Logger
from typing import Dict, Optional, List, Union, Any
from urllib.parse import urlparse

import httpx
from httpx import Response

from language_model_gateway.gateway.utilities.github.github_pull_request import (
    GithubPullRequest,
)
from language_model_gateway.gateway.utilities.github.github_pull_request_per_contributor_info import (
    GithubPullRequestPerContributorInfo,
)


class GithubPullRequestHelper:
    def __init__(self, org_name: str, access_token: str):
        """
        Initialize GitHub PR Counter with async rate limit handling.

        Args:
            org_name (str): GitHub organization name
            access_token (str): GitHub Personal Access Token
        """
        self.logger: Logger = logging.getLogger(__name__)
        self.org_name = org_name
        self.github_access_token = access_token
        assert access_token, "GitHub access token is required"

        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AsyncGithubPullRequestHelper",
        }

    async def _get_rate_limit_info(self, client: httpx.AsyncClient) -> Dict[str, int]:
        """
        Retrieve and log GitHub API rate limit information.

        Returns:
            Dict[str, int]: Rate limit details
        """
        try:
            response = await client.get(
                f"{self.base_url}/rate_limit", headers=self.headers
            )
            response.raise_for_status()
            rate_limit_data = response.json()
            core_rate_limit = rate_limit_data["resources"]["core"]

            return {
                "remaining": core_rate_limit["remaining"],
                "reset_time": core_rate_limit["reset"],
            }
        except Exception as e:
            self.logger.error(f"Rate limit fetch error: {e}")
            raise

    async def _wait_for_rate_limit_reset(self, reset_time: int) -> None:
        """
        Async wait until rate limit resets.

        Args:
            reset_time (int): Timestamp when rate limit will reset
        """
        current_time = int(asyncio.get_event_loop().time())
        wait_time = max(reset_time - current_time + 5, 0)
        if wait_time > 0:
            self.logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds.")
            await asyncio.sleep(wait_time)

    async def retrieve_closed_prs(
        self,
        *,
        max_repos: Optional[int] = None,
        max_pull_requests: Optional[int] = None,
        min_created_at: Optional[datetime] = None,
        max_created_at: Optional[datetime] = None,
        include_merged: bool = True,
        repo_name: Optional[str] = None,
    ) -> List[GithubPullRequest]:
        """
        Async method to retrieve closed pull requests across organization repositories.
        """
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
            try:
                if repo_name:
                    repos_url = f"{self.base_url}/repos/{self.org_name}/{repo_name}"
                    repo_response = await client.get(
                        repos_url,
                        headers={
                            "Accept": "application/vnd.github+json",
                            **self.headers,
                        },
                    )
                    repo_response.raise_for_status()
                    repos = [repo_response.json()]
                else:
                    # Fetch organization repositories
                    repos_url = f"{self.base_url}/orgs/{self.org_name}/repos"
                    repos_response = await client.get(
                        repos_url,
                        headers={
                            "Accept": "application/vnd.github+json",
                            **self.headers,
                        },
                        params={
                            "type": "all",
                            "sort": "pushed",
                            "direction": "desc",
                            "per_page": 500,
                        },
                    )
                    repos_response.raise_for_status()
                    repos = repos_response.json()

                # Limit repositories if max_repos is specified
                repos = repos[:max_repos] if max_repos else repos

                closed_prs_list: List[GithubPullRequest] = []

                for repo in repos:
                    # Rate limit check
                    rate_info = await self._get_rate_limit_info(client)
                    if rate_info["remaining"] < 10:
                        await self._wait_for_rate_limit_reset(rate_info["reset_time"])

                    # Fetch closed PRs for the repository
                    prs_url = (
                        f"{self.base_url}/repos/{self.org_name}/{repo['name']}/pulls"
                    )
                    prs_response = await client.get(
                        prs_url,
                        params={
                            "state": "closed",
                            "sort": "created",
                            "direction": "desc",
                        },
                    )
                    prs_response.raise_for_status()
                    prs: List[Dict[str, Any]] = prs_response.json()

                    for pr_index, pr in enumerate(prs):
                        if max_pull_requests and pr_index >= max_pull_requests:
                            break

                        pr_created_at = datetime.fromisoformat(
                            pr["created_at"].replace("Z", "+00:00")
                        )

                        if min_created_at and pr_created_at < min_created_at:
                            break

                        if not max_created_at or pr_created_at <= max_created_at:
                            if (include_merged and pr.get("'merge_commit_sha'")) or pr[
                                "state"
                            ] == "closed":
                                closed_prs_list.append(
                                    GithubPullRequest(
                                        repo=repo["name"],
                                        title=pr["title"],
                                        closed_at=(
                                            datetime.fromisoformat(
                                                pr["closed_at"].replace("Z", "+00:00")
                                            )
                                            if pr["closed_at"]
                                            else None
                                        ),
                                        html_url=pr["html_url"],
                                        diff_url=pr["diff_url"],
                                        user=pr["user"]["login"],
                                    )
                                )

                return closed_prs_list

            except Exception as e:
                self.logger.error(f"Error retrieving PRs: {e}")
                raise

    # noinspection PyMethodMayBeStatic
    def summarize_prs_by_engineer(
        self, *, pull_requests: List[GithubPullRequest]
    ) -> Dict[str, GithubPullRequestPerContributorInfo]:
        """
        Summarize pull requests by engineer.

        Args:
            pull_requests (List[GithubPullRequest]): List of pull requests

        Returns:
            Dict[str, GithubPullRequestPerContributorInfo]: Summary of PRs by engineer
        """
        engineer_pr_counts: Dict[str, GithubPullRequestPerContributorInfo] = {}

        for pr in pull_requests:
            engineer = pr.user
            info = engineer_pr_counts.get(engineer)

            if info is None:
                engineer_pr_counts[engineer] = GithubPullRequestPerContributorInfo(
                    contributor=engineer,
                    pull_request_count=1,
                    repos=[pr.repo],
                )
            else:
                info.pull_request_count += 1
                if info.repos:
                    if pr.repo not in info.repos:
                        info.repos.append(pr.repo)
                else:
                    info.repos = [pr.repo]

        # Sort engineer_pr_counts by PR count
        return dict(
            sorted(
                engineer_pr_counts.items(),
                key=lambda item: item[1].pull_request_count,
                reverse=True,
            )
        )

    # noinspection PyMethodMayBeStatic
    def parse_pr_url(self, *, pr_url: str) -> Dict[str, Union[str, int]]:
        """
        Parse GitHub PR URL to extract repository and PR details.

        Args:
            pr_url (str): Full GitHub PR URL

        Returns:
            Dict containing owner, repo, and PR number

        Raises:
            ValueError: If URL is not a valid GitHub PR URL
        """
        parsed_url = urlparse(pr_url)

        # Support both github.com and GitHub Enterprise URLs
        hostname = parsed_url.hostname
        if not (
            hostname in ["github.com", "www.github.com"]
            or (hostname and hostname.endswith(".githubenterprise.com"))
        ):
            raise ValueError("Invalid GitHub URL")

        # Regex to match GitHub PR URL pattern
        match = re.match(r"/([^/]+)/([^/]+)/pull/(\d+)", parsed_url.path)

        if not match:
            raise ValueError("Invalid GitHub PR URL format")

        return {
            "owner": match.group(1),
            "repo": match.group(2),
            "pr_number": int(match.group(3)),
        }

    async def get_pr_diff_content(self, *, pr_url: str) -> str:
        """
        Async method to fetch the actual diff content for a given GitHub PR URL.

        Args:
            pr_url (str): Full GitHub PR URL

        Returns:
            str: The raw diff content of the PR
        """
        async with httpx.AsyncClient(headers=self.headers) as client:
            try:
                # Parse the PR URL
                pr_details: Dict[str, Any] = self.parse_pr_url(pr_url=pr_url)

                # Construct diff URL
                pr_url = f"{self.base_url}/repos/{pr_details['owner']}/{pr_details['repo']}/pulls/{pr_details['pr_number']}"
                headers: Dict[str, str] = {
                    "Authorization": f"Bearer {self.github_access_token}",
                    "Accept": "application/vnd.github.v3.diff",  # Specific media type for diff
                    "X-GitHub-Api-Version": "2022-11-28",  # Specify API version
                    "User-Agent": "AsyncGithubPullRequestHelper",
                }
                # Fetch PR details
                pr_response: Response = await client.get(
                    url=pr_url, headers=headers, follow_redirects=True
                )
                pr_response.raise_for_status()

                return pr_response.text

            except Exception as e:
                self.logger.error(f"Error fetching PR diff content: {e}")
                raise

    def export_results(
        self,
        *,
        pr_counts: Dict[str, GithubPullRequestPerContributorInfo],
        output_file: Optional[str] = None,
    ) -> None:
        """
        Export PR count results to console and optional file.

        Args:
            pr_counts (Dict[str, GithubPullRequestPerContributorInfo]): PR counts by engineer
            output_file (Optional[str]): Path to output file
        """
        # Print results to console
        self.logger.info("\n------ Closed PRs by Engineer ------\n")
        for engineer, info in pr_counts.items():
            self.logger.info(f"{engineer} | {info.pull_request_count} | {info.repos}")
        self.logger.info("\n------------------------------------\n")

        # Optional file export
        if output_file:
            try:
                with open(output_file, "w") as f:
                    f.write("Contributor\tPR Count\tRepos\n")
                    for engineer, info in pr_counts.items():
                        repos_text: str = " | ".join(info.repos) if info.repos else ""
                        f.write(
                            f"{engineer}\t{info.pull_request_count}\t{repos_text}\n"
                        )
                self.logger.info(f"Results exported to {output_file}")
            except IOError as e:
                self.logger.error(f"Failed to export results: {e}")
