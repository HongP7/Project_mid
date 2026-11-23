import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
ASSIGNED_ROOT = PROJECT_ROOT / "CV19-Lê Minh Nhật-22127308"
WORK_ROOT = PROJECT_ROOT / "cv19_project"

EXPECTED_PDF_PAGES = {
    "T1_Tứ Nguyên Yếu Lý (Phần 1).pdf": 451,
    "T1_Tứ Nguyên Yếu Lý (Phần 2).pdf": 485,
    "T1_Tứ Nguyên Yếu Lý (Phần 3).pdf": 548,
}

CATEGORIES = {
    "ch",
    "vi",
    "both",
    "intro",
    "ref",
    "toc",
    "blank",
    "misc",
    "missing/ch",
    "missing/vi",
    "review",
}
