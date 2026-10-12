from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_csrf
from app.core.database import get_db
from app.models.user import User
from app.schemas.workspace import ShareRedeemOut
from app.share.service import ShareService

router = APIRouter(tags=["share"])


@router.post("/share/{token}/redeem", response_model=ShareRedeemOut)
async def redeem_share(
    token: str,
    request: Request,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> ShareRedeemOut:
    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    ip_hash = hashlib.sha256(ip.encode()).hexdigest() if ip else None
    ua_hash = hashlib.sha256(ua.encode()).hexdigest() if ua else None
    result = await ShareService(db).redeem(
        user, token, ip_hash=ip_hash, user_agent_hash=ua_hash
    )
    return ShareRedeemOut(
        target_type=result["target_type"],
        workspace_id=result["workspace_id"],
        space_id=result.get("space_id"),
        role=result["role"],
    )


@router.delete("/share-links/{link_id}", status_code=204, response_class=Response)
async def revoke_share_link(
    link_id: UUID,
    user: User = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await ShareService(db).revoke(user, link_id)
    return Response(status_code=204)
