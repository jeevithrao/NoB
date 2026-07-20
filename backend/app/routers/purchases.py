import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Purchase, Tour, User
from app.schemas.purchase import (
    BindDeviceRequest,
    PaymentWebhookPayload,
    PurchaseCreate,
    PurchaseCreateResponse,
    PurchaseOut,
)

router = APIRouter(tags=["purchases"])


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


@router.post("/purchases", response_model=PurchaseCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    body: PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tour = await db.get(Tour, body.tour_id)
    if tour is None or not tour.is_published:
        raise _api_error(status.HTTP_404_NOT_FOUND, "TOUR_NOT_FOUND", "Tour not found.")
    if tour.is_free:
        raise _api_error(status.HTTP_400_BAD_REQUEST, "TOUR_IS_FREE", "This tour doesn't require purchase.")

    existing = await db.execute(
        select(Purchase).where(Purchase.user_id == current_user.id, Purchase.tour_id == tour.id)
    )
    purchase = existing.scalar_one_or_none()
    if purchase is not None and purchase.status == "completed":
        raise _api_error(status.HTTP_409_CONFLICT, "TOUR_ALREADY_OWNED", "You already own this tour.")

    if purchase is not None and purchase.status == "pending":
        # Reuse the pending row rather than creating a duplicate order.
        pass
    else:
        purchase = Purchase(
            user_id=current_user.id,
            tour_id=tour.id,
            amount_paise=tour.price_paise,
            status="pending",
        )
        db.add(purchase)
        await db.flush()

    if settings.MOCK_PAYMENTS:
        # No real gateway configured yet — complete the purchase immediately
        # so the rest of the flow (download, walk, licensing) is buildable
        # and testable today. Swap this block for real order creation once
        # Razorpay/Stripe keys exist; the response shape won't need to change.
        purchase.gateway_order_id = purchase.gateway_order_id or f"mock_order_{uuid.uuid4().hex[:16]}"
        purchase.gateway_payment_id = f"mock_payment_{uuid.uuid4().hex[:16]}"
        purchase.status = "completed"
        await db.commit()
        return PurchaseCreateResponse(
            purchase_id=purchase.id,
            status=purchase.status,
            gateway_order_id=purchase.gateway_order_id,
            gateway_config={"mock": True},
        )

    # Real-gateway path (not wired up yet): create an order with the provider
    # here, store gateway_order_id, and return client config for its SDK.
    raise _api_error(
        status.HTTP_501_NOT_IMPLEMENTED,
        "GATEWAY_NOT_CONFIGURED",
        "Real payment gateway isn't configured yet. Set MOCK_PAYMENTS=True for now.",
    )


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    purchase = await db.get(Purchase, purchase_id)
    if purchase is None or purchase.user_id != current_user.id:
        raise _api_error(status.HTTP_404_NOT_FOUND, "PURCHASE_NOT_FOUND", "Purchase not found.")
    return purchase


@router.post("/purchases/{purchase_id}/bind-device", response_model=PurchaseOut)
async def bind_device(
    purchase_id: uuid.UUID,
    body: BindDeviceRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """First download binds the purchase to a device (Business Rules §3a).
    A second device must go through this same endpoint and will be rejected
    while the tour is bound elsewhere."""
    purchase = await db.get(Purchase, purchase_id)
    if purchase is None or purchase.user_id != current_user.id:
        raise _api_error(status.HTTP_404_NOT_FOUND, "PURCHASE_NOT_FOUND", "Purchase not found.")
    if purchase.status != "completed":
        raise _api_error(status.HTTP_400_BAD_REQUEST, "PURCHASE_NOT_COMPLETED", "Purchase isn't completed yet.")

    if purchase.device_id is not None and purchase.device_id != body.device_identifier:
        raise _api_error(
            status.HTTP_409_CONFLICT,
            "BOUND_TO_OTHER_DEVICE",
            "This tour was downloaded on another device. Re-download here to move it — "
            "your other device will need to sign in again to use it.",
        )

    purchase.device_id = body.device_identifier
    await db.commit()
    await db.refresh(purchase)
    return purchase


@router.post("/webhooks/payment", status_code=status.HTTP_204_NO_CONTENT)
async def payment_webhook(payload: PaymentWebhookPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Gateway -> server callback. Real implementation must verify the
    provider's signature header before trusting this payload — stubbed here
    since MOCK_PAYMENTS completes purchases synchronously and doesn't call
    this at all. Left in place for when a real gateway is wired up."""
    if settings.MOCK_PAYMENTS:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST, "MOCK_MODE_ACTIVE", "Webhooks are unused while MOCK_PAYMENTS=True."
        )

    result = await db.execute(select(Purchase).where(Purchase.gateway_order_id == payload.gateway_order_id))
    purchase = result.scalar_one_or_none()
    if purchase is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "PURCHASE_NOT_FOUND", "No matching purchase for this order.")

    purchase.gateway_payment_id = payload.gateway_payment_id
    purchase.status = "completed" if payload.status == "success" else "failed"
    await db.commit()
