from datetime import datetime, timezone
import os
from os import makedirs, path
from pathlib import Path
from shutil import rmtree
from typing import Dict, List

from language_model_gateway.gateway.utilities.github.github_pull_request import (
    GithubPullRequest,
)
from language_model_gateway.gateway.utilities.github.github_pull_request_helper import (
    GithubPullRequestHelper,
)
from language_model_gateway.gateway.utilities.github.github_pull_request_per_contributor_info import (
    GithubPullRequestPerContributorInfo,
)


async def test_github_get_summarized_pull_requests_from_one_repo() -> None:
    print()
    data_dir: Path = Path(__file__).parent.joinpath("./")
    temp_folder = data_dir.joinpath("./temp")
    if path.isdir(temp_folder):
        rmtree(temp_folder)
    makedirs(temp_folder)

    # Get credentials from environment variables
    org_name = "icanbwell"  # os.getenv('GITHUB_ORG')
    access_token = os.getenv("GITHUB_TOKEN")

    if not org_name or not access_token:
        raise ValueError("Please set GITHUB_ORG and GITHUB_TOKEN environment variables")

    # Initialize PR counter
    pr_counter = GithubPullRequestHelper(org_name, access_token)

    try:

        # Get PR counts with optional parameters
        pull_requests: List[GithubPullRequest] = await pr_counter.retrieve_closed_prs(
            max_repos=2,  # Optional: limit repositories
            max_pull_requests=200,  # Optional: limit PRs
            min_created_at=datetime(
                2024, 9, 1, tzinfo=timezone.utc
            ),  # Optional: minimum created date
            include_merged=True,  # Include merged PRs
            repo_name="helix.pipelines",
        )
        pr_counts: Dict[str, GithubPullRequestPerContributorInfo] = (
            pr_counter.summarize_prs_by_engineer(pull_requests=pull_requests)
        )

        # Export results
        pr_counter.export_results(
            pr_counts=pr_counts,
            output_file=str(
                temp_folder.joinpath("pr_counts.tsv")
            ),  # Optional TSV export
        )

    except Exception as e:
        print(f"An error occurred: {e}")
