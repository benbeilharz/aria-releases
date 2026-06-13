# ARIA New Releases

Generates a browsable HTML page of ARIA new release data from PDF reports.

## Usage

```bash
python3 generate_releases.py
```

This scans `~/IHGT/Research/ARIA/` for PDFs (including year subfolders like `2025/`), parses them, and writes `index.html` to this directory.

Open `index.html` locally or push to GitHub Pages to deploy.

## Dependencies

```bash
pip install pdfplumber
```

`pdfplumber` will also be auto-installed the first time the script runs if it's missing.

## Auto-regenerate on push

A pre-push git hook regenerates `index.html` automatically before each push. Run this once to activate it:

```bash
git config core.hooksPath .githooks
```

If the hook finds that `index.html` changed, it will abort the push and ask you to commit the update first.

## Configuration

Edit the variables at the top of `generate_releases.py`:

| Variable | Default | Description |
|---|---|---|
| `PDF_DIR` | `~/IHGT/Research/ARIA` | Folder containing ARIA PDFs |
| `SUPABASE_URL` | — | Supabase project URL for listened tracking |
| `SUPABASE_KEY` | — | Supabase publishable key |
| `EXCLUDED_ARTISTS` | The Wiggles, etc. | Artists to filter from output |
