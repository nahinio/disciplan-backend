"""Stream stored files with correct MIME type and filename."""

from __future__ import annotations

import mimetypes
from typing import Any

import cloudinary.utils
import httpx
from fastapi import HTTPException, status
from fastapi.responses import Response

from app.utils.cloudinary import configure_cloudinary, guess_mime_type, normalize_stored_mime_type


def _content_disposition(filename: str, *, inline: bool) -> str:
    disposition = "inline" if inline else "attachment"
    safe_name = filename.replace('"', "").replace("\n", "").replace("\r", "")
    return f'{disposition}; filename="{safe_name}"'


def _resolve_mime(file_row: dict[str, Any]) -> str:
    filename = str(file_row.get("original_filename") or "download")
    from_name = guess_mime_type(filename)
    stored = normalize_stored_mime_type(
        str(file_row.get("mime_type") or ""),
        filename,
    )
    if stored == "application/octet-stream" and from_name != "application/octet-stream":
        return from_name
    return stored


def _can_view_inline(mime_type: str) -> bool:
    if mime_type.startswith("image/") or mime_type == "application/pdf":
        return True
    return mime_type.startswith("text/")


def _delivery_url_candidates(file_row: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(url: str | None) -> None:
        if url and url not in seen:
            seen.add(url)
            out.append(url)

    add(str(file_row.get("secure_url") or ""))

    storage_key = str(file_row.get("storage_key") or "").strip()
    if storage_key:
        configure_cloudinary()
        for resource_type in ("raw", "image", "auto"):
            built, _ = cloudinary.utils.cloudinary_url(
                storage_key,
                resource_type=resource_type,
                secure=True,
            )
            add(built)

    return out


async def build_file_response(file_row: dict[str, Any], *, inline: bool) -> Response:
    filename = str(file_row.get("original_filename") or "download")
    mime_type = _resolve_mime(file_row)
    use_inline = inline and _can_view_inline(mime_type)

    last_error: Exception | None = None
    for url in _delivery_url_candidates(file_row):
        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                upstream = await client.get(url)
                upstream.raise_for_status()
                if len(upstream.content) < 16:
                    continue
                # Valid ZIP/docx/PDF should not be an HTML error page
                if upstream.content[:15].lower().startswith(b"<!doctype html"):
                    continue

                resolved_mime = mime_type
                content_type = upstream.headers.get("content-type", "")
                if content_type and "octet-stream" not in content_type.lower():
                    resolved_mime = content_type.split(";")[0].strip()
                elif resolved_mime == "application/octet-stream":
                    resolved_mime = guess_mime_type(filename)

                return Response(
                    content=upstream.content,
                    media_type=resolved_mime,
                    headers={
                        "Content-Disposition": _content_disposition(
                            filename, inline=use_inline
                        ),
                        "Content-Length": str(len(upstream.content)),
                    },
                )
        except httpx.HTTPError as exc:
            last_error = exc
            continue

    detail = f"Could not fetch file: {last_error}" if last_error else "Could not fetch file"
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
