#!/usr/bin/env python3
"""Read Crazy Carla's public YouTube RSS feed and write local JSON."""

from __future__ import annotations

import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path


HANDLE = "10aahfro"
CHANNEL_ID = "UC2wmIDZwxw4-RxtsyxSKHpA"

OUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "youtube-videos.json"
)

UA = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; IAmCrazyCarlaSite/1.0)"
    )
}


def get(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers=UA,
    )

    with urllib.request.urlopen(
        req,
        timeout=30,
    ) as response:
        return response.read()


def main() -> int:
    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={CHANNEL_ID}"
    )

    feed = get(feed_url)
    root = ET.fromstring(feed)

    ns = {
        "a": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }

    videos = []

    for entry in root.findall("a:entry", ns)[:6]:
        vid = entry.findtext(
            "yt:videoId",
            default="",
            namespaces=ns,
        )

        title = entry.findtext(
            "a:title",
            default="Crazy Carla video",
            namespaces=ns,
        )

        published = entry.findtext(
            "a:published",
            default="",
            namespaces=ns,
        )

        description = entry.findtext(
            "media:group/media:description",
            default="",
            namespaces=ns,
        )

        videos.append(
            {
                "id": vid,
                "title": title,
                "published": published,
                "description": description[:300],
                "url": f"https://www.youtube.com/watch?v={vid}",
                "thumbnail": (
                    f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
                ),
            }
        )

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT.write_text(
        json.dumps(
            {
                "channel_handle": f"@{HANDLE}",
                "channel_id": CHANNEL_ID,
                "updated_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "videos": videos,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Updated {len(videos)} videos "
        f"from {CHANNEL_ID}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())

    except Exception as exc:
        print(
            f"YouTube update failed: {exc}",
            file=sys.stderr,
        )
        raise
