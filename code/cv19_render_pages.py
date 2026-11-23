import argparse
import math
import pathlib
import sys

import pymupdf

from cv19_config import ASSIGNED_ROOT, EXPECTED_PDF_PAGES, WORK_ROOT
DEFAULT_DPI = 300


def page_render_dpi(page):
    source_dpis = []
    for image in page.get_image_info():
        for key in ("xres", "yres"):
            resolution = image.get(key)
            if isinstance(resolution, (int, float)) and math.isfinite(resolution):
                if resolution > 0:
                    source_dpis.append(resolution)
    return max(DEFAULT_DPI, math.ceil(max(source_dpis, default=DEFAULT_DPI)))


def parse_rotation(value):
    try:
        page_text, rotation_text = value.split("=", 1)
        page_number = int(page_text)
        degrees = int(rotation_text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "rotation must use PAGE=90, PAGE=180, or PAGE=270"
        ) from error
    if page_number < 1 or degrees not in {90, 180, 270}:
        raise argparse.ArgumentTypeError(
            "rotation must use a positive page number and 90, 180, or 270 degrees"
        )
    return page_number, degrees


def render_pdf(
    pdf_path, output_root, dpi=None, page_numbers=None, rotations=None, overwrite=False
):
    output_dir = output_root / "images" / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    rotations = rotations or {}

    with pymupdf.open(pdf_path) as doc:
        expected_pages = EXPECTED_PDF_PAGES[pdf_path.name]
        if len(doc) != expected_pages:
            raise ValueError(
                f"{pdf_path.name} has {len(doc)} pages; expected {expected_pages}"
            )
        selected = page_numbers if page_numbers is not None else range(1, len(doc) + 1)
        invalid_pages = [number for number in selected if number < 1 or number > len(doc)]
        invalid_rotations = [
            number for number in rotations if number < 1 or number > len(doc)
        ]
        if invalid_pages:
            raise ValueError(
                f"Page number(s) out of range for {pdf_path.name}: {invalid_pages}"
            )
        if invalid_rotations:
            raise ValueError(
                f"Rotation page number(s) out of range for {pdf_path.name}: "
                f"{invalid_rotations}"
            )

        for page_number in selected:
            output_path = output_dir / f"{pdf_path.stem}.{page_number:03}.jpg"
            if output_path.is_file() and not overwrite:
                print(f"Skipped existing image: {output_path.name}")
                continue

            page = doc[page_number - 1]
            render_dpi = dpi if dpi is not None else page_render_dpi(page)
            rotation = rotations.get(page_number, 0)
            if rotation:
                scale = render_dpi / 72
                matrix = pymupdf.Matrix(scale, scale).prerotate(rotation)
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            else:
                pixmap = page.get_pixmap(dpi=render_dpi, alpha=False)
            pixmap.save(output_path)
            print(
                f"Rendered {pdf_path.name} page {page_number} at {render_dpi} DPI"
                + (f", rotated {rotation} degrees" if rotation else "")
            )

    print(f"Images saved to {output_dir}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Render assigned PDF pages as high-resolution JPG files."
    )
    parser.add_argument(
        "pdf_name",
        nargs="?",
        help="PDF filename in the assigned folder; omit to render all PDFs.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        help=(
            "Force a render resolution. By default, use the highest embedded "
            "image DPI (minimum 300)."
        ),
    )
    parser.add_argument(
        "--pages",
        nargs="+",
        type=int,
        help="1-based page numbers to render; by default render every page.",
    )
    parser.add_argument(
        "--rotate",
        action="append",
        type=parse_rotation,
        metavar="PAGE=DEGREES",
        help="Rotate a 1-based page by 90, 180, or 270 degrees; repeat as needed.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace JPG files that already exist.",
    )
    args = parser.parse_args()

    if args.dpi is not None and args.dpi <= 0:
        parser.error("--dpi must be a positive integer")
    if args.pages and len(args.pages) != len(set(args.pages)):
        parser.error("--pages must not contain duplicates")
    rotations = dict(args.rotate or [])
    if len(rotations) != len(args.rotate or []):
        parser.error("--rotate must not repeat a page number")

    if args.pdf_name:
        if pathlib.Path(args.pdf_name).name != args.pdf_name:
            parser.error("pdf_name must be a filename in the assigned folder")
        if args.pdf_name not in EXPECTED_PDF_PAGES:
            parser.error(f"not an assigned PDF: {args.pdf_name}")
        pdf_names = [args.pdf_name]
    else:
        actual_names = {path.name for path in ASSIGNED_ROOT.glob("*.pdf")}
        expected_names = set(EXPECTED_PDF_PAGES)
        if actual_names != expected_names:
            missing = sorted(expected_names - actual_names)
            unexpected = sorted(actual_names - expected_names)
            raise ValueError(
                f"Assigned PDF scope mismatch. Missing: {missing}; unexpected: {unexpected}"
            )
        pdf_names = sorted(expected_names, key=str.casefold)
        if not pdf_names:
            raise FileNotFoundError(f"No assigned PDF files found in {ASSIGNED_ROOT}")

    for pdf_name in pdf_names:
        pdf_path = ASSIGNED_ROOT / pdf_name
        if not pdf_path.is_file():
            raise FileNotFoundError(f"Assigned PDF not found: {pdf_path}")
        render_pdf(
            pdf_path,
            WORK_ROOT,
            args.dpi,
            args.pages,
            rotations,
            args.overwrite,
        )


if __name__ == "__main__":
    main()
