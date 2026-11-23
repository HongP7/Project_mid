import csv
import json
import pathlib
import sys

import pymupdf

from cv19_config import ASSIGNED_ROOT, CATEGORIES, EXPECTED_PDF_PAGES, WORK_ROOT

SUBDIRECTORIES = (
    "ch",
    "vi",
    "intro",
    "ref",
    "toc",
    "blank",
    "misc",
    "missing/ch",
    "missing/vi",
)


def inspect_pdf(path):
    with pymupdf.open(path) as doc:
        text_chars = sum(len(page.get_text("text")) for page in doc)
        page_sizes = sorted(
            {(round(page.rect.width, 2), round(page.rect.height, 2)) for page in doc}
        )
        return {
            "file_name": path.name,
            "source_path": str(path),
            "pages": len(doc),
            "extracted_text_chars": text_chars,
            "has_text_layer": text_chars > 0,
            "page_sizes_pt": [
                {"width": width, "height": height} for width, height in page_sizes
            ],
        }


def read_existing_scope_review(manifest_path):
    if not manifest_path.is_file():
        review = {
            "status": "pending",
            "counterpart_files": [],
            "checked_by": "",
            "checked_at": "",
            "notes": (
                "Compare both versions and confirm they cover the same pages before OCR."
            ),
        }
    else:
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        review = previous.get("scope_review")
        if not isinstance(review, dict):
            raise ValueError(f"Invalid scope_review in {manifest_path}")

    if review.get("status", "pending") not in {"pending", "verified", "not_matching"}:
        raise ValueError(
            f"scope_review.status in {manifest_path} must be pending, verified, or not_matching"
        )
    if review.get("status") == "verified":
        if not review.get("counterpart_files"):
            raise ValueError(
                "List the compared counterpart_files before marking scope as "
                f"verified in {manifest_path}"
            )
        if not review.get("checked_by") or not review.get("checked_at"):
            raise ValueError(
                "Record checked_by and checked_at before marking scope as "
                f"verified in {manifest_path}"
            )
    return review


def load_existing_classifications(path):
    if not path.is_file():
        return {}

    classifications = {}
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            book = row.get("book") or pathlib.Path(row.get("pdf_name", "")).stem
            page_number = row.get("pdf_page") or row.get("page", "")
            key = (book, str(page_number))
            classifications[key] = {
                "classification": row.get("classification") or row.get("category", ""),
                "has_hannom": row.get("has_hannom", ""),
                "has_vietnamese": row.get("has_vietnamese", ""),
                "needs_review": row.get("needs_review", ""),
                "notes": row.get("notes", ""),
            }
    return classifications


def write_classification_template(path, pdfs, previous):
    fieldnames = (
        "book",
        "pdf_page",
        "image_name",
        "classification",
        "has_hannom",
        "has_vietnamese",
        "needs_review",
        "notes",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for pdf in pdfs:
            for page_number in range(1, pdf["pages"] + 1):
                book_name = pathlib.Path(pdf["file_name"]).stem
                key = (book_name, str(page_number))
                saved = previous.get(key, {})
                classification = saved.get("classification", "")
                if classification not in CATEGORIES:
                    classification = ""
                writer.writerow(
                    {
                        "book": book_name,
                        "pdf_page": page_number,
                        "image_name": f"{book_name}.{page_number:03}.jpg",
                        "classification": classification,
                        "has_hannom": saved.get("has_hannom", ""),
                        "has_vietnamese": saved.get("has_vietnamese", ""),
                        "needs_review": saved.get("needs_review") or "yes",
                        "notes": saved.get("notes", ""),
                    }
                )


def prepare():
    sys.stdout.reconfigure(encoding="utf-8")
    if not ASSIGNED_ROOT.is_dir():
        raise FileNotFoundError(f"Assigned PDF folder not found: {ASSIGNED_ROOT}")

    source_pdfs = sorted(
        ASSIGNED_ROOT.glob("*.pdf"), key=lambda path: path.name.casefold()
    )
    if not source_pdfs:
        raise FileNotFoundError(f"No assigned PDF files found in {ASSIGNED_ROOT}")
    actual_names = {path.name for path in source_pdfs}
    expected_names = set(EXPECTED_PDF_PAGES)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ValueError(
            f"Assigned PDF scope mismatch. Missing: {missing}; unexpected: {unexpected}"
        )

    pdfs = [inspect_pdf(path) for path in source_pdfs]
    for pdf in pdfs:
        expected_pages = EXPECTED_PDF_PAGES[pdf["file_name"]]
        if pdf["pages"] != expected_pages:
            raise ValueError(
                f'{pdf["file_name"]} has {pdf["pages"]} pages; '
                f"expected {expected_pages} for the assigned scope"
            )
        book_root = WORK_ROOT / "work" / pathlib.Path(pdf["file_name"]).stem
        for relative in SUBDIRECTORIES:
            (book_root / relative).mkdir(parents=True, exist_ok=True)
        (WORK_ROOT / "out" / pathlib.Path(pdf["file_name"]).stem).mkdir(
            parents=True, exist_ok=True
        )

    (WORK_ROOT / "images").mkdir(parents=True, exist_ok=True)
    (WORK_ROOT / "reports").mkdir(parents=True, exist_ok=True)

    manifest_path = WORK_ROOT / "project_manifest.json"
    scope_review = read_existing_scope_review(manifest_path)
    manifest = {
        "project": "Building a Chinese-Vietnamese Parallel Corpus on Daily Life",
        "project_code": "cv19",
        "student": {"name": "Le Minh Nhat", "student_id": "22127308"},
        "document_type": "T1 (from assigned filenames)",
        "source_format": (
            "PDF scan"
            if all(pdf["extracted_text_chars"] == 0 for pdf in pdfs)
            else "PDF with extracted text"
        ),
        "scope": {
            "parts": [pdf["file_name"] for pdf in pdfs],
            "counterpart_scope_verified": scope_review.get("status") == "verified",
            "instruction": "Compare the two versions and confirm matching scope before OCR.",
        },
        "scope_review": scope_review,
        "pdfs": pdfs,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    classification_path = WORK_ROOT / "page_inventory.csv"
    previous = load_existing_classifications(classification_path)
    write_classification_template(classification_path, pdfs, previous)

    print(f"Prepared {len(pdfs)} PDFs in {WORK_ROOT}")
    print(f"Scope record: {manifest_path}")
    print(f"Page inventory and classification sheet: {classification_path}")
    for pdf in pdfs:
        print(f'  {pdf["file_name"]}: {pdf["pages"]} pages')


if __name__ == "__main__":
    prepare()
