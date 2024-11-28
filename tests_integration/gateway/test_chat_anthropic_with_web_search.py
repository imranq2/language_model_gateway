import logging
import os
from typing import Generator, AsyncGenerator, Optional

import httpx
import pytest
from openai import OpenAI
from starlette.testclient import TestClient

from language_model_gateway.gateway.api import app


@pytest.fixture
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# If you need a sync client for OpenAI
@pytest.fixture
def sync_client() -> Generator[httpx.Client, None, None]:
    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_chat_completions_with_web_search(
    async_client: httpx.AsyncClient, sync_client: httpx.Client
) -> None:
    # Get log level from environment variable
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Set up basic configuration for logging
    logging.basicConfig(level=getattr(logging, log_level))

    # Test health endpoint
    response = await async_client.get("/health")
    assert response.status_code == 200

    # init client and connect to localhost server
    client = OpenAI(
        api_key="fake-api-key",
        base_url="http://localhost:5000/api/v1",  # change the default port if needed
        http_client=sync_client,
    )

    # call API
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "Who won the last US election?",
            }
        ],
        model="General Purpose",
    )

    # print the top "choice"
    content: Optional[str] = chat_completion.choices[0].message.content
    assert content is not None
    print(content)
    assert "Trump" in content


@pytest.mark.asyncio
async def test_chat_completions_with_chat_history_and_web_search(
    async_client: httpx.AsyncClient, sync_client: httpx.Client
) -> None:

    # Test health endpoint
    response = await async_client.get("/health")
    assert response.status_code == 200

    # init client and connect to localhost server
    client = OpenAI(
        api_key="fake-api-key",
        base_url="http://localhost:5000/api/v1",  # change the default port if needed
        http_client=sync_client,
    )

    # call API
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "I want to talk about United States",
            },
            {"role": "assistant", "content": "Ok"},
            {
                "role": "user",
                "content": "who won the last election?",
            },
        ],
        model="General Purpose",
    )

    # print the top "choice"
    print("========  Response ======")
    print(chat_completion)
    print("====== End of Response ======")
    content: Optional[str] = chat_completion.choices[0].message.content
    assert content is not None
    print(content)
    assert "Trump" in content
