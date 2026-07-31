from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.models.user import User

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def primary_email(data: dict[str, Any]) -> str:
    addresses = data.get("email_addresses") or []
    primary_id = data.get("primary_email_address_id")
    selected = next((entry for entry in addresses if entry.get("id") == primary_id), None)
    selected = selected or (addresses[0] if addresses else None)
    if not selected or not selected.get("email_address"):
        raise HTTPException(status_code=400, detail="Clerk user event has no email address")
    return str(selected["email_address"])


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    payload = await request.body()
    try:
        event = Webhook(settings.clerk_webhook_signing_secret.get_secret_value()).verify(
            payload, dict(request.headers)
        )
    except (WebhookVerificationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature"
        ) from exc

    event_type = event.get("type")
    data = event.get("data", {})
    clerk_user_id = data.get("id")
    if not clerk_user_id:
        raise HTTPException(status_code=400, detail="Clerk event has no user id")

    if event_type in {"user.created", "user.updated"}:
        values = {
            "clerk_user_id": clerk_user_id,
            "email": primary_email(data),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
        }
        statement = (
            insert(User)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[User.clerk_user_id],
                set_={key: value for key, value in values.items() if key != "clerk_user_id"},
            )
        )
        await session.execute(statement)
    elif event_type == "user.deleted":
        await session.execute(delete(User).where(User.clerk_user_id == clerk_user_id))
    await session.commit()
    return {"status": "ok"}
