#!/usr/bin/env python3
"""Refresh Crazy Carla's website with her four newest public YouTube uploads.

This updater intentionally uses yt-dlp instead of scraping YouTube's raw HTML.
YouTube changes its page markup often; yt-dlp is maintained specifically to
track those changes and is therefore a much more reliable source for this job.

The script checks Carla's Videos, Shorts, and Live tabs, enriches candidates
with real upload timestamps when needed, merges them, sorts newest-first, and
writes exactly four records to data/youtube-videos.json.
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
CANDIDATES_PER_TAB = 12
OUT = Path(__file__).resolve().parents[1] / "data" / "youtube-videos.json"

TAB_URLS = (
    f"{CHANNEL_URL}/videos",
    f"{CHANNEL_URL}/shorts",
    f"{CHANNEL_URL}/streams",
)

COMMON_OPTS: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "ignoreerrors": True,
    "socket_timeout": 30,
    "retries": 3,
    "extractor_retries": 3,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    },
}


def ydl_extract(url: str, *, flat: bool) -> dict[str, Any] | None:
    """Extract one URL with retries and return yt-dlp metadata."""
    opts = dict(COMMON_OPTS)
    opts.update(
        {
            "extract_flat": "in_playlist" if flat else False,
            "playlistend": CANDIDATES_PER_TAB if flat else None,
        }
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            return info if isinstance(info, dict) else None
        except Exception as exc:  # yt-dlp raises several extractor exceptions
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)

    if last_error:
        print(f"Warning: could not read {url}: {last_error}", file=sys.stderr)
    return None


def normalize_timestamp(info: dict[str, Any]) -> int | None:
    """Return the best available Unix timestamp from yt-dlp metadata."""
    for key in ("timestamp", "release_timestamp", "modified_timestamp"):
        value = info.get(key)
        if isinstance(value, (int, float)):
            return int(value)

    # upload_date is YYYYMMDD. Noon UTC avoids edge cases while preserving day.
    upload_date = info.get("upload_date") or info.get("release_date")
    if isinstance(upload_date, str) and len(upload_date) == 8 and upload_date.isdigit():
        try:
            dt = datetime.strptime(upload_date, "%Y%m%d").replace(
                hour=12, tzinfo=timezone.utc
            )
            return int(dt.timestamp())
        except ValueError:
            pass

    return None


def candidate_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    video_id = entry.get("id")
    if not isinstance(video_id, str) or not video_id:
        return None

    return {
        "id": video_id,
        "title": entry.get("title") or "Crazy Carla video",
        "description": entry.get("description") or "",
        "timestamp": normalize_timestamp(entry),
        "channel_id": entry.get("channel_id") or entry.get("channel"),
    }


def collect_candidates() -> dict[str, dict[str, Any]]:
    """Collect the newest IDs from Videos, Shorts, and Live tabs."""
    candidates: dict[str, dict[str, Any]] = {}
    successful_tabs = 0

    for tab_url in TAB_URLS:
        info = ydl_extract(tab_url, flat=True)
        if not info:
            continue

        entries = info.get("entries")
        if not isinstance(entries, list):
            continue

        successful_tabs += 1
        for raw in entries[:CANDIDATES_PER_TAB]:
            if not isinstance(raw, dict):
                continue
            candidate = candidate_from_entry(raw)
            if candidate:
                existing = candidates.get(candidate["id"])
                if existing is None:
                    candidates[candidate["id"]] = candidate
                elif not existing.get("timestamp") and candidate.get("timestamp"):
                    candidates[candidate["id"]] = candidate

    if successful_tabs == 0 or not candidates:
        raise RuntimeError("YouTube returned no usable Videos, Shorts, or Live entries")

    return candidates


def enrich_candidate(candidate: dict[str, Any]) -> dict[str, Any] | None:
    """Fetch full metadata when the flat channel listing lacks a real date."""
    video_id = candidate["id"]
    info = ydl_extract(f"https://www.youtube.com/watch?v={video_id}", flat=False)
    if not info:
        return candidate if candidate.get("timestamp") else None

    timestamp = normalize_timestamp(info) or candidate.get("timestamp")
    if not timestamp:
        return None

    return {
        "id": video_id,
        "title": info.get("title") or candidate.get("title") or "Crazy Carla video",
        "description": info.get("description") or candidate.get("description") or "",
        "timestamp": timestamp,
        "channel_id": info.get("channel_id") or candidate.get("channel_id"),
    }


def published_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def make_video(info: dict[str, Any]) -> dict[str, str]:
    video_id = info["id"]
    return {
        "id": video_id,
        "title": str(info.get("title") or "Crazy Carla video"),
        "published": published_iso(int(info["timestamp"])),
        "description": str(info.get("description") or "")[:300],
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def newest_four() -> tuple[list[dict[str, str]], str]:
    candidates = collect_candidates()
    enriched: list[dict[str, Any]] = []

    # Flat listings often include timestamps already. Only make individual
    # watch-page requests when yt-dlp says a candidate still needs a date.
    for candidate in candidates.values():
        if candidate.get("timestamp"):
            enriched.append(candidate)
            continue

        detailed = enrich_candidate(candidate)
        if detailed:
            enriched.append(detailed)

    if len(enriched) < VIDEO_LIMIT:
        # A second enrichment pass also refreshes metadata for dated entries;
        # useful if a flat listing gave incomplete information.
        refreshed: dict[str, dict[str, Any]] = {x["id"]: x for x in enriched}
        for candidate in candidates.values():
            if candidate["id"] in refreshed:
                continue
            detailed = enrich_candidate(candidate)
            if detailed:
                refreshed[detailed["id"]] = detailed
        enriched = list(refreshed.values())

    if len(enriched) < VIDEO_LIMIT:
        raise RuntimeError(
            f"YouTube returned only {len(enriched)} dated uploads; need {VIDEO_LIMIT}"
        )

    enriched.sort(key=lambda x: int(x["timestamp"]), reverse=True)
    selected = enriched[:VIDEO_LIMIT]

    channel_id = next(
        (
            str(item["channel_id"])
            for item in selected
            if isinstance(item.get("channel_id"), str) and item.get("channel_id")
        ),
        "",
    )

    return [make_video(item) for item in selected], channel_id


def read_existing() -> dict[str, Any] | None:
    if not OUT.exists():
        return None
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def same_video_ids(videos: list[dict[str, str]]) -> bool:
    existing = read_existing()
    if not existing or not isinstance(existing.get("videos"), list):
        return False

    old_ids = [v.get("id") for v in existing["videos"][:VIDEO_LIMIT] if isinstance(v, dict)]
    new_ids = [v["id"] for v in videos]
    return old_ids == new_ids


def main() -> int:
    videos, channel_id = newest_four()

    if same_video_ids(videos):
        print("The same 4 YouTube uploads are still newest; no website update needed.")
        return 0

    payload = {
        "channel_handle": f"@{HANDLE}",
        "channel_id": channel_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "videos": videos,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Updated data/youtube-videos.json with Carla's 4 newest YouTube uploads:")
    for index, video in enumerate(videos, start=1):
        print(f"  {index}. {video['published']}  {video['title']}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Do not overwrite the existing JSON when YouTube is unavailable.
        # A red workflow here is intentional: stale data is a real update
        # failure and should not be silently reported as success.
        print(f"YouTube update failed: {exc}", file=sys.stderr)
        raise
