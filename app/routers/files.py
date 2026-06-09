from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies.auth import get_current_user
from app.db.session import transaction
from app.repositories import file_repo
from app.utils.cloudinary import configure_cloudinary, upload_file
from app.utils.file_delivery import build_file_response

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload")
async def upload(
    user: dict = Depends(get_current_user),
    file: UploadFile = File(...),
    folder: str = Form(default="general"),
) -> dict:
    configure_cloudinary()

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Max 10 MB")

    try:
        meta = upload_file(content, file.filename or "upload", folder_suffix=folder)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cloudinary upload failed: {exc}",
        ) from exc

    async with transaction() as conn:
        file_id = await file_repo.insert_file(
            conn,
            uploaded_by_user_id=user["id"],
            storage_key=meta["storage_key"],
            secure_url=meta["secure_url"],
            original_filename=meta["original_filename"],
            mime_type=meta["mime_type"],
            size_bytes=meta["size_bytes"],
            checksum_sha256=meta["checksum_sha256"],
            width_px=meta.get("width_px"),
            height_px=meta.get("height_px"),
        )

    return {"file_id": file_id, **meta}


@router.get("/{file_id}/download")
async def download_file(file_id: int, user: dict = Depends(get_current_user)):
    from app.db.session import get_connection

    async with get_connection() as conn:
        row = await file_repo.get_file_by_id(conn, file_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return await build_file_response(row, inline=False)


@router.get("/{file_id}/view")
async def view_file(file_id: int, user: dict = Depends(get_current_user)):
    from app.db.session import get_connection

    async with get_connection() as conn:
        row = await file_repo.get_file_by_id(conn, file_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return await build_file_response(row, inline=True)


@router.get("/{file_id}")
async def get_file_meta(file_id: int, user: dict = Depends(get_current_user)) -> dict:
    from app.db.session import get_connection

    async with get_connection() as conn:
        row = await file_repo.get_file_by_id(conn, file_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return row
