"""Vercel Python serverless entrypoint.

Vercel's @vercel/python runtime serves the ASGI `app` exposed here. `vercel.json` routes
every request to this file. Only the light read/chat endpoints run here — the heavy daily
collection runs in GitHub Actions (Vercel functions have an execution-time limit).
"""

from api.main import app

__all__ = ["app"]
