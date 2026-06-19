"""Local ASGI entry point: uvicorn api:app --reload."""

from skilldrift.api_app import app

__all__ = ["app"]
