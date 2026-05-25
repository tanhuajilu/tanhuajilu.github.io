#!/usr/bin/env python3
from pathlib import Path
import re
from collections import defaultdict

ROOT = Path('/home/cailedao/hermes/jiaotongjilu_site_v2')
BOOKS = ['book-02','book-03','book-04']
BASES = [ROOT/'books', ROOT/'public'/'books']

DATE_PAT = re.compile(r'(一|二|三|四|五|六|七|八|九|十|十一|十二)月(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四|十五|十六|十七|十八|十九|二十|二十一|二十二|二十三|二十四|二十五|二十六|二十七|二十八|二十九|三十|三十一)日')
MONTHS = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月']

AUDIO_JS = """<script>(function(){
  const audio = document.getElementById('daily-audio');
  const toggle = document.getElementById('auto-next-play');
  const nextLink = Array.from(document.querySelectorAll('.hero a.btn')).find(a => a.textContent.includes('下一篇'));
  if (!audio || !toggle) return;

  const KEY = 'book01-auto-next-play';
  const RATE_KEY = 'book01-playback-rate';
  const rateSel = document.getElementById('playback-rate');

  const saved = localStorage.getItem(KEY);
  toggle.checked = saved === null ? true : saved === '1';
  toggle.addEventListener('change', () => localStorage.setItem(KEY, toggle.checked ? '1' : '0'));

  const savedRate = localStorage.getItem(RATE_KEY) || '1';
  if (rateSel) {
    if (Array.from(rateSel.options).some(o => o.value === savedRate)) rateSel.value = savedRate;
    audio.playbackRate = parseFloat(rateSel.value || '1');
    rateSel.addEventListener('change', () => {
      audio.playbackRate = parseFloat(rateSel.value || '1');
      localStorage.setItem(RATE_KEY, rateSel.value || '1');
    });
  }

  const params = new URLSearchParams(location.search);
  if (params.get('autoplay') === '1') {
    audio.play().catch(() => {});
  }

  audio.addEventListener('ended', () => {
    if (!toggle.checked || !nextLink) return;
    const u = new URL(nextLink.href, location.href);
    u.searchParams.set('autoplay', '1');
    location.href = u.toString();
  });
})();</script>"""


def parse_book_title(index_html: str) -> str:
    m = re.search(r'<h1>(.*?)</h1>', index_html, flags=re.S)
    return re.sub('<[^>]+>', '', m.group(1)).strip() if m else '未命名'


def split_month_file(html: str):
    art = re.search(r'<article class="article">(.*?)</article>', html, flags=re.S)
    if not art:
        return []
    body = art.group(1)
    chunks = re.split(r'(<h[23]>.*?</h[23]>)', body, flags=re.S)
    sections = []
    cur_title = None
    cur = []
    for c in chunks:
        if not c:
            continue
        if re.match(r'<h[23]>', c):
            txt = re.sub('<[^>]+>', '', c).strip()
            if DATE_PAT.search(txt):
                if cur_title and cur:
                    sections.append((cur_title, ''.join(cur)))
                m = DATE_PAT.search(txt)
                if not m:
                    continue
                cur_title = m.group(0)
                cur = [f'<h2>{cur_title}</h2>']
            else:
                if cur_title:
                    cur.append(c)
        else:
            if cur_title:
                cur.append(c)
    if cur_title and cur:
        sections.append((cur_title, ''.join(cur)))
    return sections


