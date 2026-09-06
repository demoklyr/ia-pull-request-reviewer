"""Tests for AIReviewer — no real Gemini API call, a fake LLMClient is injected."""

import pytest

from ai_code_reviewer.ai.reviewer import AIReviewer, InvalidLLMResponseError
from ai_code_reviewer.models.review import Category, ReviewResult, Severity

FAKE_DIFF = (
    "diff --git a/app.py b/app.py\n"
    "+def get_user(user_id):\n"
    "+    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
    "+    return db.execute(query)\n"
)


class FakeLLMClient:
    """Test double for LLMClient: returns a fixed string instead of calling Gemini."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response_text


def test_review_diff_parses_valid_json_response():
    fake_response = """{
        "summary": "One security issue found.",
        "issues": [
            {
                "severity": "HIGH",
                "category": "security",
                "title": "Potential SQL injection",
                "description": "The user-controlled value is directly interpolated into the SQL query.",
                "recommendation": "Use parameterized queries.",
                "file": "app.py",
                "line": 3
            }
        ]
    }"""
    reviewer = AIReviewer(client=FakeLLMClient(fake_response))

    result = reviewer.review_diff(FAKE_DIFF)

    assert isinstance(result, ReviewResult)
    assert len(result.issues) == 1
    assert result.issues[0].severity == Severity.HIGH
    assert result.issues[0].category == Category.SECURITY
    assert "SQL injection" in result.issues[0].title


def test_review_diff_strips_markdown_code_fences():
    fake_response = '```json\n{"summary": "Looks fine.", "issues": []}\n```'
    reviewer = AIReviewer(client=FakeLLMClient(fake_response))

    result = reviewer.review_diff(FAKE_DIFF)

    assert result.summary == "Looks fine."
    assert result.issues == []


def test_review_diff_handles_no_issues_found():
    fake_response = '{"summary": "Clean PR, no issues detected.", "issues": []}'
    reviewer = AIReviewer(client=FakeLLMClient(fake_response))

    result = reviewer.review_diff(FAKE_DIFF)

    assert result.issues == []
    assert "Clean" in result.summary


def test_review_diff_raises_on_invalid_json():
    fake_client = FakeLLMClient("this is not JSON at all")
    reviewer = AIReviewer(client=fake_client)

    with pytest.raises(InvalidLLMResponseError):
        reviewer.review_diff(FAKE_DIFF)


def test_review_diff_raises_on_json_missing_required_fields():
    # Valid JSON, but missing the required "summary" field.
    fake_response = '{"issues": []}'
    reviewer = AIReviewer(client=FakeLLMClient(fake_response))

    with pytest.raises(InvalidLLMResponseError):
        reviewer.review_diff(FAKE_DIFF)


def test_review_diff_sends_the_diff_inside_the_prompt():
    fake_client = FakeLLMClient('{"summary": "ok", "issues": []}')
    reviewer = AIReviewer(client=fake_client)

    reviewer.review_diff(FAKE_DIFF)

    assert fake_client.last_prompt is not None
    assert "SELECT * FROM users" in fake_client.last_prompt
