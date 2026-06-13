#!/usr/bin/env python3
"""
ARIA New Releases — HTML Generator
===================================
Run this script whenever you add new PDFs to the ARIA folder.

Usage:
    python3 generate_releases.py

What it does:
1. Scans all PDFs in PDF_DIR and any year subfolders (e.g. 2025/, 2026/)
2. Parses each PDF using column-based extraction to get Title, Artist, Type, Label, Date
3. Deduplicates releases across files
4. Writes index.html in this folder — deploy to GitHub Pages or open locally

Dependencies:
    pip install pdfplumber
"""

import os
import re
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    os.system(f"{sys.executable} -m pip install pdfplumber --break-system-packages -q")
    import pdfplumber

# ── Config ────────────────────────────────────────────────────────────────────
REPO_DIR = Path(__file__).parent
PDF_DIR  = Path.home() / "IHGT" / "Research" / "ARIA"   # folder containing PDFs

SUPABASE_URL = "https://dqxecdrzdzkitdkecsca.supabase.co"
SUPABASE_KEY = "sb_publishable_7AjtdPGsMa3wHcB7DWC_-A_bhNNOuEh"

EXCLUDED_ARTISTS = {'The Wiggles', 'Dorothy The Dinosaur', 'Los Wiggles'}
# ──────────────────────────────────────────────────────────────────────────────

MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April',
    5: 'May', 6: 'June', 7: 'July', 8: 'August',
    9: 'September', 10: 'October', 11: 'November', 12: 'December'
}
MONTH_ORDER = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}


def find_pdfs(base_dir: Path) -> list[Path]:
    pdfs = list(base_dir.glob("*.pdf"))
    for subdir in base_dir.iterdir():
        if subdir.is_dir() and re.match(r'^\d{4}$', subdir.name):
            pdfs.extend(subdir.glob("*.pdf"))
    return sorted(pdfs)


def parse_date(date_str: str) -> tuple[int, int, int]:
    parts = date_str.strip().split()
    return int(parts[2]), MONTH_ORDER.get(parts[1].upper(), 0), int(parts[0])


def extract_releases_from_pdf(path: Path) -> list[dict]:
    releases = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size"])
            lines = defaultdict(list)
            for w in words:
                lines[round(w['top'] / 2) * 2].append(w)

            current_date = None
            for y_key in sorted(lines.keys()):
                line_words = sorted(lines[y_key], key=lambda w: w['x0'])
                line_text = ' '.join(w['text'] for w in line_words)

                date_match = re.match(r'Released\s+(\d+\s+\w+\s+\d{4})', line_text)
                if date_match:
                    current_date = date_match.group(1)
                    continue

                if any(skip in line_text for skip in [
                    'KEY', 'ARIA AUSTRALIAN', '© 1988', 'ARIA Accreditations',
                    'the ARIA logo', 'PO Box', 'Title Artist', 'Released'
                ]):
                    continue

                if not current_date:
                    continue

                title_words, artist_words, type_word, label_words = [], [], None, []
                for w in line_words:
                    x = w['x0']
                    if x < 300:    title_words.append(w['text'])
                    elif x < 480:  artist_words.append(w['text'])
                    elif x < 520:  type_word = w['text']
                    else:          label_words.append(w['text'])

                title  = ' '.join(title_words).strip()
                artist = ' '.join(artist_words).strip()
                label  = ' '.join(label_words).strip()

                if title and artist and type_word in ('S', 'A'):
                    year, month, day = parse_date(current_date)
                    releases.append({
                        'date':       current_date,
                        'title':      title,
                        'artist':     artist,
                        'type':       'Album' if type_word == 'A' else 'Single',
                        'label':      label,
                        'year':       year,
                        'month':      month,
                        'day':        day,
                        'month_name': MONTH_NAMES.get(month, ''),
                        'sort_date':  year * 10000 + month * 100 + day,
                    })
    return releases


