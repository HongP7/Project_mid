# CV19 project preparation

The scripts use paths relative to this project folder, so they do not depend on
the Windows account or the folder from which a command is run. Assigned PDFs
are read from `CV19-Lê Minh Nhật-22127308\`; generated work files go to
`cv19_project\`.

## Local data paths

When the assigned PDFs, samples, dictionary, or alignment tool archive live
outside the repository, create `cv19_paths.local.json` in the project root.
This machine-specific file is ignored by Git. Paths must be absolute; omitted
keys keep the repository-relative defaults. `WORK_ROOT` remains
`cv19_project\`, so changing data locations does not move project state.

```json
{
  "assigned_root": "C:\\path\\to\\CV19-Lê Minh Nhật-22127308",
  "samples_root": "C:\\path\\to\\samples",
  "dictionaries_root": "C:\\path\\to\\dictionaries",
  "alignment_tool_archive": "C:\\path\\to\\tools\\ocr-nom-align-main.zip"
}
```

## Requirements

- Python 3.10 or later
- PyMuPDF

From the project root in PowerShell:

```powershell
py -m pip install -r code\requirements.txt
py code\cv19_prepare_project.py
```

Preparation checks the three assigned parts (451, 485, and 548 pages), records
PDF names, page counts, page sizes, and available text in
`cv19_project\project_manifest.json`, and creates the category folders and
`cv19_project\page_inventory.csv`.

The assignment filenames identify three T1 parts, but do not establish that
the two language versions have matching page scope. Compare the versions and
record `status`, `counterpart_files`, `checked_by`, `checked_at`, and `notes`
in `scope_review` in the manifest before starting OCR. Preparation
intentionally leaves that review pending; set `status` to `verified` only
after confirming the scopes match.

## Work division

Keep the four responsibilities separate: (1) split and name PDF pages, (2)
OCR and correct Hán-Nôm labels, (3) OCR and correct Quốc ngữ labels, and (4)
align, validate, package, and report. Start with one sample chapter or page
range to agree on the workflow.

## Render and classify pages (through step 5)

Render all assigned PDFs as JPG files. By default, the renderer uses the
highest embedded image DPI on each page, with a 300 DPI minimum. For
image-only pages it falls back to 300 DPI. Use `--dpi` to force a render DPI,
or `--pages` to render selected 1-based page numbers.
For pages needing orientation correction, add one or more
`--rotate PAGE=DEGREES` options (`90`, `180`, or `270`).

```powershell
py code\cv19_render_pages.py
# Example: render selected pages of one PDF at an explicit resolution
py code\cv19_render_pages.py "T1_Tứ Nguyên Yếu Lý (Phần 1).pdf" --dpi 400 --pages 1 2
py code\cv19_render_pages.py "T1_Tứ Nguyên Yếu Lý (Phần 1).pdf" --pages 7 --rotate 7=90
```

Rendered images are kept in `cv19_project\images\<PDF name>\`. Review each
page and fill the `classification` column in `page_inventory.csv` with one of:
`ch`, `vi`, `intro`, `ref`, `toc`, `blank`, `misc`, `missing/ch`, or
`missing/vi`. For a bilingual T2b page, enter `both` (or `ch;vi`) so the image
is copied to both categories. Do not assign categories based only on page
numbers. Leave uncertain classifications blank (or enter `review`) until
reviewed. The classifier applies only rows with a category, so you can work
through verified pages in batches; it still checks that the inventory has a
row for every page. The sheet must include `needs_review` with an explicit
`yes` or `no` value. Rows marked `yes` are never applied, even when their
`classification` cell is populated. If such a row was applied previously, the
next reconciliation removes its derived category copy and applied-state entry;
the inventory row itself remains unchanged for review.

Apply the completed sheet:

```powershell
py code\cv19_classify_pages.py
```

The script copies (does not move) rendered JPGs into
`cv19_project\work\<PDF name>\<category>\` and refuses incomplete sheets,
unknown categories, missing images, and conflicting existing files. Bounding
boxes and OCR labels are not created at this stage.
