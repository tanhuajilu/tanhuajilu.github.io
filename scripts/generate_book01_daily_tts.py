#!/usr/bin/env python3
import csv
import html
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/cailedao/hermes/jiaotongjilu_site_v2')
BOOK_DIR = ROOT / 'books' / 'book-01'
OUT_DIR = ROOT / 'audio' / 'book-01-daily'
LOG_CSV = OUT_DIR / 'generation_log.csv'
VOICE = 'zh-CN-YunjianNeural'
EDGE_TTS = Path('/home/cailedao/.hermes/hermes-agent/venv/bin/edge-tts')

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
    text = re.sub(r'\[(.*?)\]\([^\)]*\)', r'\1', text)

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

    h1 = re.search(r'<div[^>]*class="hero"[^>]*>.*?<h1>(.*?)</h1>', html_content, flags=re.S | re.I)
    if h1:
        t = normalize_tts_text(html.unescape(re.sub(r'<[^>]+>', '', h1.group(1))))
        if t:
            chunks.append(t)

    m = re.search(r'<article[^>]*class="article"[^>]*>(.*?)</article>', html_content, flags=re.S | re.I)
    article = m.group(1) if m else html_content
    blocks = re.findall(r'<(h2|h3|p)[^>]*>(.*?)</\1>', article, flags=re.S | re.I)
    if not blocks:
        blocks = [('p', article)]

    for _, raw in blocks:
        text = re.sub(r'<[^>]+>', '', raw)
        text = normalize_tts_text(html.unescape(text))
        if text:
            chunks.append(text)

    return '\n'.join(chunks)


def synthesize(text: str, out_mp3: Path) -> tuple[bool, str]:
    tmp_txt = out_mp3.with_suffix('.txt.tmp')
    tmp_txt.write_text(text, encoding='utf-8')
    cmd = [str(EDGE_TTS), '--voice', VOICE, '--file', str(tmp_txt), '--write-media', str(out_mp3)]

    last = None
    for attempt in range(1, 4):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            last = p
            if p.returncode == 0 and out_mp3.exists() and out_mp3.stat().st_size > 1024:
                tmp_txt.unlink(missing_ok=True)
                return True, f'ok(attempt={attempt})'
        except subprocess.TimeoutExpired:
            last = None
        time.sleep(1.5 * attempt)
    err = ((last.stderr if last else '') or (last.stdout if last else '') or '').strip().replace('\n', ' ')[:400]
    tmp_txt.unlink(missing_ok=True)
    return False, err or 'unknown_error'


def main():
    if not EDGE_TTS.exists():
        print(f'ERROR: edge-tts not found at {EDGE_TTS}', file=sys.stderr)
        return 2

    pages = sorted(BOOK_DIR.glob('s[0-9][0-9][0-9].html'))
    total = len(pages)
    if total == 0:
        print('ERROR: no daily pages found', file=sys.stderr)
        return 2

    existing = 0
    done = 0
    fail = 0

    new_file = not LOG_CSV.exists()
    with LOG_CSV.open('a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(['seq', 'src', 'out_mp3', 'status', 'note'])

        for i, page in enumerate(pages, 1):
            seq = page.stem
            out_mp3 = OUT_DIR / f'{seq}.mp3'
            if out_mp3.exists() and out_mp3.stat().st_size > 1024:
                existing += 1
                if i % 25 == 0 or i == total:
                    print(f'[{i}/{total}] skip-existing={existing} done={done} fail={fail}', flush=True)
                continue

            html_content = page.read_text(encoding='utf-8', errors='ignore')
            text = clean_text(html_content)
            if not text:
                fail += 1
                w.writerow([seq, str(page), str(out_mp3), 'fail', 'empty_text'])
                print(f'[{i}/{total}] FAIL {seq}: empty_text', flush=True)
                continue

            ok, note = synthesize(text, out_mp3)
            if ok:
                done += 1
                w.writerow([seq, str(page), str(out_mp3), 'ok', note])
            else:
                fail += 1
                w.writerow([seq, str(page), str(out_mp3), 'fail', note])
                print(f'[{i}/{total}] FAIL {seq}: {note}', flush=True)

            if i % 10 == 0 or i == total:
                print(f'[{i}/{total}] skip-existing={existing} done={done} fail={fail}', flush=True)

    print(f'FINISHED total={total} skip-existing={existing} done={done} fail={fail}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
