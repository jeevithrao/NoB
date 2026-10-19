import hashlib
import hmac
import json
import uuid

import httpx

KEY_ID, KEY_SECRET, WEBHOOK_SECRET = "rzp_test_key", "test-key-secret", "test-webhook-secret"


class FakeRazorpay:
    """Stand-in for api.razorpay.com, plugged in through httpx.MockTransport."""

    def __init__(self):
        self.orders_created: list[dict] = []
        self.payments_by_order: dict[str, list[dict]] = {}
        self.refunds: list[tuple[str, int]] = []
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503, json={"error": "down"})
        path = request.url.path
        if request.method == "POST" and path.endswith("/orders"):
            body = json.loads(request.content)
            order = {"id": f"order_{uuid.uuid4().hex[:14]}", **body}
            self.orders_created.append(order)
            return httpx.Response(200, json=order)
        if request.method == "GET" and "/orders/" in path and path.endswith("/payments"):
            order_id = path.split("/orders/")[1].split("/")[0]
            return httpx.Response(200, json={"items": self.payments_by_order.get(order_id, [])})
        if request.method == "POST" and "/payments/" in path and path.endswith("/refund"):
            payment_id = path.split("/payments/")[1].split("/")[0]
            self.refunds.append((payment_id, json.loads(request.content)["amount"]))
            return httpx.Response(200, json={"id": f"rfnd_{uuid.uuid4().hex[:8]}"})
        return httpx.Response(404)


def checkout_signature(order_id: str, payment_id: str, secret: str = KEY_SECRET) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def webhook_body(event: str, order_id: str, payment_id: str, amount: int) -> bytes:
    return json.dumps(
        {
            "event": event,
            "payload": {
                "payment": {"entity": {"id": payment_id, "order_id": order_id, "amount": amount, "status": "captured"}}
            },
        }
    ).encode()


async def send_webhook(client, body: bytes, *, event_id: str | None = None, secret: str = WEBHOOK_SECRET, signature: str | None = None):
    sig = signature if signature is not None else hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
    if event_id:
        headers["X-Razorpay-Event-Id"] = event_id
    return await client.post("/webhooks/payment", content=body, headers=headers)
