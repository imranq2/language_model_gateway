import pytest
@pytest.mark.httpx_mock(
    should_mock=lambda request: os.environ["RUN_TESTS_WITH_REAL_LLM"] != "1"
)