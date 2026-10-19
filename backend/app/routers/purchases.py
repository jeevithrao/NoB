import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import PaymentEvent, Purchase, Stop, Tour, TourSession, User
from app.routers.tours import _BOUND_TO_OTHER_DEVICE_MSG
from app.schemas.purchase import (
    BindDeviceRequest,
    BookingOut,
    BookingTour,
    CheckoutVerifyRequest,
    PurchaseCreate,
    PurchaseCreateResponse,
    PurchaseOut,
)
from app.services import payments

router = APIRouter(tags=["purchases"])
logger = logging.getLogger("nob.purchases")


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": {"code": code, "message": message}})


async def _active_purchase(db: AsyncSession, user_id: uuid.UUID, tour_id: uuid.UUID) -> Purchase | None:
    result = await db.execute(
        select(Purchase).where(
            Purchase.user_id == user_id,
            Purchase.tour_id == tour_id,
            Purchase.status.in_(["pending", "completed"]),
        )
    )
    return result.scalar_one_or_none()


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

    # failed/refunded rows are outside the partial unique index, so a retry or
    # re-buy creates a fresh row.
    purchase = await _active_purchase(db, current_user.id, tour.id)
    if purchase is not None and purchase.status == "completed":
        raise _api_error(status.HTTP_409_CONFLICT, "TOUR_ALREADY_OWNED", "You already own this tour.")

    if purchase is None:
        try:
            async with db.begin_nested():  # savepoint: a lost race must not poison the request
                purchase = Purchase(
                    user_id=current_user.id, tour_id=tour.id, amount_paise=tour.price_paise, status="pending"
                )
                db.add(purchase)
                await db.flush()
        except IntegrityError:
            # Two requests raced; the other one created the row. Reuse it.
            purchase = await _active_purchase(db, current_user.id, tour.id)
            if purchase is None:
                raise
            if purchase.status == "completed":
                raise _api_error(status.HTTP_409_CONFLICT, "TOUR_ALREADY_OWNED", "You already own this tour.")

    if settings.MOCK_PAYMENTS:
        # Development only: complete instantly so the whole flow is testable
        # without a gateway. (Production refuses to start with this on.)
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

    # Real gateway. Re-use the pending order if the user taps "Pay" twice.
    if purchase.gateway_order_id is None:
        try:
            purchase.gateway_order_id = await payments.create_order(purchase)
        except payments.GatewayError as exc:
            raise _api_error(status.HTTP_502_BAD_GATEWAY, "GATEWAY_ERROR", str(exc))
    await db.commit()
    return PurchaseCreateResponse(
        purchase_id=purchase.id,
        status=purchase.status,
        gateway_order_id=purchase.gateway_order_id,
        gateway_config=payments.checkout_config(purchase),
    )


async def _owned_purchase(db: AsyncSession, purchase_id: uuid.UUID, user: User, *, lock: bool = False) -> Purchase:
    query = select(Purchase).where(Purchase.id == purchase_id, Purchase.user_id == user.id)
    if lock:
        query = query.with_for_update()
    purchase = (await db.execute(query)).scalar_one_or_none()
    if purchase is None:
        raise _api_error(status.HTTP_404_NOT_FOUND, "PURCHASE_NOT_FOUND", "Purchase not found.")
    return purchase


def _refund_deadline(purchase: Purchase) -> datetime:
    return purchase.created_at + timedelta(days=settings.REFUND_WINDOW_DAYS)


def _refund_block_reason(purchase: Purchase, sessions: list[TourSession], now: datetime) -> str | None:
    """None if refundable, else the error code. Rules: Business Rules section 4."""
    if purchase.status != "completed":
        return "PURCHASE_NOT_COMPLETED"
    if purchase.is_locked or any(s.completed for s in sessions) or any(s.stops_visited > 0 for s in sessions):
        return "REFUND_NOT_ELIGIBLE"  # the walk was started or delivered
    if now > _refund_deadline(purchase):
        return "REFUND_WINDOW_EXPIRED"
    return None


