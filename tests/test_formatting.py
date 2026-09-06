"""Tests for build_review_markdown."""

from ai_code_reviewer.ai.formatting import build_review_markdown
from ai_code_reviewer.models.review import Category, ReviewIssue, ReviewResult, Severity


def test_markdown_for_clean_pr_has_no_issues_section():
    result = ReviewResult(summary="Clean PR, no issues detected.", issues=[])

    markdown = build_review_markdown(result)

    assert "Clean PR, no issues detected." in markdown
    assert "No issues found" in markdown


def test_markdown_includes_severity_category_and_recommendation():
    result = ReviewResult(
        summary="One security issue found.",
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

    markdown = build_review_markdown(result)

    assert "HIGH" in markdown
    assert "security" in markdown
    assert "Potential SQL injection" in markdown
    assert "Use parameterized queries." in markdown
    assert "`app.py`:3" in markdown


def test_markdown_handles_issue_without_file_or_line():
    result = ReviewResult(
        summary="General feedback.",
        issues=[
            ReviewIssue(
                severity=Severity.LOW,
                category=Category.TESTING,
                title="Missing edge case tests",
                description="No test covers the empty-input case.",
                recommendation="Add a test for empty input.",
            )
        ],
    )

    markdown = build_review_markdown(result)

    assert "Missing edge case tests" in markdown
    # No crash and no dangling "(`None`)" style artifact
    assert "None" not in markdown
