import hmac
import hashlib
import json
from fastapi.testclient import TestClient

from webapp import app


def sign(app_secret: str, body: bytes) -> str:
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_get(monkeypatch):
    monkeypatch.setenv("FB_VERIFY_TOKEN", "token123")
    with TestClient(app) as client:
        resp = client.get(
            "/facebook/webhook",
            params={"hub.mode": "subscribe", "hub.verify_token": "token123", "hub.challenge": "abc"},
        )
        assert resp.status_code == 200
        assert resp.text == "abc"


def test_post_signature_and_payload(monkeypatch):
    monkeypatch.setenv("FB_APP_SECRET", "secret")
    # page access token isn't required for inbound tests

    body = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "PSID-1"},
                        "message": {"text": "hello"},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(body).encode("utf-8")
    sig = sign("secret", raw)

    with TestClient(app) as client:
        resp = client.post(
            "/facebook/webhook",
            data=raw,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )
        # We don't assert side-effects; just path acceptance
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
