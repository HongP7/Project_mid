import argparse
import csv
import filecmp
import json
import pathlib
import shutil
import sys

from cv19_config import CATEGORIES, EXPECTED_PDF_PAGES, WORK_ROOT


CLASSIFICATION_PATH = WORK_ROOT / "page_inventory.csv"
APPLIED_STATE_PATH = WORK_ROOT / "page_classification_applied.json"


def parse_categories(value, row_number):
    categories = [part.strip() for part in value.split(";") if part.strip()]
    if categories == ["review"]:
        return []
    if len(categories) != len(set(categories)):
        raise ValueError(f"Row {row_number}: category contains duplicates")
    invalid = sorted(set(categories) - CATEGORIES)
    if invalid:
        raise ValueError(
            f"Row {row_number}: invalid category(ies): {', '.join(invalid)}"
        )
    if categories == ["both"]:
        return ["ch", "vi"]
    if "review" in categories:
        raise ValueError(
            f"Row {row_number}: 'review' cannot be combined with a page category"
        )
    if len(categories) > 1 and set(categories) != {"ch", "vi"}:
        raise ValueError(
            f"Row {row_number}: only 'both' or the bilingual T2b value 'ch;vi' may select both"
        )
    return categories


def read_plan(path):
    if not path.is_file():
        raise FileNotFoundError(f"Classification sheet not found: {path}")

    planned_pages = []
    seen_pages = set()
    errors = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required_fields = {
            "book",
            "pdf_page",
            "image_name",
            "classification",
            "needs_review",
            "notes",
        }
        if not required_fields.issubset(reader.fieldnames or []):
            raise ValueError(
                f"{path} must have these columns: {', '.join(sorted(required_fields))}"
            )

        for row_number, row in enumerate(reader, start=2):
            book_name = (row.get("book") or "").strip()
            page_text = (row.get("pdf_page") or "").strip()
            filename = (row.get("image_name") or "").strip()
            category_text = (row.get("classification") or "").strip()
            review_text = (row.get("needs_review") or "").strip().lower()
            if not book_name or not page_text or not filename:
                errors.append(f"row {row_number}: book, pdf_page, or image_name is empty")
                continue
            if review_text not in {"yes", "no"}:
                errors.append(
                    f"row {row_number}: needs_review must be 'yes' or 'no'"
                )
                continue
            try:
                page_number = int(page_text)
                categories = (
                    parse_categories(category_text, row_number)
                    if category_text
                    else []
                )
            except ValueError as error:
                errors.append(str(error))
                continue
            if page_number < 1:
                errors.append(f"row {row_number}: page must be a positive integer")
                continue

            pdf_name = f"{book_name}.pdf"
            if (
                pathlib.Path(book_name).name != book_name
                or pdf_name not in EXPECTED_PDF_PAGES
            ):
                errors.append(f"row {row_number}: unknown book name {book_name}")
                continue
            if page_number > EXPECTED_PDF_PAGES[pdf_name]:
                errors.append(f"row {row_number}: page is outside {pdf_name}")
                continue

            expected_filename = f"{book_name}.{page_number:03}.jpg"
            if pathlib.Path(filename).name != filename:
                errors.append(
                    f"row {row_number}: image_name must be a filename, not a path"
                )
                continue
            if filename != expected_filename:
                errors.append(
                    f"row {row_number}: expected filename {expected_filename}, got {filename}"
                )
                continue

            page_key = (pdf_name, page_number)
            if page_key in seen_pages:
                errors.append(
                    f"row {row_number}: duplicate page {pdf_name}, page {page_number}"
                )
                continue
            seen_pages.add(page_key)
            needs_review = review_text == "yes"
            planned_pages.append(
                {
                    "pdf_name": pdf_name,
                    "page": page_number,
                    "book_name": book_name,
                    "filename": filename,
                    "categories": [] if needs_review else categories,
                    "needs_review": needs_review,
                }
            )

    if errors:
        raise ValueError("Invalid classification sheet:\n- " + "\n- ".join(errors))
    expected_pages = {
        (pdf_name, page_number)
        for pdf_name, page_count in EXPECTED_PDF_PAGES.items()
        for page_number in range(1, page_count + 1)
    }
    missing_pages = expected_pages - seen_pages
    if missing_pages:
        raise ValueError(
            f"Classification sheet is missing {len(missing_pages)} page row(s); "
            "restore every row from page_inventory.csv before applying it."
        )
    if not planned_pages:
        raise ValueError(f"No pages found in classification sheet: {path}")
    return planned_pages


