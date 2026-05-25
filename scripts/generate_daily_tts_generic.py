#!/usr/bin/env python3
import csv, html, re, subprocess, sys, time
from pathlib import Path

ROOT = Path('/home/cailedao/hermes/jiaotongjilu_site_v2')
VOICE='zh-CN-YunjianNeural'
EDGE_TTS=Path('/home/cailedao/.hermes/hermes-agent/venv/bin/edge-tts')

book = sys.argv[1] if len(sys.argv)>1 else 'book-01'
BOOK_DIR = ROOT/'books'/book
OUT_DIR = ROOT/'audio'/f'{book}-daily'
LOG_CSV = OUT_DIR/'generation_log.csv'

OUT_DIR.mkdir(parents=True, exist_ok=True)

def clean_text(html_content: str) -> str:
    m = re.search(r'<article[^>]*class="article"[^>]*>(.*?)</article>', html_content, flags=re.S | re.I)
    article = m.group(1) if m else html_content
    ps = re.findall(r'<p[^>]*>(.*?)</p>', article, flags=re.S | re.I)
    if not ps:
        ps = [article]
    chunks=[]
    for p in ps:
        p=re.sub(r'<[^>]+>','',p)
        p=html.unescape(p).replace('**','')
        p=re.sub(r'\s+',' ',p).strip()
        if p: chunks.append(p)
    return '\n'.join(chunks)

def synthesize(text: str, out_mp3: Path):
    tmp=out_mp3.with_suffix('.txt.tmp')
    tmp.write_text(text,encoding='utf-8')
    cmd=[str(EDGE_TTS),'--voice',VOICE,'--file',str(tmp),'--write-media',str(out_mp3)]
    last=''
    for attempt in range(1,4):
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
            last=(p.stderr or p.stdout or '')
            if p.returncode==0 and out_mp3.exists() and out_mp3.stat().st_size>1024:
                tmp.unlink(missing_ok=True)
                return True, f'ok(attempt={attempt})'
        except subprocess.TimeoutExpired:
            last='timeout'
        time.sleep(1.5*attempt)
    tmp.unlink(missing_ok=True)
    return False, last.strip().replace('\n',' ')[:300] or 'unknown_error'

def main():
    pages=sorted(BOOK_DIR.glob('s[0-9][0-9][0-9].html'))
    total=len(pages)
    if total==0:
        print('no pages'); return 2
    new_file=not LOG_CSV.exists()
    existing=done=fail=0
    with LOG_CSV.open('a',newline='',encoding='utf-8') as f:
        w=csv.writer(f)
        if new_file: w.writerow(['seq','status','note'])
        for i,page in enumerate(pages,1):
            seq=page.stem
            out=OUT_DIR/f'{seq}.mp3'
            if out.exists() and out.stat().st_size>1024:
                existing+=1
            else:
                text=clean_text(page.read_text(encoding='utf-8',errors='ignore'))
                if not text:
                    fail+=1; w.writerow([seq,'fail','empty_text'])
                else:
                    ok,note=synthesize(text,out)
                    if ok:
                        done+=1; w.writerow([seq,'ok',note])
                    else:
                        fail+=1; w.writerow([seq,'fail',note])
            if i%10==0 or i==total:
                print(f'[{i}/{total}] skip-existing={existing} done={done} fail={fail}', flush=True)
    print(f'FINISHED book={book} total={total} skip-existing={existing} done={done} fail={fail}')
    return 0 if fail==0 else 1

if __name__=='__main__':
    raise SystemExit(main())
