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

BOOK_MAP = {
    '太':'马太福音','可':'马可福音','路':'路加福音','约':'约翰福音','徒':'使徒行传','罗':'罗马书',
    '林前':'哥林多前书','林后':'哥林多后书','加':'加拉太书','弗':'以弗所书','腓':'腓立比书','西':'歌罗西书',
    '帖前':'帖撒罗尼迦前书','帖后':'帖撒罗尼迦后书','提前':'提摩太前书','提后':'提摩太后书','多':'提多书','门':'腓利门书',
    '来':'希伯来书','雅':'雅各书','彼前':'彼得前书','彼后':'彼得后书','约一':'约翰一书','约二':'约翰二书','约三':'约翰三书',
    '犹':'犹大书','启':'启示录'
}
BOOK_KEYS = sorted(BOOK_MAP.keys(), key=len, reverse=True)


def normalize_tts_text(text: str) -> str:
    text = text.replace('**', '')
    text = re.sub(r'\[(.*?)\]\([^\)]*\)', r'\1', text)  # 清掉 markdown 链接，保留可见文本

    def repl(m):
        book = m.group(1).replace(' ', '')
        chap = m.group(2)
        verse = m.group(3)
        full = next((BOOK_MAP[k] for k in BOOK_KEYS if book == k), book)
        return f'{full}{chap}章{verse}节'

    text = re.sub(r'([\u4e00-\u9fff]{1,8})\s*(\d+)\s*[:：]\s*(\d+)', repl, text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def clean_text(html_content: str) -> str:
    chunks = []

    # 朗读页面主标题（日期/章节标题）
    h1 = re.search(r'<div[^>]*class="hero"[^>]*>.*?<h1>(.*?)</h1>', html_content, flags=re.S | re.I)
    if h1:
        t = normalize_tts_text(html.unescape(re.sub(r'<[^>]+>', '', h1.group(1))))
        if t:
            chunks.append(t)

    m = re.search(r'<article[^>]*class="article"[^>]*>(.*?)</article>', html_content, flags=re.S | re.I)
    article = m.group(1) if m else html_content

    # 按正文顺序提取小标题与段落，确保“章节标题也读一下”
    blocks = re.findall(r'<(h2|h3|p)[^>]*>(.*?)</\1>', article, flags=re.S | re.I)
    if not blocks:
        blocks = [('p', article)]

    for tag, raw in blocks:
        text = re.sub(r'<[^>]+>', '', raw)
        text = normalize_tts_text(html.unescape(text))
        if text:
            chunks.append(text)

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
