#!/usr/bin/env python3
"""Resolve a public YouTube handle, read its public RSS feed, and write local JSON."""
from __future__ import annotations
import json,re,sys,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
HANDLE='10aahfro'
OUT=Path(__file__).resolve().parents[1]/'data'/'youtube-videos.json'
UA={'User-Agent':'Mozilla/5.0 (compatible; IamCrazyCarlaSite/1.0)'}
def get(url:str)->bytes:
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as r:return r.read()
def resolve_channel_id()->str:
    html=get(f'https://www.youtube.com/@{HANDLE}').decode('utf-8','ignore')
    patterns=[r'"externalId":"(UC[^"]+)"',r'"channelId":"(UC[^"]+)"',r'channel_id=(UC[\w-]+)']
    for p in patterns:
        m=re.search(p,html)
        if m:return m.group(1)
    raise RuntimeError('Could not resolve channel ID from public handle page.')
def main()->int:
    channel_id=resolve_channel_id()
    feed=get(f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}')
    root=ET.fromstring(feed)
    ns={'a':'http://www.w3.org/2005/Atom','yt':'http://www.youtube.com/xml/schemas/2015','media':'http://search.yahoo.com/mrss/'}
    videos=[]
    for entry in root.findall('a:entry',ns)[:6]:
        vid=entry.findtext('yt:videoId',default='',namespaces=ns)
        title=entry.findtext('a:title',default='Crazy Carla video',namespaces=ns)
        published=entry.findtext('a:published',default='',namespaces=ns)
        desc=entry.findtext('media:group/media:description',default='',namespaces=ns)
        videos.append({'id':vid,'title':title,'published':published,'description':desc[:300],'url':f'https://www.youtube.com/watch?v={vid}','thumbnail':f'https://i.ytimg.com/vi/{vid}/hqdefault.jpg'})
    OUT.write_text(json.dumps({'channel_handle':'@'+HANDLE,'channel_id':channel_id,'updated_at':datetime.now(timezone.utc).isoformat(),'videos':videos},indent=2),encoding='utf-8')
    print(f'Updated {len(videos)} videos from {channel_id}')
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(f'YouTube update failed: {exc}',file=sys.stderr);raise