def build_html(releases: list[dict], supabase_url: str, supabase_key: str) -> str:
    releases_json = json.dumps(releases, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARIA New Releases</title>
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
<style>
  :root {{
    --bg: #F8F7FF;
    --surface: #FFFFFF;
    --surface2: #F2F0FF;
    --border: #E4E0FF;
    --text: #1A1633;
    --text2: #6B6490;
    --album: #7C3AED;
    --album-bg: #EDE9FE;
    --single: #EC4899;
    --single-bg: #FCE7F3;
    --nav-active: #7C3AED;
    --radius: 12px;
    --shadow: 0 2px 12px rgba(124,58,237,0.08);
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }}

  header {{
    background: linear-gradient(135deg, #7C3AED 0%, #EC4899 50%, #F59E0B 100%);
    padding: 28px 32px 24px;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px;
  }}
  .header-left {{ display: flex; align-items: center; gap: 16px; }}
  .logo {{
    width: 52px; height: 52px; border-radius: 50%;
    background: rgba(255,255,255,0.2); backdrop-filter: blur(10px);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; font-weight: 900; color: white; letter-spacing: -1px;
    border: 2px solid rgba(255,255,255,0.4);
  }}
  header h1 {{ font-size: 28px; font-weight: 800; color: white; letter-spacing: -0.5px; }}
  header p {{ font-size: 13px; color: rgba(255,255,255,0.75); margin-top: 2px; }}
  .year-badge {{
    background: rgba(255,255,255,0.25); color: white; border: 1.5px solid rgba(255,255,255,0.4);
    border-radius: 999px; padding: 6px 18px; font-size: 14px; font-weight: 700; cursor: pointer;
    transition: background 0.15s;
  }}
  .year-badge:hover {{ background: rgba(255,255,255,0.35); }}
  .year-badge.active {{ background: white; color: #7C3AED; }}

  .nav {{
    display: flex; align-items: center;
    background: var(--surface); border-bottom: 1.5px solid var(--border);
    padding: 0 32px; position: sticky; top: 0; z-index: 100;
    box-shadow: 0 1px 8px rgba(0,0,0,0.06);
  }}
  .nav-tabs {{ display: flex; }}
  .nav-tab {{
    padding: 16px 24px; font-size: 14px; font-weight: 600; color: var(--text2);
    cursor: pointer; border-bottom: 3px solid transparent; transition: all 0.15s; user-select: none;
  }}
  .nav-tab:hover {{ color: var(--nav-active); }}
  .nav-tab.active {{ color: var(--nav-active); border-bottom-color: var(--nav-active); }}
  .nav-filters {{ margin-left: auto; display: flex; gap: 8px; align-items: center; }}
  .filter-btn {{
    padding: 6px 16px; border-radius: 999px; font-size: 13px; font-weight: 600;
    cursor: pointer; border: 2px solid transparent; transition: all 0.15s; user-select: none;
  }}
  .filter-all {{ background: var(--surface2); color: var(--text); border-color: var(--border); }}
  .filter-all.active {{ background: var(--text); color: white; border-color: var(--text); }}
  .filter-album {{ background: var(--album-bg); color: var(--album); border-color: var(--album-bg); }}
  .filter-album.active {{ background: var(--album); color: white; border-color: var(--album); }}
  .filter-single {{ background: var(--single-bg); color: var(--single); border-color: var(--single-bg); }}
  .filter-single.active {{ background: var(--single); color: white; border-color: var(--single); }}
  .nav-divider {{ width: 1px; height: 20px; background: var(--border); margin: 0 4px; }}
  .filter-unheard {{ background: #D1FAE5; color: #065F46; border-color: #D1FAE5; }}
  .filter-unheard.active {{ background: #10B981; color: white; border-color: #10B981; }}
  .filter-listened {{ background: #D1FAE5; color: #065F46; border-color: #D1FAE5; }}
  .filter-listened.active {{ background: #059669; color: white; border-color: #059669; }}
  .view-toggle {{ display: flex; gap: 2px; background: var(--surface2); border-radius: 8px; padding: 3px; }}
  .view-toggle-btn {{
    padding: 5px 10px; border-radius: 6px; font-size: 13px; cursor: pointer;
    color: var(--text2); transition: all 0.15s; user-select: none; line-height: 1;
  }}
  .view-toggle-btn.active {{ background: var(--surface); color: var(--text); box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}

  .sync-indicator {{ font-size: 11px; color: rgba(255,255,255,0.8); display: flex; align-items: center; gap: 6px; }}
  .sync-dot {{ width: 7px; height: 7px; border-radius: 50%; background: #10B981; transition: background 0.3s; }}
  .sync-dot.syncing {{ background: #F59E0B; animation: pulse 1s infinite; }}
  .sync-dot.error {{ background: #EF4444; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:0.4 }} }}

  .search-bar {{ padding: 16px 32px; background: var(--surface); border-bottom: 1.5px solid var(--border); display: none; }}
  .search-bar.visible {{ display: block; }}
  .search-input {{
    width: 100%; max-width: 480px; padding: 10px 16px;
    border: 2px solid var(--border); border-radius: var(--radius);
    font-size: 14px; color: var(--text); background: var(--bg); outline: none; transition: border-color 0.15s;
  }}
  .search-input:focus {{ border-color: var(--nav-active); }}
  .search-input::placeholder {{ color: var(--text2); }}

  main {{ padding: 32px; max-width: 1280px; margin: 0 auto; }}

  .stats {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .stat-chip {{
    display: flex; align-items: center; gap: 8px;
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: 999px; padding: 8px 18px; font-size: 13px;
  }}
  .stat-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
  .stat-num {{ font-weight: 700; color: var(--text); }}
  .stat-label {{ color: var(--text2); }}

  .month-section {{ margin-bottom: 48px; }}
  .month-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }}
  .month-pill {{ font-size: 22px; font-weight: 800; color: var(--text); letter-spacing: -0.5px; }}
  .month-count {{ background: var(--surface2); color: var(--text2); border-radius: 999px; padding: 4px 12px; font-size: 12px; font-weight: 600; }}

  .week-group {{ margin-bottom: 24px; }}
  .week-header {{
    font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
    color: var(--text2); margin-bottom: 12px; display: flex; align-items: center; gap: 10px;
  }}
  .week-header::after {{ content: ''; flex: 1; height: 1px; background: var(--border); }}

  .release-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }}
  .release-card {{
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: var(--radius); padding: 14px 16px;
    transition: all 0.15s; cursor: pointer; position: relative; overflow: hidden;
  }}
  .release-card::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; }}
  .release-card.album::before {{ background: var(--album); }}
  .release-card.single::before {{ background: var(--single); }}
  .release-card:hover {{ transform: translateY(-2px); box-shadow: var(--shadow); border-color: transparent; }}
  .release-card.album:hover {{ box-shadow: 0 4px 16px rgba(124,58,237,0.15); }}
  .release-card.single:hover {{ box-shadow: 0 4px 16px rgba(236,72,153,0.15); }}
  .release-card.listened {{ opacity: 0.5; }}
  .release-card.listened .release-title {{ text-decoration: line-through; color: var(--text2); }}

  .release-title {{ font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 4px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .release-artist {{ font-size: 12px; color: var(--text2); margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .release-footer {{ display: flex; align-items: center; gap: 4px; }}
  .type-badge {{ font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 3px 8px; border-radius: 4px; }}
  .type-badge.album {{ background: var(--album-bg); color: var(--album); }}
  .type-badge.single {{ background: var(--single-bg); color: var(--single); }}
  .release-label {{ font-size: 10px; color: var(--text2); font-weight: 500; flex: 1; }}

  .am-btn {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%;
    background: #FC3C44; color: white; font-size: 9px; line-height: 1;
    text-decoration: none; flex-shrink: 0; transition: transform 0.15s, opacity 0.15s; padding-left: 1px;
  }}
  .am-btn:hover {{ transform: scale(1.15); opacity: 0.9; }}

  .listened-btn {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
    border: 1.5px solid var(--border); background: var(--surface);
    cursor: pointer; transition: all 0.15s; font-size: 11px; color: transparent;
  }}
  .listened-btn:hover {{ border-color: #10B981; color: #10B981; }}
  .listened-btn.done {{ background: #10B981; border-color: #10B981; color: white; }}

  .release-table {{ width: 100%; border-collapse: collapse; }}
  .release-table thead th {{
    text-align: left; font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text2); padding: 8px 12px;
    border-bottom: 1.5px solid var(--border); background: var(--surface);
    position: sticky; top: 57px; z-index: 2;
  }}
  .release-table tbody tr {{ border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.1s; }}
  .release-table tbody tr:hover {{ background: var(--surface2); }}
  .release-table tbody tr:last-child {{ border-bottom: none; }}
  .release-table td {{ padding: 7px 12px; font-size: 13px; vertical-align: middle; }}
  .release-table .col-title {{ font-weight: 600; color: var(--text); max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .release-table .col-artist {{ color: var(--text2); max-width: 200px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .release-table .col-label {{ color: var(--text2); font-size: 11px; }}
  tr.listened td {{ opacity: 0.45; }}
  tr.listened .col-title-cell {{ text-decoration: line-through; }}
  .table-date-row td {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; color: var(--text2); padding: 10px 12px 6px; background: var(--bg); border-bottom: none !important; cursor: default !important; }}
  .table-date-row:hover {{ background: var(--bg) !important; }}
  .col-play {{ width: 32px; text-align: center; }}
  .col-check {{ width: 36px; text-align: center; }}

  .artist-layout {{ display: grid; grid-template-columns: 300px 1fr; gap: 24px; align-items: start; }}
  .artist-sidebar {{
    background: var(--surface); border: 1.5px solid var(--border);
    border-radius: var(--radius); overflow: hidden;
    position: sticky; top: 72px; max-height: calc(100vh - 100px); overflow-y: auto;
  }}
  .artist-sidebar-header {{ padding: 16px 20px; border-bottom: 1.5px solid var(--border); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: var(--text2); position: sticky; top: 0; background: var(--surface); z-index: 1; }}
  .alpha-index {{ display: flex; flex-wrap: wrap; gap: 4px; padding: 12px 20px; border-bottom: 1.5px solid var(--border); }}
  .alpha-btn {{ width: 26px; height: 26px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; cursor: pointer; color: var(--text2); transition: all 0.1s; }}
  .alpha-btn:hover {{ background: var(--surface2); color: var(--text); }}
  .alpha-btn.has-artists {{ color: var(--nav-active); }}
  .artist-list {{ padding: 8px; }}
  .artist-item {{ padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; color: var(--text); transition: all 0.12s; display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
  .artist-item:hover {{ background: var(--surface2); }}
  .artist-item.active {{ background: var(--album); color: white; }}
  .artist-item .artist-name {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .artist-item .artist-count {{ font-size: 11px; font-weight: 700; opacity: 0.6; background: rgba(0,0,0,0.08); border-radius: 999px; padding: 2px 7px; min-width: 24px; text-align: center; flex-shrink: 0; }}
  .artist-item.active .artist-count {{ background: rgba(255,255,255,0.25); opacity: 1; }}

  .artist-detail {{ background: var(--surface); border: 1.5px solid var(--border); border-radius: var(--radius); padding: 28px; min-height: 300px; }}
  .artist-detail-empty {{ display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 300px; color: var(--text2); gap: 8px; }}
  .artist-detail-empty .big-icon {{ font-size: 48px; }}
  .artist-detail-header {{ margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1.5px solid var(--border); }}
  .artist-detail-name {{ font-size: 28px; font-weight: 800; color: var(--text); margin-bottom: 8px; }}
  .artist-detail-meta {{ display: flex; gap: 12px; flex-wrap: wrap; }}
  .artist-meta-chip {{ font-size: 12px; font-weight: 600; padding: 4px 12px; border-radius: 999px; background: var(--surface2); color: var(--text2); }}

  .timeline-item {{ display: grid; grid-template-columns: 120px 1fr; gap: 20px; margin-bottom: 12px; align-items: start; }}
  .timeline-date {{ text-align: right; padding-top: 14px; font-size: 11px; font-weight: 700; color: var(--text2); letter-spacing: 0.5px; text-transform: uppercase; }}
  .timeline-card {{ background: var(--bg); border: 1.5px solid var(--border); border-radius: var(--radius); padding: 14px 16px; border-left: 4px solid; }}
  .timeline-card.album {{ border-left-color: var(--album); }}
  .timeline-card.single {{ border-left-color: var(--single); }}
  .timeline-card-title {{ font-size: 14px; font-weight: 700; margin-bottom: 4px; }}
  .timeline-card-meta {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}

  .no-results {{ text-align: center; padding: 48px; color: var(--text2); font-size: 15px; }}
  .hidden {{ display: none !important; }}

  .artist-sidebar::-webkit-scrollbar {{ width: 4px; }}
  .artist-sidebar::-webkit-scrollbar-track {{ background: transparent; }}
  .artist-sidebar::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}

  @media (max-width: 768px) {{
    header {{ padding: 20px 16px; }}
    .nav {{ padding: 0 16px; overflow-x: auto; }}
    main {{ padding: 20px 16px; }}
    .artist-layout {{ grid-template-columns: 1fr; }}
    .artist-sidebar {{ position: static; max-height: 300px; }}
    .timeline-item {{ grid-template-columns: 90px 1fr; }}
  }}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="logo">AR</div>
    <div>
      <h1>ARIA New Releases</h1>
      <p>Australian Recording Industry Association · Official Chart Data</p>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
    <div class="sync-indicator">
      <div class="sync-dot syncing" id="sync-dot"></div>
      <span id="sync-label">Loading…</span>
    </div>
    <div id="year-tabs" style="display:flex;gap:8px;"></div>
  </div>
</header>

<nav class="nav">
  <div class="nav-tabs">
    <div class="nav-tab active" data-view="months" onclick="switchView('months')">📅 Monthly</div>
    <div class="nav-tab" data-view="artists" onclick="switchView('artists')">🎤 Artists</div>
  </div>
  <div class="nav-filters">
    <div class="filter-btn filter-all active" onclick="setFilter('all')">All</div>
    <div class="filter-btn filter-album" onclick="setFilter('Album')">Albums</div>
    <div class="filter-btn filter-single" onclick="setFilter('Single')">Singles</div>
    <div class="nav-divider"></div>
    <div class="filter-btn filter-unheard" onclick="setListenedFilter('unheard')">Unheard</div>
    <div class="filter-btn filter-listened" onclick="setListenedFilter('listened')">Listened</div>
    <div class="nav-divider" id="view-toggle-divider"></div>
    <div class="view-toggle" id="view-toggle-btns">
      <div class="view-toggle-btn active" id="btn-cards" onclick="setDisplayMode('cards')" title="Card view">▦</div>
      <div class="view-toggle-btn" id="btn-table" onclick="setDisplayMode('table')" title="Table view">☰</div>
    </div>
  </div>
</nav>

<div class="search-bar" id="search-bar">
  <input class="search-input" id="artist-search" type="text" placeholder="Search artists…" oninput="filterArtists(this.value)">
</div>

<main>
  <div class="stats" id="stats-bar"></div>
  <div id="view-months"></div>
  <div id="view-artists" style="display:none"></div>
</main>

<script>
const ALL_RELEASES = {releases_json};

// ── Supabase ──────────────────────────────────────────────────────────────────
const {{ createClient }} = supabase;
const sb = createClient('{supabase_url}', '{supabase_key}');
let listenedSet = new Set();

function setSyncState(state) {{
  const dot   = document.getElementById('sync-dot');
  const label = document.getElementById('sync-label');
  dot.className   = 'sync-dot' + (state === 'syncing' ? ' syncing' : state === 'error' ? ' error' : '');
  label.textContent = state === 'syncing' ? 'Loading…' : state === 'error' ? 'Sync error' : 'Synced';
}}

async function loadListened() {{
  const {{ data, error }} = await sb.from('listened_releases').select('key');
  if (error) {{ setSyncState('error'); return; }}
  listenedSet = new Set((data || []).map(r => r.key));
  setSyncState('ok');
}}

async function toggleListened(btn) {{
  const key = btn.dataset.lkey;
  if (!key) return;
  const wasListened = listenedSet.has(key);
  // Optimistic update
  if (wasListened) {{
    listenedSet.delete(key);
    btn.classList.remove('done');
    btn.closest('.release-card, tr')?.classList.remove('listened');
  }} else {{
    listenedSet.add(key);
    btn.classList.add('done');
    btn.closest('.release-card, tr')?.classList.add('listened');
  }}
  if (currentListenedFilter !== 'all') render();
  // Persist to Supabase
  setSyncState('syncing');
  const {{ error }} = wasListened
    ? await sb.from('listened_releases').delete().eq('key', key)
    : await sb.from('listened_releases').insert({{ key }});
  setSyncState(error ? 'error' : 'ok');
  if (error) {{
    // Revert on failure
    if (wasListened) {{ listenedSet.add(key);    btn.classList.add('done');    btn.closest('.release-card, tr')?.classList.add('listened'); }}
    else             {{ listenedSet.delete(key); btn.classList.remove('done'); btn.closest('.release-card, tr')?.classList.remove('listened'); }}
  }}
}}
// ─────────────────────────────────────────────────────────────────────────────

let currentView          = 'months';
let currentFilter        = 'all';
let currentListenedFilter = 'all';
let currentDisplayMode   = 'cards';
let currentYear          = null;
let selectedArtist       = null;

function plural(n, word) {{ return n === 1 ? `${{n}} ${{word}}` : `${{n}} ${{word}}s`; }}
function listenedKey(r)  {{ return r.artist + '|' + r.title + '|' + r.date; }}
function isListened(r)   {{ return listenedSet.has(listenedKey(r)); }}
function esc(s)          {{ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }}
function amUrl(a, t)     {{ return 'https://music.apple.com/search?term=' + encodeURIComponent(a + ' ' + t); }}

const years = [...new Set(ALL_RELEASES.map(r => r.year))].sort();
currentYear = years[years.length - 1];

function getFiltered(year, type) {{
  return ALL_RELEASES.filter(r => {{
    if (r.year !== year) return false;
    if (type !== 'all' && r.type !== type) return false;
    if (currentListenedFilter === 'unheard'  &&  isListened(r)) return false;
    if (currentListenedFilter === 'listened' && !isListened(r)) return false;
    return true;
  }});
}}

function buildYearTabs() {{
  document.getElementById('year-tabs').innerHTML = years.map(y =>
    `<button class="year-badge ${{y===currentYear?'active':''}}" onclick="selectYear(${{y}})">${{y}}</button>`
  ).join('');
}}
function selectYear(y) {{ currentYear = y; buildYearTabs(); render(); }}

function buildStats(releases) {{
  const albums  = releases.filter(r=>r.type==='Album').length;
  const singles = releases.filter(r=>r.type==='Single').length;
  const artists = new Set(releases.map(r=>r.artist)).size;
  document.getElementById('stats-bar').innerHTML = `
    <div class="stat-chip"><div class="stat-dot" style="background:#7C3AED"></div><span class="stat-num">${{albums}}</span><span class="stat-label">Albums</span></div>
    <div class="stat-chip"><div class="stat-dot" style="background:#EC4899"></div><span class="stat-num">${{singles}}</span><span class="stat-label">Singles</span></div>
    <div class="stat-chip"><div class="stat-dot" style="background:#06B6D4"></div><span class="stat-num">${{artists}}</span><span class="stat-label">Artists</span></div>
    <div class="stat-chip"><div class="stat-dot" style="background:#F59E0B"></div><span class="stat-num">${{releases.length}}</span><span class="stat-label">Total Releases</span></div>`;
}}

function buildMonthView(releases) {{
  const byMonth = {{}};
  releases.forEach(r => {{
    if (!byMonth[r.month]) byMonth[r.month] = {{}};
    if (!byMonth[r.month][r.date]) byMonth[r.month][r.date] = [];
    byMonth[r.month][r.date].push(r);
  }});
  const MNAMES = {{1:'January',2:'February',3:'March',4:'April',5:'May',6:'June',7:'July',8:'August',9:'September',10:'October',11:'November',12:'December'}};
  let html = '';
  Object.keys(byMonth).sort((a,b)=>a-b).forEach(mon => {{
    const monthReleases = Object.values(byMonth[mon]).flat();
    const sortedDates = Object.keys(byMonth[mon]).sort((a,b) => {{
      const [da,ma,ya] = a.split(' '), [db,mb,yb] = b.split(' ');
      return new Date(`${{ma}} ${{da}} ${{ya}}`)-new Date(`${{mb}} ${{db}} ${{yb}}`);
    }});
    html += `<div class="month-section"><div class="month-header"><span class="month-pill">${{MNAMES[mon]}}</span><span class="month-count">${{plural(monthReleases.length,'release')}}</span></div>`;
    if (currentDisplayMode === 'cards') {{
      sortedDates.forEach(date => {{
        const [d,m,y] = date.split(' ');
        const fmt = new Date(`${{m}} ${{d}} ${{y}}`).toLocaleDateString('en-AU',{{weekday:'long',day:'numeric',month:'long'}});
        html += `<div class="week-group"><div class="week-header">${{fmt}} · ${{plural(byMonth[mon][date].length,'release')}}</div><div class="release-grid">`;
        byMonth[mon][date].forEach(r => {{
          const lKey = listenedKey(r), lDone = isListened(r);
          html += `<div class="release-card ${{r.type.toLowerCase()}}${{lDone?' listened':''}}" onclick="goToArtist(${{JSON.stringify(r.artist)}})">
            <div class="release-title" title="${{esc(r.title)}}">${{esc(r.title)}}</div>
            <div class="release-artist">${{esc(r.artist)}}</div>
            <div class="release-footer">
              <span class="type-badge ${{r.type.toLowerCase()}}">${{r.type}}</span>
              <span class="release-label">${{esc(r.label)}}</span>
              <a class="am-btn" href="${{amUrl(r.artist,r.title)}}" target="_blank" onclick="event.stopPropagation()" title="Apple Music">▶</a>
              <div class="listened-btn${{lDone?' done':''}}" data-lkey="${{esc(lKey)}}" onclick="event.stopPropagation();toggleListened(this)" title="Mark as listened">✓</div>
            </div>
          </div>`;
        }});
        html += `</div></div>`;
      }});
    }} else {{
      html += `<table class="release-table"><thead><tr><th class="col-play"></th><th>Title</th><th>Artist</th><th>Type</th><th>Label</th><th>Date</th><th class="col-check"></th></tr></thead><tbody>`;
      sortedDates.forEach(date => {{
        const [d,m,y] = date.split(' ');
        const fmt = new Date(`${{m}} ${{d}} ${{y}}`).toLocaleDateString('en-AU',{{weekday:'long',day:'numeric',month:'long'}});
        html += `<tr class="table-date-row"><td colspan="7">${{fmt}} · ${{plural(byMonth[mon][date].length,'release')}}</td></tr>`;
        byMonth[mon][date].forEach(r => {{
          const lKey = listenedKey(r), lDone = isListened(r);
          html += `<tr class="${{lDone?'listened':''}}" onclick="goToArtist(${{JSON.stringify(r.artist)}})">
            <td class="col-play"><a class="am-btn" href="${{amUrl(r.artist,r.title)}}" target="_blank" onclick="event.stopPropagation()" title="Apple Music">▶</a></td>
            <td class="col-title col-title-cell" title="${{esc(r.title)}}">${{esc(r.title)}}</td>
            <td class="col-artist">${{esc(r.artist)}}</td>
            <td><span class="type-badge ${{r.type.toLowerCase()}}">${{r.type}}</span></td>
            <td class="col-label">${{esc(r.label)}}</td>
            <td class="col-label">${{fmt}}</td>
            <td class="col-check"><div class="listened-btn${{lDone?' done':''}}" data-lkey="${{esc(lKey)}}" onclick="event.stopPropagation();toggleListened(this)" title="Mark as listened">✓</div></td>
          </tr>`;
        }});
      }});
      html += `</tbody></table>`;
    }}
    html += `</div>`;
  }});
  document.getElementById('view-months').innerHTML = html || '<div class="no-results">No releases match the current filters.</div>';
}}

function buildArtistView() {{
  const artistMap = {{}};
  ALL_RELEASES.forEach(r => {{ if (!artistMap[r.artist]) artistMap[r.artist]=[]; artistMap[r.artist].push(r); }});
  const filteredMap = {{}};
  Object.keys(artistMap).forEach(a => {{
    const f = artistMap[a].filter(r => currentFilter==='all' || r.type===currentFilter);
    if (f.length) filteredMap[a] = f;
  }});
  const sorted  = Object.keys(filteredMap).sort((a,b)=>a.localeCompare(b));
  const letters = [...new Set(sorted.map(a=>a[0].toUpperCase()))];
  const alphaHtml = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ#'.split('').map(ch =>
    `<div class="alpha-btn ${{letters.includes(ch)?'has-artists':''}}" onclick="scrollToLetter('${{ch}}')">${{ch}}</div>`
  ).join('');
  const listHtml = sorted.map(a =>
    `<div class="artist-item ${{a===selectedArtist?'active':''}}" data-artist="${{esc(a)}}" data-first="${{a[0].toUpperCase()}}" onclick="selectArtist(${{JSON.stringify(a)}})">
      <span class="artist-name">${{esc(a)}}</span><span class="artist-count">${{filteredMap[a].length}}</span>
    </div>`
  ).join('');
  const detailHtml = selectedArtist && filteredMap[selectedArtist]
    ? buildDetail(selectedArtist, filteredMap[selectedArtist])
    : `<div class="artist-detail-empty"><div class="big-icon">🎤</div><div>Select an artist to see their releases</div></div>`;
  document.getElementById('view-artists').innerHTML = `
    <div class="artist-layout">
      <div class="artist-sidebar">
        <div class="artist-sidebar-header">Artists (${{sorted.length}})</div>
        <div class="alpha-index">${{alphaHtml}}</div>
        <div class="artist-list" id="artist-list">${{listHtml}}</div>
      </div>
      <div class="artist-detail" id="artist-detail">${{detailHtml}}</div>
    </div>`;
}}

function buildDetail(artist, releases) {{
  releases = releases.slice().sort((a,b)=>a.sort_date-b.sort_date);
  const albums    = releases.filter(r=>r.type==='Album').length;
  const singles   = releases.filter(r=>r.type==='Single').length;
  const yearRange = [...new Set(releases.map(r=>r.year))].sort();
  const yearStr   = yearRange.length>1 ? `${{yearRange[0]}}–${{yearRange[yearRange.length-1]}}` : `${{yearRange[0]}}`;
  const labels    = [...new Set(releases.map(r=>r.label))].join(', ');
  let tl = '';
  releases.forEach(r => {{
    const [d,m,y] = r.date.split(' ');
    const fmt  = new Date(`${{m}} ${{d}} ${{y}}`).toLocaleDateString('en-AU',{{day:'numeric',month:'short',year:'numeric'}});
    const lKey = listenedKey(r), lDone = isListened(r);
    tl += `<div class="timeline-item">
      <div class="timeline-date">${{fmt}}</div>
      <div class="timeline-card ${{r.type.toLowerCase()}}">
        <div class="timeline-card-title">${{esc(r.title)}}</div>
        <div class="timeline-card-meta">
          <span class="type-badge ${{r.type.toLowerCase()}}">${{r.type}}</span>
          <span class="release-label">${{esc(r.label)}}</span>
          <a class="am-btn" href="${{amUrl(r.artist,r.title)}}" target="_blank" title="Apple Music">▶</a>
          <div class="listened-btn${{lDone?' done':''}}" data-lkey="${{esc(lKey)}}" onclick="toggleListened(this)" title="Mark as listened">✓</div>
        </div>
      </div>
    </div>`;
  }});
  return `
    <div class="artist-detail-header">
      <div class="artist-detail-name">${{esc(artist)}}</div>
      <div class="artist-detail-meta">
        <span class="artist-meta-chip">📅 ${{yearStr}}</span>
        ${{albums>0?`<span class="artist-meta-chip" style="background:#EDE9FE;color:#7C3AED">💿 ${{albums}} Album${{albums>1?'s':''}}</span>`:''}}
        ${{singles>0?`<span class="artist-meta-chip" style="background:#FCE7F3;color:#EC4899">🎵 ${{singles}} Single${{singles>1?'s':''}}</span>`:''}}
        <span class="artist-meta-chip">🏷️ ${{esc(labels)}}</span>
      </div>
    </div>
    <div class="timeline">${{tl}}</div>`;
}}

function selectArtist(artist) {{
  selectedArtist = artist;
  document.querySelectorAll('.artist-item').forEach(el => el.classList.toggle('active', el.dataset.artist===artist));
  const artistMap = {{}};
  ALL_RELEASES.forEach(r => {{ if (!artistMap[r.artist]) artistMap[r.artist]=[]; artistMap[r.artist].push(r); }});
  const f = (artistMap[artist]||[]).filter(r => currentFilter==='all' || r.type===currentFilter);
  document.getElementById('artist-detail').innerHTML = buildDetail(artist, f);
}}

function goToArtist(artist)   {{ selectedArtist = artist; switchView('artists'); }}
function scrollToLetter(letter) {{
  for (const item of document.querySelectorAll('.artist-item')) {{
    if (item.dataset.first === letter) {{ item.scrollIntoView({{behavior:'smooth',block:'start'}}); break; }}
  }}
}}
function filterArtists(query) {{
  const q = query.toLowerCase();
  document.querySelectorAll('.artist-item').forEach(el => el.classList.toggle('hidden', !el.dataset.artist.toLowerCase().includes(q)));
}}
function setListenedFilter(val) {{
  currentListenedFilter = currentListenedFilter === val ? 'all' : val;
  document.querySelector('.filter-unheard').classList.toggle('active', currentListenedFilter==='unheard');
  document.querySelector('.filter-listened').classList.toggle('active', currentListenedFilter==='listened');
  render();
}}
function setDisplayMode(mode) {{
  currentDisplayMode = mode;
  document.getElementById('btn-cards').classList.toggle('active', mode==='cards');
  document.getElementById('btn-table').classList.toggle('active', mode==='table');
  if (currentView === 'months') render();
}}
function switchView(view) {{
  currentView = view;
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.view===view));
  document.getElementById('view-months').style.display   = view==='months'  ? 'block' : 'none';
  document.getElementById('view-artists').style.display  = view==='artists' ? 'block' : 'none';
  document.getElementById('search-bar').classList.toggle('visible', view==='artists');
  const showToggle = view === 'months';
  document.getElementById('view-toggle-btns').style.display    = showToggle ? '' : 'none';
  document.getElementById('view-toggle-divider').style.display = showToggle ? '' : 'none';
  render();
}}
function setFilter(type) {{
  currentFilter = type;
  document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
  const map = {{all:'.filter-all',Album:'.filter-album',Single:'.filter-single'}};
  if (map[type]) document.querySelector(map[type]).classList.add('active');
  render();
}}
function render() {{
  buildStats(getFiltered(currentYear, currentFilter));
  if (currentView==='months') buildMonthView(getFiltered(currentYear, currentFilter));
  else buildArtistView();
}}

// Init — fetch listened state, then render
loadListened().then(() => {{ buildYearTabs(); render(); }});
</script>
</body>
</html>"""


def main():
    print("🔍 Scanning for PDFs...")
    if not PDF_DIR.exists():
        print(f"   ⚠️  PDF_DIR not found: {PDF_DIR}")
        print("   Edit the PDF_DIR variable at the top of this script.")
        sys.exit(1)

    pdfs = find_pdfs(PDF_DIR)
    print(f"   Found {len(pdfs)} PDF(s) in {PDF_DIR}")

    all_releases = []
    for pdf in pdfs:
        print(f"   Parsing: {pdf.name}...", end=' ')
        releases = extract_releases_from_pdf(pdf)
        print(f"{len(releases)} releases")
        all_releases.extend(releases)

    seen = set()
    deduped = []
    for r in all_releases:
        if r['artist'] in EXCLUDED_ARTISTS:
            continue
        key = (r['title'], r['artist'], r['date'])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    deduped.sort(key=lambda r: (r['sort_date'], r['artist'], r['title']))
    print(f"\n📊 Total: {len(deduped)} unique releases ({len(all_releases) - len(deduped)} duplicates removed)")

    print("🎨 Generating HTML...")
    html = build_html(deduped, SUPABASE_URL, SUPABASE_KEY)

    output_path = REPO_DIR / "index.html"
    output_path.write_text(html, encoding='utf-8')
    print(f"✅ Saved: {output_path}")
    print(f"\nPush to GitHub and enable Pages to deploy.")


if __name__ == '__main__':
    main()
