"""AI review engine: sends a diff to an LLM and returns a validated ReviewResult.

Pipeline: diff -> prompt -> Gemini -> raw JSON text -> Pydantic -> ReviewResult
"""

import json
from typing import Protocol

from google import genai

from ai_code_reviewer.ai.prompts import build_review_prompt
from ai_code_reviewer.config import get_settings
from ai_code_reviewer.models.review import ReviewResult


class LLMClient(Protocol):
    """Anything that can turn a prompt into raw text output.

    This is the seam that makes AIReviewer testable: in production we use
    GeminiClient, in tests we inject a fake object with a `.generate()`
    method that returns a canned string — no real API call, no API key
    needed to run the test suite.
    """

    def generate(self, prompt: str) -> str: ...


class GeminiClient:
    """Thin adapter around the google-genai SDK, matching the LLMClient protocol."""

    def __init__(self, api_key: str | None = None, model_name: str = "gemini-3.6-flash") -> None:
        self._api_key = api_key if api_key is not None else get_settings().gemini_api_key
        self._client = genai.Client(api_key=self._api_key)
        self._model_name = model_name

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model_name,
            contents=prompt,
        )
        return response.text


class InvalidLLMResponseError(ValueError):
    """Raised when the LLM output cannot be parsed/validated as a ReviewResult."""


class AIReviewer:
    """Runs the full diff -> prompt -> LLM -> JSON -> Pydantic pipeline."""

    def __init__(self, client: LLMClient | None = None) -> None:
        # Same dependency-injection pattern as GitHubClient, but lazy: we
        # only store what was passed in (possibly None). The real
        # GeminiClient is only constructed on first actual use, in
        # _get_client(). This matters because building GeminiClient calls
        # genai.Client(api_key=...), which raises if the key is missing or
        # invalid — we don't want that to happen just because AIReviewer()
        # was instantiated (e.g. as a FastAPI dependency for a request that
        # ends up never needing the AI reviewer at all).
        self._client = client

    def _get_client(self) -> LLMClient:
        if self._client is None:
            self._client = GeminiClient()
        return self._client

    def review_diff(self, diff: str) -> ReviewResult:
        """Send `diff` to the LLM and return a validated, structured review."""
        prompt = build_review_prompt(diff)
        raw_output = self._get_client().generate(prompt)
        cleaned = _strip_code_fences(raw_output)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise InvalidLLMResponseError(
                f"LLM did not return valid JSON: {exc}\nRaw output: {raw_output!r}"
            ) from exc

        try:
            return ReviewResult.model_validate(data)
        except Exception as exc:  # pydantic.ValidationError, re-raised as our own type
            raise InvalidLLMResponseError(
                f"LLM JSON did not match the expected schema: {exc}"
            ) from exc


def _strip_code_fences(text: str) -> str:
    """LLMs often wrap JSON in ```json ... ``` fences; strip them if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]  # drop opening fence line (``` or ```json)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # drop closing fence line
        stripped = "\n".join(lines)
    return stripped.strip()
