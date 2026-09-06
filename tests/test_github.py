"""Tests for GitHubClient — all HTTP calls are mocked with respx.

No real network call to api.github.com happens here, and no real
GITHUB_TOKEN is needed to run these tests.
"""

import httpx
import pytest
import respx

from ai_code_reviewer.github.client import GitHubClient

OWNER = "some-owner"
REPO = "some-repo"
PR_NUMBER = 42


@pytest.fixture
def client() -> GitHubClient:
    return GitHubClient(token="fake-token-for-tests")


@pytest.mark.asyncio
@respx.mock
async def test_get_pull_request_returns_metadata(client: GitHubClient):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json={"number": PR_NUMBER, "title": "Fix bug", "state": "open"},
        )
    )

    pr = await client.get_pull_request(OWNER, REPO, PR_NUMBER)

    assert pr["number"] == PR_NUMBER
    assert pr["title"] == "Fix bug"


@pytest.mark.asyncio
@respx.mock
async def test_get_pull_request_diff_returns_raw_text(client: GitHubClient):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"
    fake_diff = "diff --git a/file.py b/file.py\n+print('hello')\n"
    respx.get(url).mock(return_value=httpx.Response(200, text=fake_diff))

    diff = await client.get_pull_request_diff(OWNER, REPO, PR_NUMBER)

    assert diff == fake_diff


@pytest.mark.asyncio
@respx.mock
async def test_create_review_posts_body_and_event(client: GitHubClient):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}/reviews"
    route = respx.post(url).mock(
        return_value=httpx.Response(200, json={"id": 1, "state": "COMMENTED"})
    )

    result = await client.create_review(
        OWNER, REPO, PR_NUMBER, body="Looks good, one nit.", event="COMMENT"
    )

    assert result["state"] == "COMMENTED"
    # Verify what we actually sent to GitHub
    sent_payload = route.calls.last.request.content
    assert b"Looks good, one nit." in sent_payload
    assert b"COMMENT" in sent_payload


@pytest.mark.asyncio
@respx.mock
async def test_get_pull_request_raises_on_http_error(client: GitHubClient):
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/pulls/{PR_NUMBER}"
    respx.get(url).mock(return_value=httpx.Response(404, json={"message": "Not Found"}))

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_pull_request(OWNER, REPO, PR_NUMBER)
