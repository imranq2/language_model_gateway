import os
from os import makedirs, path
from pathlib import Path
from shutil import rmtree

from language_model_gateway.gateway.utilities.github.github_pull_request_helper import (
    GithubPullRequestHelper,
)


async def test_github_get_pull_request_diff() -> None:
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
        diff: str = await pr_counter.get_pr_diff_content(
            pr_url="https://github.com/icanbwell/language-model-gateway-configuration/pull/6/"
        )
        print(diff)

    except Exception as e:
        print(f"An error occurred: {e}")