@router.get("/purchases", response_model=list[BookingOut])
async def list_my_purchases(
    tab: Literal["upcoming", "past", "all"] = Query(default="all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """"My Bookings". upcoming = bought and not yet finished (not started or in
    progress); past = finished walks and refunded purchases. Pending/failed
    attempts are not bookings and never appear."""
    purchases = (
        await db.execute(
            select(Purchase)
            .where(Purchase.user_id == current_user.id, Purchase.status.in_(["completed", "refunded"]))
            .order_by(Purchase.created_at.desc(), Purchase.id)
        )
    ).scalars().all()
    if not purchases:
        return []

    tour_ids = {p.tour_id for p in purchases}
    tours = {
        t.id: t
        for t in (await db.execute(select(Tour).where(Tour.id.in_(tour_ids)))).scalars().unique().all()
    }
    stop_counts = {
        row[0]: row[1]
        for row in (
            await db.execute(
                select(Stop.tour_id, func.count(Stop.id)).where(Stop.tour_id.in_(tour_ids)).group_by(Stop.tour_id)
            )
        ).all()
    }
    sessions_by_tour: dict[uuid.UUID, list[TourSession]] = {}
    for sess in (
        await db.execute(
            select(TourSession)
            .where(TourSession.user_id == current_user.id, TourSession.tour_id.in_(tour_ids))
            .order_by(TourSession.started_at.desc())
        )
    ).scalars():
        sessions_by_tour.setdefault(sess.tour_id, []).append(sess)

    now = datetime.now(timezone.utc)
    out: list[BookingOut] = []
    for purchase in purchases:
        sessions = sessions_by_tour.get(purchase.tour_id, [])
        latest = sessions[0] if sessions else None
        if latest is None:
            walk = "not_started"
        elif latest.completed:
            walk = "completed"
        else:
            walk = "in_progress"
        is_past = purchase.status == "refunded" or walk == "completed"
        if (tab == "upcoming" and is_past) or (tab == "past" and not is_past):
            continue
        refundable = _refund_block_reason(purchase, sessions, now) is None
        out.append(
            BookingOut(
                purchase_id=purchase.id,
                status=purchase.status,
                amount_paise=purchase.amount_paise,
                purchased_at=purchase.created_at,
                tour=BookingTour.model_validate(tours[purchase.tour_id]),
                walk_status=walk,
                stops_visited=latest.stops_visited if latest else 0,
                stop_count=stop_counts.get(purchase.tour_id, 0),
                session_id=latest.id if latest and not latest.completed else None,
                device_bound=purchase.device_id is not None,
                can_refund=refundable,
                refund_deadline=_refund_deadline(purchase) if refundable else None,
            )
        )
    return out


@router.get("/purchases/{purchase_id}", response_model=PurchaseOut)
async def get_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current status. If a real payment is still pending, ask the gateway
    directly, so a delayed or lost webhook never strands a paying user
    (Feature Spec 1: manual "check payment status" fallback)."""
    purchase = await _owned_purchase(db, purchase_id, current_user, lock=True)
    if not settings.MOCK_PAYMENTS and purchase.status == "pending" and purchase.gateway_order_id:
        try:
            captured = await payments.fetch_captured_payment(purchase.gateway_order_id)
        except payments.GatewayError:
            captured = None  # gateway unreachable: report what we know
        if captured:
            await payments.apply_payment_result(
                db, purchase, payment_id=captured["id"], succeeded=True, amount_paise=captured.get("amount")
            )
            await db.commit()
            await db.refresh(purchase)
    return purchase


@router.post("/purchases/{purchase_id}/verify", response_model=PurchaseOut)
async def verify_checkout(
    purchase_id: uuid.UUID,
    body: CheckoutVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Called by the app right after Razorpay Checkout succeeds, with the three
    values the SDK returns. The signature proves the payment, so the user gets
    instant confirmation; the webhook later is a harmless no-op."""
    purchase = await _owned_purchase(db, purchase_id, current_user, lock=True)
    if settings.MOCK_PAYMENTS:
        raise _api_error(status.HTTP_400_BAD_REQUEST, "MOCK_MODE_ACTIVE", "Not used while MOCK_PAYMENTS=true.")
    if purchase.gateway_order_id != body.razorpay_order_id or not payments.verify_checkout_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise _api_error(status.HTTP_400_BAD_REQUEST, "INVALID_SIGNATURE", "Payment signature is invalid.")
    await payments.apply_payment_result(db, purchase, payment_id=body.razorpay_payment_id, succeeded=True)
    await db.commit()
    await db.refresh(purchase)
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
            _BOUND_TO_OTHER_DEVICE_MSG,
        )

    purchase.device_id = body.device_identifier
    await db.commit()
    await db.refresh(purchase)
    return purchase


@router.post("/purchases/{purchase_id}/refund", response_model=PurchaseOut)
async def refund_purchase(
    purchase_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full refund, only while the walk has never been started and the purchase
    is within REFUND_WINDOW_DAYS (default 14).

      - not found / not yours ... 404
      - not a completed purchase . 400 PURCHASE_NOT_COMPLETED
      - any stop visited, or walk completed ... 409 REFUND_NOT_ELIGIBLE
      - older than the window ... 409 REFUND_WINDOW_EXPIRED
      - gateway failure ......... 502 GATEWAY_ERROR (nothing is changed; safe to retry)
    """
    purchase = await _owned_purchase(db, purchase_id, current_user, lock=True)
    sessions = (
        await db.execute(
            select(TourSession).where(
                TourSession.user_id == current_user.id, TourSession.tour_id == purchase.tour_id
            )
        )
    ).scalars().all()

    reason = _refund_block_reason(purchase, list(sessions), datetime.now(timezone.utc))
    if reason == "PURCHASE_NOT_COMPLETED":
        raise _api_error(status.HTTP_400_BAD_REQUEST, reason, "Only completed purchases can be refunded.")
    if reason == "REFUND_NOT_ELIGIBLE":
        raise _api_error(status.HTTP_409_CONFLICT, reason, "Refund refused: the walk has already been started.")
    if reason == "REFUND_WINDOW_EXPIRED":
        raise _api_error(
            status.HTTP_409_CONFLICT,
            reason,
            f"Refunds are only available within {settings.REFUND_WINDOW_DAYS} days of purchase.",
        )

    if not settings.MOCK_PAYMENTS and purchase.gateway_payment_id:
        try:
            await payments.refund_payment(purchase.gateway_payment_id, purchase.amount_paise)
        except payments.GatewayError as exc:
            raise _api_error(status.HTTP_502_BAD_GATEWAY, "GATEWAY_ERROR", str(exc))

    purchase.status = "refunded"
    purchase.is_locked = False
    purchase.locked_at = None
    purchase.device_id = None  # the licence is gone, so is the device binding
    await db.commit()
    await db.refresh(purchase)
    return purchase


_SUCCESS_EVENTS = {"payment.captured", "order.paid"}
_FAILURE_EVENTS = {"payment.failed"}


@router.post("/webhooks/payment", status_code=status.HTTP_204_NO_CONTENT)
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Razorpay -> server. Never trusts an unsigned request; idempotent.

      - bad/missing signature ... 401 (nothing is read or stored)
      - already-seen event id ... 204 (replay is a no-op)
      - unknown order/event ..... 204 (so the gateway doesn't retry forever)
    """
    if settings.MOCK_PAYMENTS:
        raise _api_error(status.HTTP_400_BAD_REQUEST, "MOCK_MODE_ACTIVE", "Webhooks are unused while MOCK_PAYMENTS=true.")

    raw = await request.body()
    if not payments.verify_webhook_signature(raw, request.headers.get("X-Razorpay-Signature")):
        raise _api_error(status.HTTP_401_UNAUTHORIZED, "INVALID_SIGNATURE", "Webhook signature is invalid.")

    try:
        payload = json.loads(raw)
        event_type = payload["event"]
    except (ValueError, KeyError, TypeError):
        raise _api_error(status.HTTP_400_BAD_REQUEST, "INVALID_PAYLOAD", "Malformed webhook payload.")

    entities = (payload.get("payload") or {})
    payment = ((entities.get("payment") or {}).get("entity")) or {}
    order = ((entities.get("order") or {}).get("entity")) or {}
    order_id = payment.get("order_id") or order.get("id")
    payment_id = payment.get("id")
    amount = payment.get("amount")
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(raw).hexdigest()

    event = PaymentEvent(
        event_id=event_id,
        event_type=event_type,
        gateway_order_id=order_id,
        gateway_payment_id=payment_id,
        payload=payload,
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        return  # replay of a delivery we already processed

    outcome = "ignored"
    if order_id and event_type in (_SUCCESS_EVENTS | _FAILURE_EVENTS):
        purchase = (
            await db.execute(select(Purchase).where(Purchase.gateway_order_id == order_id).with_for_update())
        ).scalar_one_or_none()
        if purchase is None:
            outcome = "unknown_order"
        elif not payment_id:
            outcome = "ignored"
        else:
            outcome = await payments.apply_payment_result(
                db, purchase, payment_id=payment_id, succeeded=event_type in _SUCCESS_EVENTS, amount_paise=amount
            )
    event.outcome = outcome
    await db.commit()
