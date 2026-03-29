# PDF Splitter

A simple tool for breaking a PDF into smaller pieces. Use the browser-based UI for a quick drag-and-drop experience, or run the Python script directly from the command line if you prefer to stay in the terminal.

## Ways to use it

### Browser UI
Just open the github hosted page

### Command line

Install the one dependency first:
```bash
pip install -r requirements.txt
```

Then run it:
```bash
# Split into 10-page chunks
python pdf_splitter.py input.pdf chunks --chunk-size 10

# Extract specific page ranges (1-indexed, comma-separated)
python pdf_splitter.py input.pdf ranges --ranges "1-5,6-12,20-30"

# One file per page
python pdf_splitter.py input.pdf pages
```

Output files land in a sub-folder next to your input PDF by default. Pass `-o /some/dir` to choose a different location.

## Split modes

| Mode | What it does |
|---|---|
| `chunks` | Groups pages into equal-sized files (default: 10 pages each) |
| `ranges` | Cuts at the exact page ranges you specify |
| `pages` | Every single page becomes its own PDF |
| `letterhead` | Detects a repeating letterhead/logo and splits there automatically |
