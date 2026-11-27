import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT))

import cv19_classify_pages as classify_pages
from cv19_config import EXPECTED_PDF_PAGES


FIELDS = (
    "book",
    "pdf_page",
    "image_name",
    "classification",
    "needs_review",
    "notes",
)
PART_ONE = next(
    Path(pdf_name).stem
    for pdf_name, page_count in EXPECTED_PDF_PAGES.items()
    if page_count == 451
)


def write_inventory(path, page_400_review="yes", include_review_column=True):
    fields = list(FIELDS)
    if not include_review_column:
        fields.remove("needs_review")

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for pdf_name, page_count in EXPECTED_PDF_PAGES.items():
            book = Path(pdf_name).stem
            for page_number in range(1, page_count + 1):
                classification = ""
                needs_review = "no"
                if book == PART_ONE and page_number == 399:
                    classification = "ch"
                elif book == PART_ONE and page_number == 400:
                    classification = "vi"
                    needs_review = page_400_review
                row = {
                    "book": book,
                    "pdf_page": page_number,
                    "image_name": f"{book}.{page_number:03}.jpg",
                    "classification": classification,
                    "needs_review": needs_review,
                    "notes": "",
                }
                writer.writerow({key: row[key] for key in fields})


class ReadPlanReviewTests(unittest.TestCase):
    def test_needs_review_yes_is_excluded_even_with_category(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sheet = Path(temp_dir) / "inventory.csv"
            write_inventory(sheet, page_400_review=" YES ")

            plan = classify_pages.read_plan(sheet)
            page_399 = next(
                page for page in plan
                if page["book_name"] == PART_ONE and page["page"] == 399
            )
            page_400 = next(
                page for page in plan
                if page["book_name"] == PART_ONE and page["page"] == 400
            )

            self.assertEqual(page_399["categories"], ["ch"])
            self.assertFalse(page_399["needs_review"])
            self.assertEqual(page_400["categories"], [])
            self.assertTrue(page_400["needs_review"])

    def test_needs_review_column_is_required(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sheet = Path(temp_dir) / "inventory.csv"
            write_inventory(sheet, include_review_column=False)

            with self.assertRaisesRegex(ValueError, "needs_review"):
                classify_pages.read_plan(sheet)

    def test_invalid_needs_review_value_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sheet = Path(temp_dir) / "inventory.csv"
            write_inventory(sheet, page_400_review="pending")

            with self.assertRaisesRegex(ValueError, "needs_review must be"):
                classify_pages.read_plan(sheet)


class ApplyPlanReviewTests(unittest.TestCase):
    def test_reviewed_page_is_removed_from_derived_state_but_inventory_stays(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "project"
            sheet = Path(temp_dir) / "inventory.csv"
            write_inventory(sheet)
            original_sheet = sheet.read_bytes()

            images = root / "images" / PART_ONE
            image_399 = images / f"{PART_ONE}.399.jpg"
            image_400 = images / f"{PART_ONE}.400.jpg"
            images.mkdir(parents=True)
            image_399.write_bytes(b"confirmed page")
            image_400.write_bytes(b"review page")

            work_399 = root / "work" / PART_ONE / "ch" / image_399.name
            work_400 = root / "work" / PART_ONE / "vi" / image_400.name
            work_399.parent.mkdir(parents=True)
            work_400.parent.mkdir(parents=True)
            work_400.write_bytes(image_400.read_bytes())

            applied_state = root / "page_classification_applied.json"
            applied_state.write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "pdf_name": f"{PART_ONE}.pdf",
                                "page": 399,
                                "categories": ["ch"],
                            },
                            {
                                "pdf_name": f"{PART_ONE}.pdf",
                                "page": 400,
                                "categories": ["vi"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(classify_pages, "WORK_ROOT", root),
                patch.object(classify_pages, "APPLIED_STATE_PATH", applied_state),
            ):
                classify_pages.apply_plan(classify_pages.read_plan(sheet))

            state = json.loads(applied_state.read_text(encoding="utf-8"))
            self.assertEqual(
                state["pages"],
                [
                    {
                        "pdf_name": f"{PART_ONE}.pdf",
                        "page": 399,
                        "categories": ["ch"],
                    }
                ],
            )
            self.assertTrue((root / "work" / PART_ONE / "ch" / image_399.name).is_file())
            self.assertFalse(work_400.exists())
            self.assertEqual(sheet.read_bytes(), original_sheet)
            with sheet.open("r", encoding="utf-8-sig", newline="") as file:
                page_400 = next(
                    row for row in csv.DictReader(file)
                    if row["book"] == PART_ONE and row["pdf_page"] == "400"
                )
            self.assertEqual(page_400["classification"], "vi")
            self.assertEqual(page_400["needs_review"], "yes")


if __name__ == "__main__":
    unittest.main()
