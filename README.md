# AI Code Reviewer

> An AI-powered GitHub bot that automatically reviews Pull Requests and detects potential bugs, security issues, performance problems, and missing tests.

## Overview

AI Code Reviewer integrates an LLM into the GitHub development workflow.

When a Pull Request is opened or updated, the system:

```text
GitHub PR
   ↓
Webhook
   ↓
FastAPI
   ↓
GitHub API
   ↓
Code Diff
   ↓
LLM
   ↓
Structured Review
   ↓
GitHub Comment
```

The goal is to demonstrate practical **AI Engineering and Software Engineering** skills by building a complete, testable, and containerized application.

## Tech Stack

* Python 3.12+
* FastAPI
* Pydantic
* Gemini API
* GitHub API & Webhooks
* Pytest
* Docker
* GitHub Actions

## MVP Features

* Analyze GitHub Pull Request diffs
* Detect potential bugs and security issues
* Identify performance and code-quality problems
* Generate structured AI reviews
* Automatically comment on Pull Requests
* Unit tests with Pytest
* Dockerized application
* CI with GitHub Actions

## Project Structure

```text
ai-code-reviewer/
├── src/
│   └── ai_code_reviewer/
│       ├── api/
│       ├── github/
│       ├── ai/
│       └── models/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Example

Given:

```python
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)
```

The AI reviewer can report:

```text
HIGH — Security

Potential SQL injection vulnerability.

Recommendation:
Use parameterized queries instead of string interpolation.
```

## Run Locally

```bash
git clone https://github.com/YOUR_USERNAME/ai-code-reviewer.git
cd ai-code-reviewer

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

Configure your environment:

```env
GEMINI_API_KEY=your_api_key
GITHUB_TOKEN=your_token
GITHUB_WEBHOOK_SECRET=your_secret
```

Run:

```bash
uvicorn ai_code_reviewer.api.routes:app --reload
```

Or with Docker:

```bash
docker compose up --build
```

## Team

Built collaboratively using Git, GitHub Pull Requests, code reviews, and CI/CD.

**Status:** MVP — In Development
