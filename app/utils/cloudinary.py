"""Cloudinary file upload — binaries stored externally, metadata in MySQL."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from typing import Any

import cloudinary
import cloudinary.uploader

from app.config import get_settings

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"}


def guess_mime_type(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"


def normalize_stored_mime_type(mime_type: str | None, filename: str) -> str:
    if mime_type and "/" in mime_type:
        return mime_type
    return guess_mime_type(filename)


def configure_cloudinary() -> None:
    settings = get_settings()
    if not settings.cloudinary_cloud_name:
        return
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )


def upload_file(
    file_bytes: bytes,
    filename: str,
    *,
    folder_suffix: str = "general",
    resource_type: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    folder = f"{settings.cloudinary_folder}/{folder_suffix}"
    checksum = hashlib.sha256(file_bytes).hexdigest()
    ext = os.path.splitext(filename)[1].lower()
    is_image = ext in _IMAGE_EXTENSIONS
    resolved_type = resource_type or ("image" if is_image else "raw")

    upload_kwargs: dict[str, Any] = {
        "folder": folder,
        "resource_type": resolved_type,
        "unique_filename": True,
    }
    if resolved_type == "image":
        upload_kwargs["use_filename"] = True
    else:
        stem = os.path.splitext(filename)[0]
        safe_stem = re.sub(r"[^\w\-.]", "_", stem)[:80] or "file"
        upload_kwargs["public_id"] = f"{safe_stem}{ext}"
        upload_kwargs["use_filename"] = False

    result = cloudinary.uploader.upload(file_bytes, **upload_kwargs)

    return {
        "storage_key": result["public_id"],
        "secure_url": result["secure_url"],
        "mime_type": guess_mime_type(filename),
        "resource_type": resolved_type,
        "size_bytes": result.get("bytes", len(file_bytes)),
        "checksum_sha256": checksum,
        "width_px": result.get("width"),
        "height_px": result.get("height"),
        "original_filename": filename,
    }


def delete_file(storage_key: str, resource_type: str = "image") -> None:
    cloudinary.uploader.destroy(storage_key, resource_type=resource_type)
