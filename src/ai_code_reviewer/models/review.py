"""Pydantic models describing a structured code review result.

This is the contract between the LLM output and the rest of the app:
whatever Gemini returns MUST validate against ReviewResult, otherwise
we reject it rather than publish garbage on GitHub.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """How serious an issue is."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Category(str, Enum):
    """What kind of problem was detected, matching the V1 spec."""

    BUG = "bug"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BEST_PRACTICE = "best_practice"
    TESTING = "testing"


class ReviewIssue(BaseModel):
    """A single issue detected in the diff."""

    severity: Severity
    category: Category
    title: str = Field(..., description="Short one-line summary of the issue.")
    description: str = Field(..., description="Explanation of the problem and why it matters.")
    recommendation: str = Field(..., description="Concrete suggestion to fix it.")
    file: str | None = Field(default=None, description="File path where the issue was found.")
    line: int | None = Field(default=None, description="Line number in the diff, if known.")


class ReviewResult(BaseModel):
    """The full structured review returned by the LLM for one PR diff."""

    summary: str = Field(..., description="One or two sentence overview of the PR quality.")
    issues: list[ReviewIssue] = Field(default_factory=list)
