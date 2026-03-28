"""
PDF Splitter
============
Splits a PDF into multiple output files using one of three modes:

  chunks   - Split every N pages into a separate file
  ranges   - Split by explicit page ranges (e.g. "1-5,10-15,20")
  pages    - Split every page into its own file
"""

import argparse
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def _save_writer(writer: PdfWriter, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"  Saved: {output_path}")


def _output_path(output_dir: Path, stem: str, index: int, total: int) -> Path:
    """Build a zero-padded output filename."""
    width = len(str(total))
    return output_dir / f"{stem}_{str(index).zfill(width)}.pdf"


# ---------------------------------------------------------------------------
# Split modes
# ---------------------------------------------------------------------------

def split_by_chunks(reader: PdfReader, chunk_size: int, output_dir: Path, stem: str) -> int:
    """Split the PDF into groups of *chunk_size* pages."""
    total_pages = len(reader.pages)
    total_parts = (total_pages + chunk_size - 1) // chunk_size

    for part_index in range(total_parts):
        writer = PdfWriter()
        start = part_index * chunk_size
        end = min(start + chunk_size, total_pages)
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])
        out = _output_path(output_dir, stem, part_index + 1, total_parts)
        _save_writer(writer, out)

    return total_parts


def split_by_ranges(reader: PdfReader, ranges_str: str, output_dir: Path, stem: str) -> int:
    """
    Split by explicit page ranges.

    Ranges are 1-indexed and comma-separated, e.g.:
        "1-5,6-10,15,20-25"
    Single page numbers are treated as a single-page range.
    """
    total_pages = len(reader.pages)
    raw_parts = [r.strip() for r in ranges_str.split(",") if r.strip()]
    parsed: list[tuple[int, int]] = []

    for part in raw_parts:
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(part)

        if start < 1 or end > total_pages or start > end:
            print(
                f"  Warning: range '{part}' is out of bounds "
                f"(PDF has {total_pages} pages). Skipping.",
                file=sys.stderr,
            )
            continue
        parsed.append((start, end))

    total_parts = len(parsed)
    for idx, (start, end) in enumerate(parsed, start=1):
        writer = PdfWriter()
        for page_num in range(start - 1, end):   # convert to 0-indexed
            writer.add_page(reader.pages[page_num])
        out = _output_path(output_dir, stem, idx, total_parts)
        _save_writer(writer, out)

    return total_parts


def split_into_pages(reader: PdfReader, output_dir: Path, stem: str) -> int:
    """Extract every page into its own PDF file."""
    total_pages = len(reader.pages)

    for page_num in range(total_pages):
        writer = PdfWriter()
        writer.add_page(reader.pages[page_num])
        out = _output_path(output_dir, stem, page_num + 1, total_pages)
        _save_writer(writer, out)

    return total_pages


def _page_has_image(page) -> bool:
    """Return True if the page contains at least one /Subtype /Image XObject."""
    resources = page.get("/Resources")
    if not resources:
        return False
    xobjects = resources.get("/XObject")
    if not xobjects:
        return False
    for obj in xobjects.values():
        if hasattr(obj, "get") and obj.get("/Subtype") == "/Image":
            return True
    return False


def split_by_letterhead(
    reader: PdfReader,
    output_dir: Path,
    stem: str,
    marker_text: str = "VENUE RENTAL AGREEMENT",
) -> int:
    """
    Split the PDF at every page that contains both an image (the letterhead logo,
    detected via /Subtype /Image in the page's XObject resources) and the
    marker_text.  Each matching page starts a new output PDF.
    """
    total_pages = len(reader.pages)
    split_indices: list[int] = []

    for i, page in enumerate(reader.pages):
        if _page_has_image(page):
            text = page.extract_text() or ""
            if marker_text.upper() in text.upper():
                split_indices.append(i)
                print(f"  Split point detected at page {i + 1}")

    if not split_indices:
        print(
            "  Warning: no letterhead split points found — outputting as single file.",
            file=sys.stderr,
        )
        split_indices = [0]

    total_parts = len(split_indices)
    for idx, start in enumerate(split_indices):
        end = split_indices[idx + 1] if idx + 1 < total_parts else total_pages
        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])
        out = _output_path(output_dir, stem, idx + 1, total_parts)
        _save_writer(writer, out)

    return total_parts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split a PDF into multiple output files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Split every 10 pages
  python pdf_splitter.py input.pdf chunks --chunk-size 10

  # Extract specific page ranges (1-indexed)
  python pdf_splitter.py input.pdf ranges --ranges "1-5,6-12,20-30"

  # One file per page
  python pdf_splitter.py input.pdf pages
        """,
    )

    parser.add_argument("input", help="Path to the source PDF file.")
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory (default: same folder as input, in a sub-folder named after the PDF).",
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    # -- chunks mode --
    chunks_p = subparsers.add_parser("chunks", help="Split every N pages.")
    chunks_p.add_argument(
        "-n", "--chunk-size",
        type=int,
        default=10,
        metavar="N",
        help="Number of pages per output file (default: 10).",
    )

    # -- ranges mode --
    ranges_p = subparsers.add_parser("ranges", help="Split by explicit page ranges.")
    ranges_p.add_argument(
        "-r", "--ranges",
        required=True,
        metavar="RANGES",
        help='Comma-separated 1-indexed ranges, e.g. "1-5,6-12,20-30".',
    )

    # -- pages mode --
    subparsers.add_parser("pages", help="Split every page into its own file.")

    # -- letterhead mode --
    lh_p = subparsers.add_parser(
        "letterhead",
        help="Split on pages that contain an image (logo) and a marker text.",
    )
    lh_p.add_argument(
        "-m",
        "--marker",
        default="VENUE RENTAL AGREEMENT",
        metavar="TEXT",
        help='Text that must also appear on a logo page to trigger a split (default: "VENUE RENTAL AGREEMENT").',
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"Error: file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if input_path.suffix.lower() != ".pdf":
        print(f"Error: input file must be a PDF: {input_path}", file=sys.stderr)
        sys.exit(1)

    stem = input_path.stem
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else input_path.parent / stem
    )

    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    print(f"Input : {input_path} ({total_pages} pages)")
    print(f"Output: {output_dir}")
    print()

    if args.mode == "chunks":
        count = split_by_chunks(reader, args.chunk_size, output_dir, stem)
    elif args.mode == "ranges":
        count = split_by_ranges(reader, args.ranges, output_dir, stem)
    elif args.mode == "pages":
        count = split_into_pages(reader, output_dir, stem)
    elif args.mode == "letterhead":
        count = split_by_letterhead(reader, output_dir, stem, args.marker)
    else:
        parser.print_help()
        sys.exit(1)

    print(f"\nDone — {count} file(s) written to {output_dir}")


if __name__ == "__main__":
    main()
