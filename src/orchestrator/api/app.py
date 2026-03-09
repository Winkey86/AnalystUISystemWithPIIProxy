"""Minimal API entrypoint for local scaffold validation."""

from fastapi import FastAPI

app = FastAPI(title="Orchestrator Kernel")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
