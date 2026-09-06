"""Tests for the FastAPI routes (/health and /webhook).

GitHubClient and AIReviewer are replaced with fakes via FastAPI's
dependency_overrides — no real GitHub or Gemini call happens here.
"""

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from ai_code_reviewer.ai.reviewer import InvalidLLMResponseError
from ai_code_reviewer.api.routes import get_ai_reviewer, get_app_settings, get_github_client
from ai_code_reviewer.config import Settings
from ai_code_reviewer.main import app
from ai_code_reviewer.models.review import Category, ReviewIssue, ReviewResult, Severity

client = TestClient(app)


class FakeGitHubClient:
    """Records what would have been sent to GitHub, without a real call."""

    def __init__(self, diff: str = "diff --git a/app.py b/app.py\n+print('hi')\n"):
        self.diff = diff
        self.created_review: dict | None = None

    async def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> str:
        return self.diff

    async def create_review(self, owner, repo, pr_number, body, event="COMMENT") -> dict:
        self.created_review = {
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "body": body,
            "event": event,
        }
        return {"id": 1}


class FakeAIReviewer:
    """Returns a fixed ReviewResult instead of calling Gemini."""

    def __init__(self, result: ReviewResult):
        self.result = result

    def review_diff(self, diff: str) -> ReviewResult:
        return self.result


class FailingAIReviewer:
    """Simulates the LLM returning something we can't parse/validate."""

    def review_diff(self, diff: str) -> ReviewResult:
        raise InvalidLLMResponseError("boom")


def _pr_payload(action="opened", pr_number=1, repo_full_name="octocat/hello-world") -> dict:
    return {
        "action": action,
        "pull_request": {"number": pr_number},
        "repository": {"full_name": repo_full_name},
    }


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Make sure overrides from one test never leak into the next one."""
    yield
    app.dependency_overrides.clear()


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_webhook_ignores_non_pull_request_events():
    response = client.post(
        "/webhook", json={"action": "created"}, headers={"X-GitHub-Event": "issue_comment"}
    )

    assert response.status_code == 200
    assert response.json()["processed"] is False


def test_webhook_ignores_irrelevant_pull_request_actions():
    payload = _pr_payload(action="closed")

    response = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})

    assert response.json()["processed"] is False


def test_webhook_processes_opened_pull_request_and_posts_review():
    fake_github = FakeGitHubClient()
    fake_result = ReviewResult(
        summary="One issue found.",
        issues=[
            ReviewIssue(
                severity=Severity.HIGH,
                category=Category.SECURITY,
                title="Potential SQL injection",
                description="User input is interpolated directly into the query.",
                recommendation="Use parameterized queries.",
                file="app.py",
                line=3,
            )
        ],
    )

    app.dependency_overrides[get_github_client] = lambda: fake_github
    app.dependency_overrides[get_ai_reviewer] = lambda: FakeAIReviewer(fake_result)

    payload = _pr_payload(action="opened")
    response = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})

    assert response.status_code == 200
    body = response.json()
    assert body["processed"] is True
    assert body["issues_found"] == 1

    assert fake_github.created_review is not None
    assert fake_github.created_review["owner"] == "octocat"
    assert fake_github.created_review["repo"] == "hello-world"
    assert "SQL injection" in fake_github.created_review["body"]


def test_webhook_processes_synchronize_action_too():
    fake_github = FakeGitHubClient()
    fake_result = ReviewResult(summary="All good.", issues=[])

    app.dependency_overrides[get_github_client] = lambda: fake_github
    app.dependency_overrides[get_ai_reviewer] = lambda: FakeAIReviewer(fake_result)

    payload = _pr_payload(action="synchronize")
    response = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})

    assert response.json()["processed"] is True
    assert fake_github.created_review is not None


def test_webhook_skips_review_on_empty_diff():
    fake_github = FakeGitHubClient(diff="   ")

    app.dependency_overrides[get_github_client] = lambda: fake_github
    app.dependency_overrides[get_ai_reviewer] = lambda: FakeAIReviewer(
        ReviewResult(summary="unused", issues=[])
    )

    payload = _pr_payload(action="opened")
    response = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})

    body = response.json()
    assert body["processed"] is False
    assert body["reason"] == "empty_diff"
    assert fake_github.created_review is None


def test_webhook_handles_invalid_llm_response_gracefully():
    fake_github = FakeGitHubClient()

    app.dependency_overrides[get_github_client] = lambda: fake_github
    app.dependency_overrides[get_ai_reviewer] = lambda: FailingAIReviewer()

    payload = _pr_payload(action="opened")
    response = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})

    body = response.json()
    assert body["processed"] is False
    assert body["reason"] == "invalid_llm_response"
    assert fake_github.created_review is None


def test_webhook_handles_malformed_payload():
    payload = {"action": "opened"}  # missing "repository" and "pull_request"

    response = client.post("/webhook", json=payload, headers={"X-GitHub-Event": "pull_request"})

    body = response.json()
    assert body["processed"] is False
    assert body["reason"] == "malformed_payload"


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_rejects_invalid_signature_when_secret_is_configured():
    app.dependency_overrides[get_app_settings] = lambda: Settings(github_webhook_secret="top-secret")

    response = client.post(
        "/webhook",
        json=_pr_payload(action="closed"),
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=wrong"},
    )

    assert response.status_code == 401


def test_webhook_accepts_valid_signature_when_secret_is_configured():
    fake_github = FakeGitHubClient()
    app.dependency_overrides[get_github_client] = lambda: fake_github
    app.dependency_overrides[get_ai_reviewer] = lambda: FakeAIReviewer(
        ReviewResult(summary="ok", issues=[])
    )
    app.dependency_overrides[get_app_settings] = lambda: Settings(github_webhook_secret="top-secret")

    payload = _pr_payload(action="opened")
    raw_body = json.dumps(payload).encode()
    signature = _sign(raw_body, "top-secret")

    response = client.post(
        "/webhook",
        content=raw_body,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json()["processed"] is True
