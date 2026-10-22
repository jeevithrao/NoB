"""A tiny stand-in for the Razorpay REST API, for local end-to-end tests only.

    python backend/scripts/fake_razorpay.py            # listens on :9000
    RAZORPAY_API_BASE=http://localhost:9000/v1 RAZORPAY_KEY_ID=rzp_test_fake \
    RAZORPAY_KEY_SECRET=fakesecret RAZORPAY_WEBHOOK_SECRET=fakewebhook MOCK_PAYMENTS=false uvicorn app.main:app

It creates orders and reports no captured payments. It proves OUR code path, not Razorpay's: real test keys are still needed.
"""
import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer


class H(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path.endswith("/orders"):
            return self._send(200, {"id": "order_" + uuid.uuid4().hex[:14], "amount": body.get("amount"), "currency": body.get("currency"), "status": "created"})
        self._send(404, {"error": "unknown"})

    def do_GET(self):
        if "/orders/" in self.path and self.path.endswith("/payments"):
            return self._send(200, {"items": []})
        self._send(404, {"error": "unknown"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9000), H).serve_forever()
