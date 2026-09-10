#!/usr/bin/env python3
"""Write Crazy Carla's four newest YouTube uploads to local JSON.

Strategy:
1. Discover Carla's current YouTube channel ID from her public handle page.
2. Try YouTube's public RSS feed first.
3. If RSS is unavailable, read Carla's Videos / Shorts / Live tabs.
4. Resolve exact publish dates from YouTube's player/page metadata.
5. If YouTube temporarily changes or blocks its public markup, KEEP the
   existing four videos instead of failing the GitHub Action.
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

# Kept only as a fallback. The script now discovers the live channel ID from
# @10aahfro before attempting RSS, so a stale ID will not break the workflow.
FALLBACK_CHANNEL_ID = "UC2wmlDZwxw4-RxtsyxSKHpA"

VIDEO_LIMIT = 4
CANDIDATES_PER_TAB = 10

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
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
        ) as exc:
            last_error = exc

            # A 404 is not temporary, so do not waste time retrying it.
            if isinstance(exc, urllib.error.HTTPError) and exc.code == 404:
                break

            if attempt + 1 < attempts:
                time.sleep(2**attempt)

    assert last_error is not None
    raise last_error


def text_content(value: Any, default: str = "") -> str:
    """Read text from YouTube's commonly used text shapes."""
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
    video_id: str,
    title: str,
    published: str,
    description: str,
) -> dict[str, str]:
    return {
        "id": video_id,
        "title": title or "Crazy Carla video",
        "published": published,
        "description": (description or "")[:300],
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def parse_date(value: str) -> datetime:
    """Parse YouTube ISO dates such as 2026-09-09 or ...Z timestamps."""
    value = value.strip()

    # A date-only value is valid ISO but naive; make it UTC for sorting.
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed


def parse_feed(data: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(data)

    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }

    videos: list[dict[str, str]] = []

    for entry in root.findall("a:entry", ns):
        video_id = entry.findtext("yt:videoId", default="", namespaces=ns)
        if not video_id:
            continue

        published = entry.findtext(
            "a:published",
            default="",
            namespaces=ns,
        )
        if not published:
            continue

        videos.append(
            make_video(
                video_id,
                entry.findtext(
                    "a:title",
                    default="Crazy Carla video",
                    namespaces=ns,
                ),
                published,
                entry.findtext(
                    "media:group/media:description",
                    default="",
                    namespaces=ns,
                ),
            )
        )

    videos.sort(key=lambda item: parse_date(item["published"]), reverse=True)
    return videos[:VIDEO_LIMIT]


def walk(value: Any):
    """Yield every dictionary nested inside decoded YouTube page data."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def extract_json_object_after_marker(page: str, marker: str) -> dict[str, Any]:
    """Decode a JSON object assigned after a JavaScript marker.

    This avoids fragile regex such as {.*?}; which can break when YouTube adds
    nested objects, braces inside strings, or changes whitespace.
    """
    start = page.find(marker)
    if start < 0:
        raise ValueError(f"Marker not found: {marker}")

    brace = page.find("{", start + len(marker))
    if brace < 0:
        raise ValueError(f"No JSON object after marker: {marker}")

    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(page[brace:])

    if not isinstance(value, dict):
        raise ValueError(f"Expected object after marker: {marker}")

    return value


def initial_data(page: str) -> dict[str, Any]:
    """Read ytInitialData using several assignment forms YouTube has used."""
    markers = (
        "var ytInitialData =",
        "var ytInitialData=",
        'window["ytInitialData"] =',
        'window["ytInitialData"]=',
        "ytInitialData =",
        "ytInitialData=",
    )

    for marker in markers:
        try:
            return extract_json_object_after_marker(page, marker)
        except (ValueError, json.JSONDecodeError):
            pass

    raise ValueError("YouTube page did not contain readable ytInitialData")


def player_response(page: str) -> dict[str, Any]:
    """Read ytInitialPlayerResponse from a watch page if present."""
    markers = (
        "var ytInitialPlayerResponse =",
        "var ytInitialPlayerResponse=",
        "ytInitialPlayerResponse =",
        "ytInitialPlayerResponse=",
    )

    for marker in markers:
        try:
            return extract_json_object_after_marker(page, marker)
        except (ValueError, json.JSONDecodeError):
            pass

    # YouTube also embeds the player response in ytplayer config-like JSON.
    # This regex only finds the key; json.JSONDecoder handles the object itself.
    key_match = re.search(r'"ytInitialPlayerResponse"\s*:\s*', page)
    if key_match:
        brace = page.find("{", key_match.end())
        if brace >= 0:
            try:
                value, _ = json.JSONDecoder().raw_decode(page[brace:])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass

    return {}


def discover_channel_id() -> str:
    """Discover the current channel ID from Carla's public handle page."""
    page = get(f"https://www.youtube.com/@{HANDLE}").decode(
        "utf-8",
        errors="replace",
    )

    patterns = (
        r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]+)"',
        r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]+)"',
        r'youtube\.com/channel/(UC[A-Za-z0-9_-]+)',
    )

    for pattern in patterns:
        match = re.search(pattern, page)
        if match:
            return match.group(1)

    print(
        "Warning: could not discover channel ID from handle page; "
        "using fallback channel ID.",
        file=sys.stderr,
    )
    return FALLBACK_CHANNEL_ID


