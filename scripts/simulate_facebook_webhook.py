"""
Facebook Messenger Webhook Simulator
------------------------------------
Purpose: Send realistic webhook POSTs to your FastAPI endpoint to validate
the SmartMessageAggregator merges text + image into a single processing unit.

It can generate:
- A text-only event
- One or more image-attachment events
- Or a single combined event (text + attachments in one message)

The request is signed with X-Hub-Signature-256 using FB_APP_SECRET so your
"/facebook/webhook" endpoint will accept it.

Notes
- Avoid PSIDs starting with "TEST_" (the service ignores those by design).
- You can also supply a --log-file to auto-extract image URLs from your logs
  (regex http(s)://...). If --image is omitted and --log-file is provided,
  top URLs found will be used.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import random
import re
import time
import uuid
from typing import List, Dict, Any, Optional

import httpx
from threading import Event
from dotenv import load_dotenv


def sign_body(app_secret: str, body: bytes) -> str:
    mac = hmac.new(app_secret.encode("utf-8"), msg=body, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"


def build_message_text(psid: str, page_id: str, text: str, ts_ms: int | None = None) -> Dict[str, Any]:
    ts = ts_ms or int(time.time() * 1000)
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": ts,
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": page_id},
                        "timestamp": ts,
                        "message": {
                            "mid": f"m_{uuid.uuid4().hex}",
                            "seq": random.randint(1, 1000000),
                            "text": text,
                        },
                    }
                ],
            }
        ],
    }


def build_message_image(psid: str, page_id: str, image_url: str, ts_ms: int | None = None) -> Dict[str, Any]:
    ts = ts_ms or int(time.time() * 1000)
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": ts,
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": page_id},
                        "timestamp": ts,
                        "message": {
                            "mid": f"m_{uuid.uuid4().hex}",
                            "seq": random.randint(1, 1000000),
                            "attachments": [
                                {"type": "image", "payload": {"url": image_url, "is_reusable": True}}
                            ],
                        },
                    }
                ],
            }
        ],
    }


def build_message_combined(psid: str, page_id: str, text: str, image_urls: List[str], ts_ms: int | None = None) -> Dict[str, Any]:
    ts = ts_ms or int(time.time() * 1000)
    attachments = [
        {"type": "image", "payload": {"url": url, "is_reusable": True}} for url in image_urls
    ]
    return {
        "object": "page",
        "entry": [
            {
                "id": page_id,
                "time": ts,
                "messaging": [
                    {
                        "sender": {"id": psid},
                        "recipient": {"id": page_id},
                        "timestamp": ts,
                        "message": {
                            "mid": f"m_{uuid.uuid4().hex}",
                            "seq": random.randint(1, 1000000),
                            "text": text,
                            "attachments": attachments,
                        },
                    }
                ],
            }
        ],
    }


def extract_urls_from_log(path: str, limit: int = 5) -> List[str]:
    """Extract http(s) URLs from a log/text file (best-effort)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"Could not read log file {path}: {e}")
        return []
    urls = re.findall(r"https?://[^\s\)\]\}\>\<\"]+", content)
    # Keep only images by extension hint if possible
    image_like = [u for u in urls if re.search(r"\.(jpg|jpeg|png|gif|webp)(\?|$)", u, re.IGNORECASE)]
    return (image_like or urls)[:limit]


async def post_signed(url: str, payload: Dict[str, Any], app_secret: str) -> httpx.Response:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sig = sign_body(app_secret, body)
    headers = {"Content-Type": "application/json", "X-Hub-Signature-256": sig}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, headers=headers, content=body)
        return resp


def _read_new_lines(path: str, start_pos: int) -> tuple[list[str], int]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(start_pos)
            data = f.read()
            new_pos = f.tell()
    except FileNotFoundError:
        return [], start_pos
    except Exception:
        return [], start_pos
    if not data:
        return [], new_pos
    # Normalize Windows newlines
    lines = data.replace("\r\n", "\n").splitlines()
    return lines, new_pos


def analyze_merge_logs(lines: list[str], psid: str, run_tag: Optional[str]) -> dict:
    """Best-effort heuristic to detect whether a single aggregated processing occurred.

    Looks for common aggregator keywords and counts processing events.
    """
    kw = [
        "SmartMessageAggregator",
        "aggregate",
        "aggregat",  # broader match
        "combine",
        "merged",
        "context_key",
        "Processing aggregated",
        "process_complete",
        "process_complete_message",
        "timeout",
        "dedup",
    ]
    matched = []
    for ln in lines:
        lower = ln.lower()
        if any(k.lower() in lower for k in kw):
            if (psid and psid in ln) or (run_tag and run_tag in ln) or True:
                matched.append(ln)

    # Simple counters
    processed_count = sum(
        1 for ln in matched if "process_complete" in ln.lower() or "processing aggregated" in ln.lower()
    )
    merged_mentions = sum(1 for ln in matched if "merged" in ln.lower() or "combine" in ln.lower())
    timeout_mentions = sum(1 for ln in matched if "timeout" in ln.lower())

    success = processed_count == 1 and timeout_mentions <= 1

    return {
        "matched_count": len(matched),
        "processed_count": processed_count,
        "merged_mentions": merged_mentions,
        "timeout_mentions": timeout_mentions,
        "sample": matched[-10:],
        "success": success,
    }


