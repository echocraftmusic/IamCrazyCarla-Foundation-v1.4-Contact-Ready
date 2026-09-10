#!/usr/bin/env python3
"""Update Crazy Carla's website with her four newest PUBLIC YouTube uploads.

This version uses the official YouTube Data API v3 instead of scraping YouTube.
That avoids GitHub Actions being blocked by YouTube's "confirm you're not a bot"
challenge.

Required environment variable:
    YOUTUBE_API_KEY

The key only needs read access to the public YouTube Data API. No Carla login,
OAuth token, cookies, or browser session is required.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HANDLE = "10aahfro"
VIDEO_LIMIT = 4
LOOKAHEAD = 15

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "youtube-videos.json"
API_BASE = "https://www.googleapis.com/youtube/v3"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def api_get(resource: str, **params: str | int) -> dict[str, Any]:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Missing YOUTUBE_API_KEY. Add it as a GitHub Actions repository "
            "secret before running this workflow."
        )

    query = dict(params)
    query["key"] = key
    url = f"{API_BASE}/{resource}?{urllib.parse.urlencode(query)}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "CrazyCarlaWebsite/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body)
            message = (
                detail.get("error", {})
                .get("message", body)
            )
        except json.JSONDecodeError:
            message = body or str(exc)
        raise RuntimeError(
            f"YouTube Data API returned HTTP {exc.code}: {message}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach YouTube Data API: {exc}") from exc


def get_channel() -> tuple[str, str]:
    data = api_get(
        "channels",
        part="id,contentDetails",
        forHandle=f"@{HANDLE}",
        maxResults=1,
    )

    items = data.get("items", [])
    if not items:
        raise RuntimeError(
            f"YouTube could not find the channel for @{HANDLE}."
        )

    channel = items[0]
    channel_id = channel.get("id", "")
    uploads_id = (
        channel.get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads", "")
    )

    if not channel_id or not uploads_id:
        raise RuntimeError(
            "YouTube returned the channel but not its uploads playlist."
        )

    return channel_id, uploads_id


def get_recent_upload_ids(uploads_id: str) -> list[str]:
    data = api_get(
        "playlistItems",
        part="snippet,contentDetails",
        playlistId=uploads_id,
        maxResults=LOOKAHEAD,
    )

    ids: list[str] = []
    seen: set[str] = set()

    for item in data.get("items", []):
        video_id = (
            item.get("contentDetails", {}).get("videoId")
            or item.get("snippet", {})
            .get("resourceId", {})
            .get("videoId")
        )

        if video_id and video_id not in seen:
            seen.add(video_id)
            ids.append(video_id)

    if not ids:
        raise RuntimeError("The uploads playlist did not return any videos.")

    return ids


def get_video_details(video_ids: list[str]) -> list[dict[str, str]]:
    data = api_get(
        "videos",
        part="snippet,status",
        id=",".join(video_ids[:50]),
        maxResults=min(len(video_ids), 50),
    )

    videos: list[dict[str, str]] = []

    for item in data.get("items", []):
        video_id = item.get("id", "")
        snippet = item.get("snippet", {})
        status = item.get("status", {})

        # Do not feature private/unlisted items or scheduled future streams.
        if status.get("privacyStatus") != "public":
            continue
        if snippet.get("liveBroadcastContent") == "upcoming":
            continue

        published = snippet.get("publishedAt", "")
        if not video_id or not published:
            continue

        title = snippet.get("title") or "Crazy Carla video"
        description = snippet.get("description") or ""

        thumbs = snippet.get("thumbnails", {})
        thumbnail = ""
        for size in ("maxres", "standard", "high", "medium", "default"):
            candidate = thumbs.get(size, {}).get("url")
            if candidate:
                thumbnail = candidate
                break
        if not thumbnail:
            thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        videos.append(
            {
                "id": video_id,
                "title": title,
                "published": published,
                "description": description[:300],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": thumbnail,
            }
        )

    videos.sort(
        key=lambda video: datetime.fromisoformat(
            video["published"].replace("Z", "+00:00")
        ),
        reverse=True,
    )

    if len(videos) < VIDEO_LIMIT:
        raise RuntimeError(
            f"YouTube returned only {len(videos)} usable public uploads; "
            f"{VIDEO_LIMIT} are required."
        )

    return videos[:VIDEO_LIMIT]


def main() -> int:
    channel_id, uploads_id = get_channel()
    recent_ids = get_recent_upload_ids(uploads_id)
    videos = get_video_details(recent_ids)

    checked_at = now_iso()
    payload = {
        "channel_handle": f"@{HANDLE}",
        "channel_id": channel_id,
        "last_checked_at": checked_at,
        "updated_at": checked_at,
        "videos": videos,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Channel: @{HANDLE} ({channel_id})")
    print(f"Uploads playlist: {uploads_id}")
    print("Newest four public uploads:")
    for index, video in enumerate(videos, start=1):
        print(
            f"  {index}. {video['published']} | "
            f"{video['id']} | {video['title']}"
        )
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"YouTube update failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
