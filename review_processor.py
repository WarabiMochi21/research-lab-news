"""Process editorial drafts; only publish immutable approved revisions."""
from display_text import display_text
import argparse
import json
import os
import sys
import base64
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
from urllib.error import HTTPError

BASE = 'https://research-lab-review.jaydentimothyliu.workers.dev'

def request_json(url, payload=None, headers=None):
    req=Request(url, data=None if payload is None else json.dumps(payload).encode(), headers={'Content-Type':'application/json', 'User-Agent':'ResearchLabEditorial/1.0', 'Accept':'application/json', **(headers or {})})
    try:
        with urlopen(req, timeout=75) as r:
            raw=r.read(1000000)
    except HTTPError as error:
        print('Connection diagnostic:', 'HTTP',error.code, 'server=',error.headers.get('Server','unknown'), 'content-type=',error.headers.get('Content-Type','unknown'), 'challenge=',error.headers.get('cf-mitigated','none'))
        raise
    return json.loads(raw)

def bridge(route, payload=None):
    secret=os.environ.get('REVIEW_API_SECRET','')
    if not secret: raise RuntimeError('Missing REVIEW_API_SECRET')
    return request_json(BASE+'/api/'+route,payload,{'Authorization':'Bearer '+secret})

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def evidence(entry):
    # Only approved publisher domains may be fetched. Other links remain editor-supplied excerpts.
    hosts=('cnbc.com','abcnews.go.com','abcnews.com','bbc.com','bbc.co.uk','bea.gov','nytimes.com','bloomberg.com','theguardian.com','federalreserve.gov','sec.gov','finance.yahoo.com')
    url=entry.get('url','')
    p=urlsplit(url)
    host=(p.hostname or '').lower()
    result={'url':url,'editor_notes':entry.get('notes',''),'access':'editor-supplied notes only'}
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not any(host==h or host.endswith('.'+h) for h in hosts): return result
    try:
        import trafilatura
        req=Request(url,headers={'User-Agent':'ResearchLabResearch/1.0'})
        with build_opener(NoRedirect).open(req,timeout=20) as r:
            if 'html' not in r.headers.get('Content-Type',''): return result
            raw=r.read(2000001)
        if len(raw)>2000000: return result
        text=trafilatura.extract(raw,include_comments=False,include_tables=True)
        if text and len(text)>300:
            result.update(access='extracted page text, truncated at 14000 characters',text=text[:14000])
    except Exception:
        pass
    return result

def research(row):
    from editorial import build_brief
    entries = json.loads(row['inputs'])
    sources = [evidence(x) for x in entries]
    text, copy = build_brief(sources, request_json)
    copy = {key: display_text(value) for key, value in copy.items()}
    # Freeze the exact poster bytes before review; image failure keeps the draft queued.
    from news_card import render_card
    from PIL import Image
    from datetime import datetime, timezone
    first=json.loads(row['inputs'])[0]
    item={'title':copy['headline'],'description':copy['summary'], 'publisher':urlsplit(first['url']).hostname or 'Editorial sources', 'published':first.get('published') or datetime.now(timezone.utc).isoformat()}
    with tempfile.TemporaryDirectory() as folder:
        picture=render_card(item,copy,Path(folder)/'poster.png')
        target=Path(folder)/'poster.jpg'
        Image.open(picture).convert('RGB').save(target,'JPEG',quality=88,optimize=True)
        encoded=base64.b64encode(target.read_bytes()).decode()
    if len(encoded)>900000: raise RuntimeError('Poster exceeds storage limit; draft remains queued')
    bridge('ready',{'id':row['id'],'revision':row['revision'],'analysis':text,'image_b64':encoded})

def publish(row):
    import bot
    url=os.environ.get('DISCORD_WEBHOOK_URL','')
    bot.verify_destination(url,os.environ.get('DISCORD_CHANNEL_ID',''))
    # Claim is persisted before Discord POST. Ambiguous delivery is never auto-retried.
    claimed=bridge('claim',{'id':row['id'],'revision':row['revision']})
    payload={'username':'Research Lab','allowed_mentions':{'parse':[]},'embeds':[{'title':claimed['title'][:160],'description':display_text(claimed['analysis']),'footer':{'text':'Human-approved research brief'}}]}
    image=claimed.get('image_b64')
    if image:
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'poster.jpg'
            target.write_bytes(base64.b64decode(image,validate=True))
            payload['embeds'][0]['image']={'url':'attachment://poster.jpg'}
            receipt=bot.deliver(url,payload,target)
    else:
        receipt=bot.deliver(url,payload)
    bridge('complete',{'id':claimed['id'],'revision':claimed['revision'],'message_id':receipt})

def collect_news():
    import bot
    import hashlib
    config=json.loads((bot.ROOT/'config.json').read_text(encoding='utf-8'))
    items=[]
    ok=0
    for feed in config['feeds']:
        try:
            items.extend(bot.parse_feed(bot.http(feed['url']),feed,config))
            ok+=1
        except Exception:
            print('Feed unavailable:',feed['name'])
    if not ok: raise RuntimeError('All feeds failed')
    config=dict(config,max_posts_per_run=100,max_posts_per_day=100)
    selected=bot.select_items(items,{'items':{}},config)
    from editorial import group_topics
    groups=group_topics(selected, request_json)
    added=0
    for group in groups:
        # The oldest URL is a stable anchor while newer follow-up coverage is added.
        item=group[0]
        anchor=min(group, key=lambda x:(x['published'],x['url']))
        key='rss-'+hashlib.sha256(anchor['url'].encode()).hexdigest()
        sources=[]
        hosts=set()
        for article in group:
            host=urlsplit(article['url']).hostname
            if host in hosts: continue
            hosts.add(host)
            sources.append({'url':article['url'], 'notes':article['title']+'\n'+article.get('description','')+'\nRSS excerpt only.', 'publisher':article['publisher'], 'published':article['published']})
            if len(sources)>=4: break
        result=bridge('drafts',{'id_key':key,'title':item['title'],'sources':sources})
        if result.get('created'): added+=1
        if result.get('daily_cap') or added>=3: break
    print('Automatic news drafts added:',added)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--collect',action='store_true')
    args=parser.parse_args()
    collection_failed=0
    if args.collect:
        try: collect_news()
        except Exception as error:
            collection_failed=1
            print('Collection failed; existing approved drafts will still be processed:',type(error).__name__)
    rows=bridge('queue').get('results',[])
    rows.sort(key=lambda row: row['status'] != 'approved')
    print('Publication enabled:', args.publish, 'Approved drafts:', sum(r['status']=='approved' for r in rows))
    processed=published=failed=0
    for row in rows:
        try:
            if row['status']=='queued' and processed<3:
                processed+=1
                research(row)
                print('Draft ready for human review:',row['id'])
            elif row['status']=='approved' and args.publish and published<3:
                published+=1
                publish(row)
                print('Approved draft published:',row['id'])
        except HTTPError as error:
            failed+=1
            print('Draft failed:',row['id'],'HTTP',error.code)
        except Exception as error:
            failed+=1
            print('Draft failed:',row['id'],type(error).__name__)
    print(json.dumps({'attempted_research':processed,'attempted_publication':published,'failed':failed}))
    if failed or collection_failed: sys.exit(1)

if __name__=='__main__': main()

