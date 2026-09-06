"""FastAPI application entrypoint for AI Code Reviewer."""

from fastapi import FastAPI

from ai_code_reviewer.api.routes import router

app = FastAPI(
    title="AI Code Reviewer",
    description="Automatically reviews GitHub Pull Requests using an LLM.",
    version="0.1.0",
)

app.include_router(router)
