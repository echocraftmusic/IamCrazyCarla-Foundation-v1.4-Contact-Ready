#!/usr/bin/env python3
"""Write Crazy Carla's four newest YouTube uploads to local JSON.

The public RSS feed is tried first. If YouTube returns 404 (as it currently
does for this channel), the script falls back to Carla's public Videos and
Shorts pages, combines both lists, and sorts them by their real publish dates.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HANDLE = "10aahfro"
CHANNEL_ID = "UC2wmlDZwxw4-RxtsyxSKHpA"
VIDEO_LIMIT = 4
CANDIDATES_PER_TAB = 4

OUT = Path(__file__).resolve().parents[1] / "data" / "youtube-videos.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def get(url: str, attempts: int = 3) -> bytes:
    """Download a public page, retrying temporary network/server failures."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def text_content(value: Any, default: str = "") -> str:
    """Read text from YouTube's several commonly used text shapes."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return default
    if isinstance(value.get("content"), str):
        return value["content"]
    if isinstance(value.get("simpleText"), str):
        return value["simpleText"]
    runs = value.get("runs")
    if isinstance(runs, list):
        return "".join(
            run.get("text", "") for run in runs if isinstance(run, dict)
        )
    return default


def make_video(
    video_id: str, title: str, published: str, description: str
) -> dict[str, str]:
    return {
        "id": video_id,
        "title": title or "Crazy Carla video",
        "published": published,
        "description": (description or "")[:300],
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def parse_feed(data: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(data)
    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    videos: list[dict[str, str]] = []
    for entry in root.findall("a:entry", ns)[:VIDEO_LIMIT]:
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        if not video_id:
            continue
        videos.append(
            make_video(
                video_id,
                entry.findtext(
                    "a:title", default="Crazy Carla video", namespaces=ns
                ),
                entry.findtext("a:published", default="", namespaces=ns),
                entry.findtext(
                    "media:group/media:description",
                    default="",
                    namespaces=ns,
                ),
            )
        )
    return videos


def walk(value: Any):
    """Yield every dictionary nested inside decoded YouTube page data."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def initial_data(page: str) -> dict[str, Any]:
    patterns = (
        r"var ytInitialData\s*=\s*({.*?});</script>",
        r"window\[\"ytInitialData\"\]\s*=\s*({.*?});</script>",
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    raise ValueError("YouTube page did not contain ytInitialData")


def tab_candidates(tab: str) -> list[dict[str, str]]:
    """Collect the newest candidate IDs/titles from one public channel tab."""
    url = f"https://www.youtube.com/@{HANDLE}/{tab}"
    page = get(url).decode("utf-8", errors="replace")
    data = initial_data(page)
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in walk(data):
        video_id = ""
        title = "Crazy Carla video"

        model = item.get("lockupViewModel")
        if (
            isinstance(model, dict)
            and model.get("contentType") == "LOCKUP_CONTENT_TYPE_VIDEO"
        ):
            video_id = model.get("contentId", "")
            title = text_content(
                model.get("metadata", {})
                .get("lockupMetadataViewModel", {})
                .get("title"),
                title,
            )

        short = item.get("shortsLockupViewModel")
        if isinstance(short, dict):
            command = short.get("onTap", {}).get("innertubeCommand", {})
            video_id = command.get("reelWatchEndpoint", {}).get("videoId", "")
            title = text_content(
                short.get("overlayMetadata", {}).get("primaryText"), title
            )

        legacy = item.get("videoRenderer") or item.get("gridVideoRenderer")
        if isinstance(legacy, dict):
            video_id = legacy.get("videoId", "")
            title = text_content(legacy.get("title"), title)

        reel = item.get("reelItemRenderer")
        if isinstance(reel, dict):
            video_id = reel.get("videoId", "")
            title = text_content(reel.get("headline"), title)

        if video_id and video_id not in seen:
            seen.add(video_id)
            found.append({"id": video_id, "title": title})
            if len(found) >= CANDIDATES_PER_TAB:
                break
    return found


def video_details(candidate: dict[str, str]) -> dict[str, str]:
    """Get an exact publish date and description for a video or Short."""
    video_id = candidate["id"]
    page = get(f"https://www.youtube.com/watch?v={video_id}").decode(
        "utf-8", errors="replace"
    )
    date_match = re.search(
        r'<meta\s+itemprop="datePublished"\s+content="([^"]+)"', page
    ) or re.search(r'"publishDate":"([^"]+)"', page)
    if not date_match:
        raise ValueError(f"No publish date found for video {video_id}")

    title_match = re.search(
        r'<meta\s+name="title"\s+content="([^"]*)"', page
    )
    description_match = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"', page
    )
    title = (
        html.unescape(title_match.group(1))
        if title_match
        else candidate["title"]
    )
    description = (
        html.unescape(description_match.group(1))[:300]
        if description_match
        else ""
    )
    return make_video(video_id, title, date_match.group(1), description)


def scrape_channel() -> list[dict[str, str]]:
    """Combine regular videos and Shorts, then return the true newest four."""
    candidates: dict[str, dict[str, str]] = {}
    tab_errors: list[str] = []
    for tab in ("videos", "shorts", "streams"):
        try:
            for candidate in tab_candidates(tab):
                candidates.setdefault(candidate["id"], candidate)
        except Exception as exc:
            tab_errors.append(f"{tab}: {exc}")

    if not candidates:
        raise RuntimeError(
            "Could not read Carla's Videos, Shorts, or Live pages: "
            + "; ".join(tab_errors)
        )

    videos: list[dict[str, str]] = []
    detail_errors: list[str] = []
    for candidate in candidates.values():
        try:
            videos.append(video_details(candidate))
        except Exception as exc:
            detail_errors.append(f"{candidate['id']}: {exc}")

    if len(videos) < VIDEO_LIMIT:
        raise RuntimeError(
            f"Only {len(videos)} usable uploads were found. "
            + "; ".join(detail_errors)
        )

    videos.sort(key=lambda video: parse_date(video["published"]), reverse=True)
    return videos[:VIDEO_LIMIT]


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def unchanged(videos: list[dict[str, str]]) -> bool:
    if not OUT.exists():
        return False
    try:
        current = json.loads(OUT.read_text(encoding="utf-8"))
        return current.get("videos") == videos
    except (OSError, json.JSONDecodeError):
        return False


def main() -> int:
    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={CHANNEL_ID}"
    )
    try:
        videos = parse_feed(get(feed_url))
        source = "YouTube RSS feed"
        if len(videos) < VIDEO_LIMIT:
            raise ValueError(f"RSS returned only {len(videos)} videos")
    except Exception as feed_error:
        print(f"RSS unavailable ({feed_error}); using public channel pages.")
        videos = scrape_channel()
        source = "public Videos and Shorts pages"

    if unchanged(videos):
        print(f"The same {VIDEO_LIMIT} videos are still newest; no update needed.")
        return 0

    payload = {
        "channel_handle": f"@{HANDLE}",
        "channel_id": CHANNEL_ID,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "videos": videos,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Updated {len(videos)} videos from {source}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"YouTube update failed: {exc}", file=sys.stderr)
        raise