async def watch_logs_for_merge(path: str, start_pos: int, psid: str, run_tag: Optional[str], window_secs: float = 20.0) -> dict:
    """Poll a server log file for a short window and summarize merge/combine signals."""
    if not path:
        return {"skipped": True}
    pos = start_pos
    collected: list[str] = []
    t0 = time.monotonic()
    while time.monotonic() - t0 < window_secs:
        lines, pos = await asyncio.to_thread(_read_new_lines, path, pos)
        if lines:
            collected.extend(lines)
        await asyncio.sleep(0.25)
    return analyze_merge_logs(collected, psid=psid, run_tag=run_tag)


async def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Simulate Facebook Messenger webhook events")
    parser.add_argument("--base-url", default="http://127.0.0.1:2024/facebook/webhook", help="Webhook URL")
    parser.add_argument("--psid", default="123456789012345", help="Sender PSID (avoid values starting with TEST_)")
    parser.add_argument("--page-id", default="999999999999999", help="Page ID")
    parser.add_argument("--text", default="giải thích cho anh hình ảnh này", help="Text content")
    parser.add_argument("--image", action="append", dest="images", default=[], help="Image URL (repeatable)")
    parser.add_argument("--log-file", default="", help="Optional log file to auto-extract image URLs")
    parser.add_argument("--delay", type=float, default=2.5, help="Delay (s) between text and image events")
    parser.add_argument("--combined", action="store_true", help="Send a single combined message (text+attachments)")
    parser.add_argument("--count", type=int, default=1, help="How many times to run the sequence")
    parser.add_argument("--app-secret", default=os.getenv("FB_APP_SECRET", ""), help="FB App Secret for signing")
    parser.add_argument("--server-log", default=os.getenv("SERVER_LOG", "log-console.txt"), help="Path to server log to watch")
    parser.add_argument("--tag", default="", help="Optional run tag to inject into text for log correlation (e.g., SIM_RUN=XYZ)")
    args = parser.parse_args()

    if not args.app_secret:
        raise SystemExit("FB_APP_SECRET not provided. Set --app-secret or export FB_APP_SECRET in your environment.")

    images: List[str] = list(args.images)
    if not images and args.log_file and os.path.exists(args.log_file):
        images = extract_urls_from_log(args.log_file, limit=5)
        if images:
            print(f"Extracted {len(images)} URL(s) from log: {images}")

    # Prepare a run correlation tag that will be included in text
    run_tag = args.tag or f"SIM_RUN={uuid.uuid4().hex[:8]}"

    # Capture starting offset for log tailing
    start_pos = 0
    if args.server_log and os.path.exists(args.server_log):
        try:
            start_pos = os.path.getsize(args.server_log)
        except Exception:
            start_pos = 0

    for i in range(args.count):
        ts_now = int(time.time() * 1000)
        if args.combined:
            payload = build_message_combined(args.psid, args.page_id, f"{args.text} [{run_tag}]", images or [], ts_now)
            resp = await post_signed(args.base_url, payload, args.app_secret)
            print(f"[combined#{i+1}] status={resp.status_code} body={resp.text}")
        else:
            # Text-first
            text_payload = build_message_text(args.psid, args.page_id, f"{args.text} [{run_tag}]", ts_now)
            resp1 = await post_signed(args.base_url, text_payload, args.app_secret)
            print(f"[text   #{i+1}] status={resp1.status_code} body={resp1.text}")

            # Optional small delay then each image as a separate webhook
            if images:
                await asyncio.sleep(args.delay)
                for idx, url in enumerate(images, start=1):
                    img_payload = build_message_image(args.psid, args.page_id, url, ts_now + idx)
                    resp2 = await post_signed(args.base_url, img_payload, args.app_secret)
                    print(f"[image{idx:02d}#{i+1}] status={resp2.status_code} body={resp2.text}")

    # After sending, watch logs briefly to infer whether merge succeeded
    summary = await watch_logs_for_merge(
        path=args.server_log,
        start_pos=start_pos,
        psid=args.psid,
        run_tag=run_tag,
        window_secs=20.0,
    )
    if summary.get("skipped"):
        print("[merge-check] Skipped log watch (no server log path provided)")
    else:
        print("[merge-check] Summary:")
        print(
            json.dumps(
                {
                    k: (v if k != "sample" else v) for k, v in summary.items()
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
