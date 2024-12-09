import os
from typing import Tuple, Optional
from urllib.parse import urlparse, ParseResult


class UrlParser:
    @staticmethod
    def parse_s3_uri(uri: str) -> Tuple[str, str]:
        parsed = urlparse(uri)
        if parsed.scheme != "s3":
            raise ValueError(f"Invalid S3 URI scheme: {uri}")

        bucket = parsed.netloc
        path = parsed.path.lstrip("/")  # Remove leading slash

        return bucket, path

    @staticmethod
    def is_github_url(url: str) -> bool:
        parsed_url: ParseResult = urlparse(url)
        host: Optional[str] = parsed_url.hostname
        return host is not None and (
            host == "github.com" or host.endswith(".github.com")
        )

    @staticmethod
    def get_url_for_file_name(file_name: str) -> str:
        """
        Get the URL for a given image file name

        :return:
        """

        # get just the image file name
        image_generation_url = os.environ["IMAGE_GENERATION_URL"]
        url = f"{image_generation_url}/{file_name}"
        return url