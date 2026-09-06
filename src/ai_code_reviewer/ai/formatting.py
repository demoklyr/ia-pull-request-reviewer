"""Turn a ReviewResult into a human-readable Markdown comment for GitHub."""

from ai_code_reviewer.models.review import ReviewResult

SEVERITY_EMOJI = {
    "LOW": "🟢",
    "MEDIUM": "🟡",
    "HIGH": "🟠",
    "CRITICAL": "🔴",
}


def build_review_markdown(result: ReviewResult) -> str:
    """Render a ReviewResult as a Markdown string suitable for a PR comment."""
    lines = ["## 🤖 AI Code Review", "", result.summary, ""]

    if not result.issues:
        lines.append("No issues found. ✅")
        return "\n".join(lines)

    for issue in result.issues:
        emoji = SEVERITY_EMOJI.get(issue.severity.value, "⚪")
        location = ""
        if issue.file:
            location = f" (`{issue.file}`" + (f":{issue.line}" if issue.line else "") + ")"

        lines.append(f"### {emoji} {issue.severity.value} — {issue.category.value}{location}")
        lines.append("")
        lines.append(f"**{issue.title}**")
        lines.append("")
        lines.append(issue.description)
        lines.append("")
        lines.append(f"**Recommendation:** {issue.recommendation}")
        lines.append("")

    return "\n".join(lines)
