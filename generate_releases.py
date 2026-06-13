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

import calendar
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber", "--break-system-packages", "-q"])
    import pdfplumber

# ── Config ────────────────────────────────────────────────────────────────────
REPO_DIR      = Path(__file__).parent
PDF_DIR       = Path.home() / "IHGT" / "Research" / "ARIA"
TEMPLATE_PATH = REPO_DIR / "template.html"

SUPABASE_URL = "https://dqxecdrzdzkitdkecsca.supabase.co"
SUPABASE_KEY = "sb_publishable_7AjtdPGsMa3wHcB7DWC_-A_bhNNOuEh"

EXCLUDED_ARTISTS = frozenset({'The Wiggles', 'Dorothy The Dinosaur', 'Los Wiggles'})

# PDF column x-coordinate boundaries (points from left margin)
TITLE_COL_MAX  = 300
ARTIST_COL_MAX = 480
TYPE_COL_MAX   = 520

HEADER_SKIP_PHRASES = (
    'KEY', 'ARIA AUSTRALIAN', '© 1988', 'ARIA Accreditations',
    'the ARIA logo', 'PO Box', 'Title Artist', 'Released',
)
# ──────────────────────────────────────────────────────────────────────────────


def find_pdfs(base_dir: Path) -> list[Path]:
    pdfs = list(base_dir.glob("*.pdf"))
    for subdir in base_dir.iterdir():
        if subdir.is_dir() and re.match(r'^\d{4}$', subdir.name):
            pdfs.extend(subdir.glob("*.pdf"))
    return sorted(pdfs)


def parse_date(date_str: str) -> tuple[int, int, int]:
    dt = datetime.strptime(date_str.strip().title(), "%d %b %Y")
    return dt.year, dt.month, dt.day


def extract_releases_from_pdf(path: Path) -> list[dict]:
    releases = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size"])
            lines: dict[int, list] = defaultdict(list)
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

                if any(skip in line_text for skip in HEADER_SKIP_PHRASES):
                    continue

                if not current_date:
                    continue

                title_words, artist_words, type_word, label_words = [], [], None, []
                for w in line_words:
                    x = w['x0']
                    if x < TITLE_COL_MAX:    title_words.append(w['text'])
                    elif x < ARTIST_COL_MAX: artist_words.append(w['text'])
                    elif x < TYPE_COL_MAX:   type_word = w['text']
                    else:                    label_words.append(w['text'])

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
                        'month_name': calendar.month_name[month],
                        'sort_date':  year * 10000 + month * 100 + day,
                    })
    return releases


def deduplicate(releases: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    result = []
    for r in releases:
        if r['artist'] in EXCLUDED_ARTISTS:
            continue
        key = (r['title'], r['artist'], r['date'])
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def build_html(releases: list[dict], supabase_url: str, supabase_key: str) -> str:
    template = TEMPLATE_PATH.read_text(encoding='utf-8')
    return (template
        .replace('__RELEASES_JSON__', json.dumps(releases, ensure_ascii=False))
        .replace('__SUPABASE_URL__', supabase_url)
        .replace('__SUPABASE_KEY__', supabase_key))


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

    deduped = deduplicate(all_releases)
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