def render_daily(book_title, idx, total, title, article_html, prev_href, next_href, audio_src):
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{book_title}-{title}</title><link rel="stylesheet" href="../../style.css"></head><body><main class="site"><a href="index.html">← 返回本书目录</a> · <a href="../../index.html">书库首页</a><div class="hero"><h1>{title}</h1><p class="meta">{book_title} · 第{idx}/{total}段</p><p><a class="btn" href="{prev_href}">上一篇</a><a class="btn" href="{next_href}">下一篇</a></p><div class="audio-panel"><audio id="daily-audio" controls preload="none" src="{audio_src}"></audio><p class="meta audio-controls-inline"><label><input type="checkbox" id="auto-next-play"> 自动翻页并播放&nbsp;&nbsp;</label><span class="speed-control">播放速度：<select id="playback-rate"><option value="0.8">0.8x</option><option value="0.9">0.9x</option><option value="1" selected>1.0x</option><option value="1.1">1.1x</option><option value="1.25">1.25x</option><option value="1.5">1.5x</option></select></span></p></div></div><article class="article">{article_html}</article></main>{AUDIO_JS}</body></html>'''


def render_month(book_title, month_name, links):
    li = ''.join([f'<li><a href="{href}">{txt}</a></li>' for href, txt in links])
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{book_title}-{month_name}</title><link rel="stylesheet" href="../../style.css"></head><body><main class="site"><a href="index.html">← 返回本书目录</a> · <a href="../../index.html">书库首页</a><div class="hero"><h1>{month_name}</h1><p class="meta">{book_title}</p></div><article class="article"><ol class="section-list">{li}</ol></article></main></body></html>'


def render_book_index(book_title, month_links, total):
    li=''.join([f'<li><a href="{m}.html">{name}</a></li>' for m,name in month_links])
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{book_title}</title><link rel="stylesheet" href="../../style.css"></head><body><main class="site"><a href="../../index.html">← 返回书库首页</a><div class="hero"><h1>{book_title}</h1><p class="meta">共 {total} 段</p></div><div class="layout"><aside class="sidebar"><h3>月份目录</h3><ol class="section-list">{li}</ol></aside><article class="article"><p>请选择月份开始阅读。</p></article></div></main></body></html>'

for base in BASES:
    for b in BOOKS:
        bd = base/b
        idx_html = (bd/'index.html').read_text(encoding='utf-8', errors='ignore')
        book_title = parse_book_title(idx_html)

        all_sections = []
        month_map = defaultdict(list)

        for i in range(1,13):
            sf = bd/f's{i:03d}.html'
            if not sf.exists():
                continue
            sections = split_month_file(sf.read_text(encoding='utf-8', errors='ignore'))
            for title, article in sections:
                all_sections.append((title, article))
                month = title.split('月')[0] + '月'
                month_map[month].append(title)

        total = len(all_sections)
        if total == 0:
            print('WARN no sections', bd)
            continue

        # Write daily pages
        month_links = []
        seq_titles = []
        for n, (title, article) in enumerate(all_sections, 1):
            seq = f's{n:03d}.html'
            prev_href = 'index.html' if n == 1 else f's{n-1:03d}.html'
            next_href = f's{n+1:03d}.html' if n < total else 'index.html'
            audio_src = f'https://audio.tanhuajilu.dpdns.org/{b}/{"s%03d"%n}.mp3'
            (bd/seq).write_text(render_daily(book_title, n, total, title, article, prev_href, next_href, audio_src), encoding='utf-8')
            seq_titles.append((seq, title))

        # month pages m01..m12 with links to corresponding seqs by title matching order
        title_to_seq = {}
        # consume duplicates in order
        for seq,title in seq_titles:
            title_to_seq.setdefault(title, []).append(seq)

        for mi, mname in enumerate(MONTHS, 1):
            links=[]
            for t in month_map.get(mname, []):
                arr = title_to_seq.get(t, [])
                if arr:
                    links.append((arr.pop(0), t))
            if links:
                mfile=f'm{mi:02d}.html'
                (bd/mfile).write_text(render_month(book_title, mname, links), encoding='utf-8')
                month_links.append((f'm{mi:02d}', mname))

        (bd/'index.html').write_text(render_book_index(book_title, month_links, total), encoding='utf-8')
        print('DONE', bd, 'total', total, 'months', len(month_links))
