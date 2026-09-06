"""API routes: health check and GitHub webhook entrypoint.

The webhook is the orchestrator of the whole pipeline:
    GitHub event -> diff -> AI reviewer -> Markdown -> GitHub review comment
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from ai_code_reviewer.ai.formatting import build_review_markdown
from ai_code_reviewer.ai.reviewer import AIReviewer, InvalidLLMResponseError
from ai_code_reviewer.api.security import verify_github_signature
from ai_code_reviewer.config import Settings, get_settings
from ai_code_reviewer.github.client import GitHubClient

logger = logging.getLogger(__name__)

router = APIRouter()

# Only these pull_request actions trigger a review: a fresh PR, or new
# commits pushed to an existing PR. Other actions (closed, labeled,
# reopened...) are intentionally ignored for V1.
RELEVANT_ACTIONS = {"opened", "synchronize"}


def get_github_client() -> GitHubClient:
    """FastAPI dependency: real GitHub client (reads token from settings).

    Overridden in tests with app.dependency_overrides to inject a fake.
    """
    return GitHubClient()


def get_ai_reviewer() -> AIReviewer:
    """FastAPI dependency: real AI reviewer (reads Gemini key from settings).

    Overridden in tests with app.dependency_overrides to inject a fake.
    """
    return AIReviewer()


def get_app_settings() -> Settings:
    """FastAPI dependency: app settings, overridable in tests."""
    return get_settings()


@router.get("/health")
async def health() -> dict:
    """Simple liveness check used for monitoring and Docker healthchecks."""
    return {"status": "ok"}


@router.post("/webhook")
async def webhook(
    request: Request,
    github_client: GitHubClient = Depends(get_github_client),
    ai_reviewer: AIReviewer = Depends(get_ai_reviewer),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    """Entrypoint for GitHub webhook events.

    Verifies the request signature first (see api/security.py), then only
    processes `pull_request` events with action `opened` or `synchronize`.
    Everything else is acknowledged but ignored.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not verify_github_signature(raw_body, signature_header, settings.github_webhook_secret):
        logger.warning("Rejected webhook with invalid or missing signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    payload = json.loads(raw_body)
    action = payload.get("action")

    logger.info("Received GitHub webhook event=%s action=%s", event_type, action)

    if event_type != "pull_request" or action not in RELEVANT_ACTIONS:
        return {"received": True, "event": event_type, "action": action, "processed": False}

    repo_full_name = payload.get("repository", {}).get("full_name")
    pr_number = payload.get("pull_request", {}).get("number")

    if not repo_full_name or pr_number is None:
        logger.warning("Webhook payload missing repository or pull_request info")
        return {
            "received": True,
            "event": event_type,
            "action": action,
            "processed": False,
            "reason": "malformed_payload",
        }

    owner, repo = repo_full_name.split("/", 1)

    diff = await github_client.get_pull_request_diff(owner, repo, pr_number)

    if not diff.strip():
        logger.info("Empty diff for PR #%s, skipping review", pr_number)
        return {
            "received": True,
            "event": event_type,
            "action": action,
            "processed": False,
            "reason": "empty_diff",
        }

    try:
        result = ai_reviewer.review_diff(diff)
    except InvalidLLMResponseError:
        logger.exception("AI reviewer failed to produce a valid review for PR #%s", pr_number)
        return {
            "received": True,
            "event": event_type,
            "action": action,
            "processed": False,
            "reason": "invalid_llm_response",
        }

    body = build_review_markdown(result)
    await github_client.create_review(owner, repo, pr_number, body=body, event="COMMENT")

    return {
        "received": True,
        "event": event_type,
        "action": action,
        "processed": True,
        "issues_found": len(result.issues),
    }
