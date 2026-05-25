#!/usr/bin/env python3
from pathlib import Path
import re, requests, json

root=Path('/home/cailedao/hermes/jiaotongjilu_site_v2')
src_dir=root/'audio'/'book-01-daily'
state_file=src_dir/'uploaded_state.json'

raw=Path('/home/cailedao/hermes/cftoken.txt').read_text()
m=re.search(r'[A-Za-z0-9_-]{30,}', raw)
if not m:
    raise SystemExit('token_not_found')
token=m.group(0)
account='8dfe365486eaab9cd7aa633d09d5813f'
bucket='audio'
base=f'https://api.cloudflare.com/client/v4/accounts/{account}/r2/buckets/{bucket}/objects'
headers={'Authorization':f'Bearer {token}','Content-Type':'audio/mpeg'}

state={}
if state_file.exists():
    try:
        state=json.loads(state_file.read_text(encoding='utf-8'))
    except Exception:
        state={}

mp3s=sorted(src_dir.glob('s*.mp3'))
ready=[p for p in mp3s if p.stat().st_size>1024]
up=skip=fail=0
for i,p in enumerate(ready,1):
    key=f'book-01/{p.name}'
    size=p.stat().st_size
    if state.get(key)==size:
        skip+=1
    else:
        r=requests.put(f'{base}/{key}',headers=headers,data=p.read_bytes(),timeout=120)
        if r.status_code==200:
            up+=1
            state[key]=size
        else:
            fail+=1
            print('FAIL',p.name,r.status_code)
    if i%20==0 or i==len(ready):
        print(f'[{i}/{len(ready)}] up={up} skip={skip} fail={fail}', flush=True)

state_file.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print({'ready_local':len(ready),'uploaded_now':up,'skipped_state':skip,'failed':fail,'uploaded_total_state':len(state)})
