#!/usr/bin/env python3
"""
Crazy Carla YouTube updater.

This version is deliberately strict:
- It reads Carla's public Videos, Shorts, and Live tabs with yt-dlp.
- It merges and sorts all candidates by the best available upload timestamp.
- It writes exactly the newest 4 public uploads to data/youtube-videos.json.
- It does NOT silently keep stale data when YouTube cannot be read.
  A failed refresh must fail the GitHub Action so the problem is visible.
- It records last_checked_at every successful run so we can prove the updater ran.

No YouTube login or API key is required.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yt_dlp

HANDLE = "10aahfro"
CHANNEL_URL = f"https://www.youtube.com/@{HANDLE}"
VIDEO_LIMIT = 4
CANDIDATES_PER_TAB = 15

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "youtube-videos.json"

TAB_URLS = [
    f"{CHANNEL_URL}/videos",
    f"{CHANNEL_URL}/shorts",
    f"{CHANNEL_URL}/streams",
]

BASE_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "ignoreerrors": True,
    "socket_timeout": 30,
    "retries": 5,
    "extractor_retries": 5,
    "geo_bypass": True,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ydl_extract(url: str, *, flat: bool) -> dict[str, Any] | None:
    opts = dict(BASE_OPTS)
    opts["extract_flat"] = "in_playlist" if flat else False
    if flat:
        opts["playlistend"] = CANDIDATES_PER_TAB

    last_error: Exception | None = None

    for attempt in range(3):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info if isinstance(info, dict) else None
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)

    if last_error:
        print(f"ERROR reading {url}: {last_error}", file=sys.stderr)
    return None


def parse_timestamp(info: dict[str, Any]) -> int | None:
    for key in (
        "timestamp",
        "release_timestamp",
        "modified_timestamp",
    ):
        value = info.get(key)
        if isinstance(value, (int, float)):
            return int(value)

    for key in ("upload_date", "release_date"):
        value = info.get(key)
        if isinstance(value, str) and len(value) == 8 and value.isdigit():
            try:
                dt = datetime.strptime(value, "%Y%m%d").replace(
                    hour=12,
                    tzinfo=timezone.utc,
                )
                return int(dt.timestamp())
            except ValueError:
                pass

    return None


def normalize_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    video_id = entry.get("id")
    if not isinstance(video_id, str) or not video_id:
        return None

    return {
        "id": video_id,
        "title": entry.get("title") or "Crazy Carla video",
        "description": entry.get("description") or "",
        "timestamp": parse_timestamp(entry),
        "channel_id": entry.get("channel_id") or "",
    }


def collect_candidates() -> dict[str, dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    successful_tabs = 0

    for tab_url in TAB_URLS:
        print(f"Reading {tab_url}")
        info = ydl_extract(tab_url, flat=True)
        if not info:
            continue

        entries = info.get("entries")
        if not isinstance(entries, list):
            continue

        usable = 0
        for raw in entries[:CANDIDATES_PER_TAB]:
            if not isinstance(raw, dict):
                continue

            item = normalize_entry(raw)
            if not item:
                continue

            usable += 1
            old = candidates.get(item["id"])
            if old is None:
                candidates[item["id"]] = item
            elif not old.get("timestamp") and item.get("timestamp"):
                candidates[item["id"]] = item

        if usable:
            successful_tabs += 1
            print(f"  Found {usable} candidate(s).")

    if successful_tabs == 0 or not candidates:
        raise RuntimeError(
            "Could not read any usable uploads from Carla's Videos, Shorts, or Live tabs."
        )

    print(f"Collected {len(candidates)} unique candidate(s).")
    return candidates


def enrich(candidate: dict[str, Any]) -> dict[str, Any] | None:
    video_id = candidate["id"]
    info = ydl_extract(f"https://www.youtube.com/watch?v={video_id}", flat=False)

    if not info:
        # Keep a flat entry only if it already has a reliable timestamp.
        return candidate if candidate.get("timestamp") else None

    timestamp = parse_timestamp(info) or candidate.get("timestamp")
    if not timestamp:
        return None

    return {
        "id": video_id,
        "title": info.get("title") or candidate.get("title") or "Crazy Carla video",
        "description": info.get("description") or candidate.get("description") or "",
        "timestamp": int(timestamp),
        "channel_id": info.get("channel_id") or candidate.get("channel_id") or "",
    }


def make_video(item: dict[str, Any]) -> dict[str, str]:
    video_id = str(item["id"])
    timestamp = int(item["timestamp"])

    return {
        "id": video_id,
        "title": str(item.get("title") or "Crazy Carla video"),
        "published": datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        ).isoformat(),
        "description": str(item.get("description") or "")[:300],
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def get_newest_four() -> tuple[list[dict[str, str]], str]:
    candidates = collect_candidates()
    enriched: list[dict[str, Any]] = []

    # Enrich every candidate. This costs a few more requests, but avoids the
    # exact problem the old updater had: channel-page metadata can be incomplete.
    for index, candidate in enumerate(candidates.values(), start=1):
        print(
            f"Resolving {index}/{len(candidates)}: "
            f"{candidate['id']} - {candidate.get('title', '')[:70]}"
        )
        full = enrich(candidate)
        if full and full.get("timestamp"):
            enriched.append(full)

    if len(enriched) < VIDEO_LIMIT:
        raise RuntimeError(
            f"Only {len(enriched)} uploads had usable dates; need {VIDEO_LIMIT}."
        )

    enriched.sort(key=lambda item: int(item["timestamp"]), reverse=True)
    selected = enriched[:VIDEO_LIMIT]

    channel_id = next(
        (
            str(item.get("channel_id"))
            for item in selected
            if isinstance(item.get("channel_id"), str) and item.get("channel_id")
        ),
        "",
    )

    return [make_video(item) for item in selected], channel_id


def read_existing() -> dict[str, Any]:
    if not OUT.exists():
        return {}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    old = read_existing()
    old_ids = [
        item.get("id")
        for item in old.get("videos", [])
        if isinstance(item, dict)
    ][:VIDEO_LIMIT]

    videos, channel_id = get_newest_four()
    new_ids = [item["id"] for item in videos]

    payload = {
        "channel_handle": f"@{HANDLE}",
        "channel_id": channel_id or old.get("channel_id", ""),
        "last_checked_at": now_iso(),
        "updated_at": now_iso(),
        "videos": videos,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("")
    print("Newest 4 uploads selected:")
    for number, video in enumerate(videos, start=1):
        print(f"  {number}. {video['published']} | {video['id']} | {video['title']}")

    if old_ids == new_ids:
        print("")
        print("The selected video IDs are unchanged, but the successful check timestamp was refreshed.")
    else:
        print("")
        print(f"Changed IDs: {old_ids} -> {new_ids}")

    print(f"Wrote: {OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("", file=sys.stderr)
        print(f"YOUTUBE REFRESH FAILED: {exc}", file=sys.stderr)
        print(
            "The existing JSON was NOT silently accepted as current.",
            file=sys.stderr,
        )
        raise
