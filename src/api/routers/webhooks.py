# src/api/routers/webhooks.py
"""Router for Clerk webhook endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from svix.webhooks import Webhook, WebhookVerificationError

from api.deps import DbSession
from api.services.user import UserService
from api.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Webhooks"])


@router.post(
    "/clerk",
    status_code=status.HTTP_200_OK,
    summary="Clerk webhook receiver",
    description="Receives and processes Clerk webhook events for user sync.",
)
async def clerk_webhook(
    request: Request,
    db: DbSession,
) -> dict[str, str]:
    """Handle incoming Clerk webhook events.

    Verifies the Svix signature, then processes ``user.created`` and
    ``user.updated`` events by upserting user data via :class:`UserService`.

    :param request: The incoming HTTP request.
    :param db: Database session.
    :returns: Acknowledgement dict.
    :raises HTTPException: If signature verification fails.
    """
    settings = get_settings()
    body = await request.body()
    headers = dict(request.headers)

    # Verify Svix webhook signature
    try:
        wh = Webhook(settings.clerk_webhook_secret)
        payload = wh.verify(body, headers)
    except WebhookVerificationError:
        logger.warning("Clerk webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    event_type = payload.get("type")
    if event_type not in ("user.created", "user.updated"):
        return {"status": "ignored"}

    data = payload.get("data", {})

    # Extract primary email from Clerk's email_addresses array
    email_addresses = data.get("email_addresses", [])
    email = email_addresses[0].get("email_address") if email_addresses else None

    clerk_data = {
        "id": data.get("id"),
        "email": email,
        "first_name": data.get("first_name"),
        "last_name": data.get("last_name"),
        "username": data.get("username"),
        "image_url": data.get("image_url"),
    }

    service = UserService(db)
    await service.upsert_from_clerk(clerk_data)

    logger.info("Processed Clerk %s event for user %s", event_type, clerk_data["id"])
    return {"status": "ok"}
