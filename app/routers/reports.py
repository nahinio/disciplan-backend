from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies.auth import get_current_user
from app.db.session import transaction
from app.repositories import report_repo
from app.schemas.phase3 import CreateContentReportRequest

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("")
async def submit_report(
    body: CreateContentReportRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        try:
            report_id = await report_repo.create_report(
                conn,
                reporter_user_id=user["id"],
                entity_type_code=body.entity_type_code,
                entity_id=body.entity_id,
                reason_code=body.reason_code,
                notes=body.notes,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
    return {"id": report_id, "message": "Report submitted"}
