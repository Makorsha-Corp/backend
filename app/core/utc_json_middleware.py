"""Middleware: ensure naive ISO datetimes in JSON responses include UTC Z suffix."""
from __future__ import annotations

import json
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.datetime_serialize import ensure_utc_z_in_json


class UtcJsonResponseMiddleware(BaseHTTPMiddleware):
    """Append Z to naive datetime strings in /api/ JSON bodies."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if not request.url.path.startswith("/api/"):
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        if not body:
            return response

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        fixed = ensure_utc_z_in_json(payload)
        new_body = json.dumps(fixed, default=str).encode("utf-8")

        headers = dict(response.headers)
        headers.pop("content-length", None)

        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
