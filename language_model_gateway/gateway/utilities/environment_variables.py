import os
from typing import Optional


class EnvironmentVariables:
    @property
    def github_org(self) -> Optional[str]:
        return os.environ.get("GITHUB_ORG")

    @property
    def github_token(self) -> Optional[str]:
        return os.environ.get("GITHUB_TOKEN")