def tab_candidates(tab: str) -> list[dict[str, str]]:
    """Collect candidate IDs/titles from one public channel tab."""
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
                short.get("overlayMetadata", {}).get("primaryText"),
                title,
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


def first_string(value: Any, *paths: tuple[str, ...]) -> str:
    """Return the first non-empty string found at one of several dict paths."""
    for path in paths:
        current = value
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)

        if isinstance(current, str) and current.strip():
            return current.strip()

    return ""


def video_details(candidate: dict[str, str]) -> dict[str, str]:
    """Get an exact publish date, title, and description for a video/Short."""
    video_id = candidate["id"]

    page = get(f"https://www.youtube.com/watch?v={video_id}").decode(
        "utf-8",
        errors="replace",
    )

    player = player_response(page)

    microformat = (
        player.get("microformat", {})
        .get("playerMicroformatRenderer", {})
        if isinstance(player, dict)
        else {}
    )
    details = player.get("videoDetails", {}) if isinstance(player, dict) else {}

    published = first_string(
        microformat,
        ("publishDate",),
        ("uploadDate",),
    )

    # HTML metadata fallback.
    if not published:
        patterns = (
            r'<meta[^>]+itemprop=["\']datePublished["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+itemprop=["\']uploadDate["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+itemprop=["\']datePublished["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+itemprop=["\']uploadDate["\']',
            r'"publishDate"\s*:\s*"([^"]+)"',
            r'"uploadDate"\s*:\s*"([^"]+)"',
        )

        for pattern in patterns:
            match = re.search(pattern, page, re.IGNORECASE)
            if match:
                published = html.unescape(match.group(1))
                break

    if not published:
        raise ValueError(f"No publish date found for video {video_id}")

    # Prefer ytInitialPlayerResponse because it is less sensitive to HTML
    # attribute ordering than meta-tag regexes.
    title = first_string(details, ("title",)) or candidate["title"]
    description = first_string(details, ("shortDescription",))

    if not title:
        title_match = re.search(
            r'<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']*)',
            page,
            re.IGNORECASE,
        )
        if title_match:
            title = html.unescape(title_match.group(1))

    if not description:
        description_match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',
            page,
            re.IGNORECASE,
        )
        if description_match:
            description = html.unescape(description_match.group(1))

    return make_video(
        video_id,
        html.unescape(title),
        published,
        html.unescape(description),
    )


def scrape_channel() -> list[dict[str, str]]:
    """Combine regular videos, Shorts, and Live, returning the newest four."""
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


def read_existing() -> dict[str, Any] | None:
    if not OUT.exists():
        return None

    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def existing_has_safe_feed() -> bool:
    current = read_existing()
    return bool(
        current
        and isinstance(current.get("videos"), list)
        and len(current["videos"]) >= VIDEO_LIMIT
    )


def unchanged(videos: list[dict[str, str]]) -> bool:
    current = read_existing()
    return bool(current and current.get("videos") == videos)


def fetch_newest_videos() -> tuple[list[dict[str, str]], str, str]:
    """Return videos, source description, and the channel ID used."""
    channel_id = discover_channel_id()

    feed_ids = [channel_id]
    if FALLBACK_CHANNEL_ID not in feed_ids:
        feed_ids.append(FALLBACK_CHANNEL_ID)

    feed_errors: list[str] = []

    for candidate_id in feed_ids:
        feed_url = (
            "https://www.youtube.com/feeds/videos.xml"
            f"?channel_id={candidate_id}"
        )

        try:
            videos = parse_feed(get(feed_url))
            if len(videos) < VIDEO_LIMIT:
                raise ValueError(f"RSS returned only {len(videos)} videos")

            return videos, "YouTube RSS feed", candidate_id
        except Exception as exc:
            feed_errors.append(f"{candidate_id}: {exc}")

    print(
        "RSS unavailable (" + "; ".join(feed_errors) + "); "
        "using public channel pages."
    )

    videos = scrape_channel()
    return videos, "public Videos / Shorts / Live pages", channel_id


def main() -> int:
    try:
        videos, source, channel_id = fetch_newest_videos()
    except Exception as exc:
        # This is intentionally a SOFT failure when a valid feed already
        # exists. YouTube changes its public markup periodically; a temporary
        # scrape problem should not erase Carla's current videos or make the
        # scheduled GitHub Action look like the website is broken.
        if existing_has_safe_feed():
            print(
                "WARNING: YouTube could not be refreshed right now: "
                f"{exc}",
                file=sys.stderr,
            )
            print(
                f"Keeping the existing {VIDEO_LIMIT} videos. "
                "The workflow will try again on the next scheduled run."
            )
            return 0

        # If there is no valid existing JSON to protect, fail loudly because
        # the site would otherwise have no safe video data.
        raise

    if unchanged(videos):
        print(
            f"The same {VIDEO_LIMIT} videos are still newest; "
            "no update needed."
        )
        return 0

    payload = {
        "channel_handle": f"@{HANDLE}",
        "channel_id": channel_id,
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
