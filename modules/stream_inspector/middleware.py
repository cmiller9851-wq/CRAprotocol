"""
SPDX-License-Identifier: SAEL-1.0
Copyright (c) 2026 QuickPrompt Solutions™ / Miller Sovereign Holdings
Authors: QuickPrompt Solutions™ — Cory Miller, Sovereign Architect
License: Sovereign Authorship Enforced License (SAEL v1.0)
Distribution or relicensing without explicit sovereign license grant is prohibited.
"""

from typing import Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .decoder import OptimizedStreamInspectorDecoder as StreamInspectorDecoder


class StreamInspectorMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "json" not in content_type:
            return response

        decoder = StreamInspectorDecoder()

        async def intercepted_generator():
            async for chunk in response.body_iterator:
                if isinstance(chunk, bytes):
                    chunk_str = chunk.decode("utf-8", errors="ignore")
                else:
                    chunk_str = str(chunk)

                cleaned_text, events = decoder.process_chunk(chunk_str)
                if events:
                    pass
                yield cleaned_text.encode("utf-8")

        return Response(
            content=intercepted_generator(),
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