def load_applied_state():
    if not APPLIED_STATE_PATH.is_file():
        return []

    state = json.loads(APPLIED_STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise ValueError(f"Invalid applied classification record: {APPLIED_STATE_PATH}")
    pages = state.get("pages")
    if not isinstance(pages, list):
        raise ValueError(f"Invalid applied classification record: {APPLIED_STATE_PATH}")

    validated = []
    for row_number, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise ValueError(f"Invalid page entry {row_number} in {APPLIED_STATE_PATH}")
        pdf_name = page.get("pdf_name")
        page_number = page.get("page")
        categories = page.get("categories")
        if (
            not isinstance(pdf_name, str)
            or pathlib.Path(pdf_name).name != pdf_name
            or pdf_name not in EXPECTED_PDF_PAGES
            or not isinstance(page_number, int)
            or page_number < 1
            or page_number > EXPECTED_PDF_PAGES.get(pdf_name, 0)
            or not isinstance(categories, list)
            or not categories
        ):
            raise ValueError(f"Invalid page entry {row_number} in {APPLIED_STATE_PATH}")
        try:
            checked_categories = parse_categories(";".join(categories), row_number)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid page entry {row_number} in {APPLIED_STATE_PATH}: {error}"
            ) from error
        validated.append(
            {
                "pdf_name": pdf_name,
                "page": page_number,
                "filename": f"{pathlib.Path(pdf_name).stem}.{page_number:03}.jpg",
                "book_name": pathlib.Path(pdf_name).stem,
                "categories": checked_categories,
            }
        )
    return validated


def apply_plan(planned_pages):
    destinations = []
    expected_destinations = set()
    classified_count = 0
    skipped_review_count = sum(1 for page in planned_pages if page["needs_review"])
    unclassified_count = sum(
        1
        for page in planned_pages
        if not page["categories"] and not page["needs_review"]
    )
    for page in planned_pages:
        if not page["categories"]:
            continue
        classified_count += 1
        source = WORK_ROOT / "images" / page["book_name"] / page["filename"]
        if not source.is_file():
            raise FileNotFoundError(f"Rendered page image not found: {source}")
        for category in page["categories"]:
            destination = (
                WORK_ROOT
                / "work"
                / page["book_name"]
                / category
                / page["filename"]
            )
            if destination.exists() and not filecmp.cmp(source, destination, shallow=False):
                raise FileExistsError(
                    f"Refusing to overwrite a different file: {destination}"
                )
            destinations.append((source, destination))
            expected_destinations.add(destination)

    previous_pages = load_applied_state()
    stale_destinations = []
    for page in previous_pages:
        source = WORK_ROOT / "images" / page["book_name"] / page["filename"]
        if not source.is_file():
            raise FileNotFoundError(
                f"Cannot safely update classifications; rendered source is missing: {source}"
            )
        for category in page["categories"]:
            destination = (
                WORK_ROOT
                / "work"
                / page["book_name"]
                / category
                / page["filename"]
            )
            if destination not in expected_destinations and destination.exists():
                if not filecmp.cmp(source, destination, shallow=False):
                    raise FileExistsError(
                        "Refusing to remove a changed file from an earlier "
                        f"classification: {destination}"
                    )
                stale_destinations.append(destination)

    copied = 0
    for source, destination in destinations:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
            copied += 1

    for destination in stale_destinations:
        destination.unlink()

    state = {
        "pages": [
            {
                "pdf_name": page["pdf_name"],
                "page": page["page"],
                "categories": page["categories"],
            }
            for page in planned_pages
            if page["categories"]
        ]
    }
    temporary_state = APPLIED_STATE_PATH.with_suffix(".json.tmp")
    temporary_state.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_state.replace(APPLIED_STATE_PATH)

    print(
        f"Applied {classified_count} classified page(s); "
        f"left {unclassified_count} unclassified page(s); "
        f"skipped {skipped_review_count} needs_review=yes page(s); "
        f"copied {copied} image(s) and removed {len(stale_destinations)} stale image(s)"
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Copy rendered pages into their manually selected categories."
    )
    parser.add_argument(
        "--sheet",
        type=pathlib.Path,
        default=CLASSIFICATION_PATH,
        help="Page inventory CSV (defaults to cv19_project/page_inventory.csv).",
    )
    args = parser.parse_args()
    apply_plan(read_plan(args.sheet))


if __name__ == "__main__":
    main()
