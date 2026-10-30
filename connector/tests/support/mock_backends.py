"""In-process user and payment APIs for tests.

dispatch does not import this module. tests/test_enterprise.py calls `app`
through httpx.ASGITransport. `python mocks/mock_backends.py` can serve the
same app on 127.0.0.1:8001 for a local HTTP check. It does not execute SQL
and does not stand in for a production database.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, HTTPException

MOCK_REST_HOST = "127.0.0.1"
MOCK_REST_PORT = 8001

USERS: dict[str, dict[str, str]] = {
    "U-1001": {
        "user_id": "U-1001",
        "name": "张三",
        "status": "active",
    },
}

PAYMENTS: dict[str, dict[str, str]] = {
    "P-3001": {
        "payment_id": "P-3001",
        "order_id": "O-2001",
        "amount": "128.00",
        "status": "paid",
        "channel": "card",
    },
}

app = FastAPI(title="commerce-user-sample", version="0.1.0")


@app.get("/api/users/{user_id}")
def get_user(user_id: str) -> dict[str, str]:
    row = USERS.get(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"user not found: {user_id}")
    return row


@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str) -> dict[str, str]:
    row = PAYMENTS.get(payment_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"payment not found: {payment_id}")
    return row


def start_mock_server(host: str = MOCK_REST_HOST, port: int = MOCK_REST_PORT) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start_mock_server()
