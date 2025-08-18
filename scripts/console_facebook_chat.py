"""
Interactive console chat simulator for Facebook Messenger webhook.
- Sends signed POSTs to /api/facebook/webhook with realistic payloads.
- Polls a debug endpoint to print bot replies in the console.

Prereqs:
- Server running with the Facebook router mounted under /api (webapp.py or app.py as configured)
- Env: FB_APP_SECRET set, ALLOW_FB_DEBUG=1 on the server to enable /api/facebook/debug/conversation

Usage (Windows PowerShell):
  .\.venv\Scripts\python.exe scripts/console_facebook_chat.py --base http://127.0.0.1:2024/api --psid 123456789012345
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from typing import Dict, Any

import requests
from dotenv import load_dotenv


def sign_body(app_secret: str, body: bytes) -> str:
    mac = hmac.new(app_secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def build_payload(psid: str, page_id: str, text: str) -> Dict[str, Any]:
    now_ms = int(time.time() * 1000)
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": int(now_ms / 1000),
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": page_id},
                        "timestamp": now_ms,
                        "message": {
                            "mid": f"m_{now_ms}",
                            "text": text,
                        },
                    }
                ],
            }
        ],
    }


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Console Facebook chat simulator")
    parser.add_argument("--base", default="http://127.0.0.1:2024/api", help="Base server URL (without trailing slash)")
    parser.add_argument("--psid", default="123456789012345", help="Sender PSID (digits)")
    parser.add_argument("--page-id", default="999999999999999", help="Page ID")
    parser.add_argument("--app-secret", default=os.getenv("FB_APP_SECRET", ""), help="FB App Secret for signing")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="Seconds between conversation polls")
    args = parser.parse_args()

    if not args.app_secret:
        print("ERROR: FB_APP_SECRET missing. Provide --app-secret or set env FB_APP_SECRET.")
        raise SystemExit(2)

    webhook_url = args.base.rstrip("/") + "/facebook/webhook"
    convo_url = args.base.rstrip("/") + "/facebook/debug/conversation"

    print("Interactive chat. Type a message and press Enter. Type /quit to exit.\n")
    print(f"Webhook: {webhook_url}")
    print(f"Debug conversation: {convo_url} (server must set ALLOW_FB_DEBUG=1)")

    last_seen_count = 0
    try:
        while True:
            text = input("You: ").strip()
            if not text:
                continue
            if text.lower() in {"/quit", ":q", "exit"}:
                break

            payload = build_payload(args.psid, args.page_id, text)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "X-Hub-Signature-256": sign_body(args.app_secret, body),
            }

            try:
                resp = requests.post(webhook_url, data=body, headers=headers, timeout=10)
                print(f"-> sent ({resp.status_code})")
            except Exception as e:
                print(f"Send error: {e}")
                continue

            # Poll conversation to display new bot replies
            # We poll a few times quickly after each send
            for _ in range(10):
                try:
                    r = requests.get(convo_url, params={"psid": args.psid, "limit": 6}, timeout=5)
                    if r.status_code == 200:
                        data = r.json()
                        msgs = data.get("messages", [])
                        # Print any new messages since last check
                        if len(msgs) > last_seen_count:
                            # Show only the new tail
                            new_msgs = msgs[: len(msgs) - last_seen_count]
                            for m in reversed(new_msgs):  # oldest to newest
                                who = "Bot" if not m.get("is_from_user") else "You"
                                content = m.get("content", "").strip()
                                print(f"{who}: {content}")
                            last_seen_count = len(msgs)
                    else:
                        # Silent if debug disabled
                        pass
                except Exception:
                    pass
                time.sleep(args.poll_interval)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
