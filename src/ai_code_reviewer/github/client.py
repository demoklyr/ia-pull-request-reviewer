"""Thin async client around the GitHub REST API endpoints we need.

Only three operations are exposed, matching exactly what the review
pipeline needs:
- get_pull_request:      fetch PR metadata (title, author, branches...)
- get_pull_request_diff: fetch the raw unified diff of the PR
- create_review:         publish a review (comment) on the PR
"""

import httpx

from ai_code_reviewer.config import get_settings

GITHUB_API_URL = "https://api.github.com"


class GitHubClient:
    """Async wrapper around the subset of the GitHub REST API we use."""

    def __init__(self, token: str | None = None, base_url: str = GITHUB_API_URL) -> None:
        # If no token is explicitly passed, fall back to the app settings
        # (which reads GITHUB_TOKEN from the environment / .env file).
        self._token = token if token is not None else get_settings().github_token
        self._base_url = base_url

    def _headers(self, accept: str = "application/vnd.github+json") -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        """Fetch pull request metadata (title, author, base/head branches, etc.)."""
        url = f"{self._base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            return response.json()

    async def get_pull_request_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """Fetch the raw unified diff of a pull request.

        Same endpoint as get_pull_request, but GitHub returns a plain-text
        diff instead of JSON when we ask for the `.diff` media type.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = self._headers(accept="application/vnd.github.v3.diff")

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    async def create_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
    ) -> dict:
        """Publish a review on a pull request.

        `event` must be one of: "APPROVE", "REQUEST_CHANGES", "COMMENT".
        We default to "COMMENT" so the bot never blocks or approves a PR
        on its own unless explicitly configured to do so.
        """
        url = f"{self._base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        payload = {"body": body, "event": event}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            return response.json()
