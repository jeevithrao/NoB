"""Razorpay integration + the purchase payment state machine.

Everything money-related funnels through `apply_payment_result`, which is the
single place a purchase becomes `completed` or `failed`. It is idempotent: the
checkout-verify endpoint, the webhook and the "check status" fallback can all
report the same payment in any order, any number of times.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Purchase

logger = logging.getLogger("nob.payments")

# Tests inject an httpx.MockTransport here; production leaves it None.
_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    global _transport
    _transport = transport


class GatewayError(Exception):
    """The payment provider could not be reached or rejected the request."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.RAZORPAY_API_BASE,
        auth=(settings.RAZORPAY_KEY_ID or "", settings.RAZORPAY_KEY_SECRET or ""),
        timeout=15,
        transport=_transport,
    )


# --------------------------------------------------------------------------- signatures

def _hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_checkout_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Razorpay Checkout returns signature = HMAC_SHA256(order_id|payment_id, key_secret)."""
    if not settings.RAZORPAY_KEY_SECRET or not signature:
        return False
    expected = _hmac_hex(settings.RAZORPAY_KEY_SECRET, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature)


def verify_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Webhooks carry X-Razorpay-Signature = HMAC_SHA256(raw body, webhook secret)."""
    if not settings.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected = _hmac_hex(settings.RAZORPAY_WEBHOOK_SECRET, raw_body)
    return hmac.compare_digest(expected, signature)


# --------------------------------------------------------------------------- gateway calls

async def create_order(purchase: Purchase) -> str:
    """Create a Razorpay order for this purchase and return its id."""
    try:
        async with _client() as client:
            resp = await client.post(
                "/orders",
                json={
                    "amount": purchase.amount_paise,
                    "currency": settings.PAYMENT_CURRENCY,
                    "receipt": str(purchase.id),
                    "notes": {"purchase_id": str(purchase.id), "tour_id": str(purchase.tour_id)},
                },
            )
        resp.raise_for_status()
        return resp.json()["id"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.error("Razorpay order creation failed for purchase %s: %s", purchase.id, exc)
        raise GatewayError("Could not create the payment order.") from exc


async def fetch_captured_payment(order_id: str) -> dict | None:
    """Ask Razorpay whether this order has a captured payment (webhook fallback)."""
    try:
        async with _client() as client:
            resp = await client.get(f"/orders/{order_id}/payments")
        resp.raise_for_status()
        for item in resp.json().get("items", []):
            if item.get("status") == "captured":
                return item
        return None
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("Razorpay payment lookup failed for order %s: %s", order_id, exc)
        raise GatewayError("Could not check the payment status.") from exc


async def refund_payment(payment_id: str, amount_paise: int) -> None:
    """Issue a full refund of a captured payment."""
    try:
        async with _client() as client:
            resp = await client.post(f"/payments/{payment_id}/refund", json={"amount": amount_paise})
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Razorpay refund failed for payment %s: %s", payment_id, exc)
        raise GatewayError("The refund could not be processed. Please try again.") from exc


def checkout_config(purchase: Purchase) -> dict:
    """What the mobile/web SDK needs to open Razorpay Checkout. The key id is
    public by design; the key SECRET never leaves the server."""
    return {
        "provider": "razorpay",
        "key_id": settings.RAZORPAY_KEY_ID,
        "order_id": purchase.gateway_order_id,
        "amount": purchase.amount_paise,
        "currency": settings.PAYMENT_CURRENCY,
        "name": settings.PAYMENT_MERCHANT_NAME,
    }


# --------------------------------------------------------------------------- state machine

async def _has_other_active_purchase(db: AsyncSession, purchase: Purchase) -> bool:
    result = await db.execute(
        select(Purchase.id).where(
            Purchase.user_id == purchase.user_id,
            Purchase.tour_id == purchase.tour_id,
            Purchase.id != purchase.id,
            Purchase.status.in_(["pending", "completed"]),
        )
    )
    return result.first() is not None


async def apply_payment_result(
    db: AsyncSession,
    purchase: Purchase,
    *,
    payment_id: str,
    succeeded: bool,
    amount_paise: int | None = None,
) -> str:
    """Move a purchase according to a payment outcome. Returns what happened:
    completed | already_completed | failed | ignored.  Never raises for a replay."""
    if purchase.status == "refunded":
        return "ignored"  # a late event must not resurrect a refunded purchase

    if succeeded:
        if amount_paise is not None and amount_paise != purchase.amount_paise:
            logger.error(
                "Amount mismatch on purchase %s: paid %s, expected %s; NOT completing",
                purchase.id, amount_paise, purchase.amount_paise,
            )
            return "ignored"
        if purchase.status == "completed":
            if purchase.gateway_payment_id not in (None, payment_id):
                logger.error(
                    "Purchase %s already completed with payment %s but order also paid by %s; refund manually",
                    purchase.id, purchase.gateway_payment_id, payment_id,
                )
            return "already_completed"
        if purchase.status == "failed" and await _has_other_active_purchase(db, purchase):
            logger.error(
                "Late payment %s for failed purchase %s but the user has another active purchase; refund manually",
                payment_id, purchase.id,
            )
            return "ignored"
        purchase.status = "completed"
        purchase.gateway_payment_id = payment_id
        return "completed"

    # failure
    if purchase.status == "pending":
        purchase.status = "failed"
        return "failed"
    return "ignored"  # completed/failed/refunded stay as they are
