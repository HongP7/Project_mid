import json
import pathlib


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
WORK_ROOT = PROJECT_ROOT / "cv19_project"
LOCAL_PATHS_FILE = PROJECT_ROOT / "cv19_paths.local.json"

if LOCAL_PATHS_FILE.is_file():
    local_paths = json.loads(LOCAL_PATHS_FILE.read_text(encoding="utf-8-sig"))
    if not isinstance(local_paths, dict):
        raise ValueError(f"{LOCAL_PATHS_FILE} must contain a JSON object")
else:
    local_paths = {}


def configured_path(name, default):
    value = local_paths.get(name)
    if value is None:
        return default
    if not isinstance(value, str):
        raise TypeError(f"{name} in {LOCAL_PATHS_FILE} must be a string")
    path = pathlib.Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{name} in {LOCAL_PATHS_FILE} must be an absolute path")
    return path


ASSIGNED_ROOT = configured_path(
    "assigned_root",
    PROJECT_ROOT / "CV19-Lê Minh Nhật-22127308",
)
SAMPLES_ROOT = configured_path("samples_root", PROJECT_ROOT / "samples")
DICTIONARIES_ROOT = configured_path("dictionaries_root", PROJECT_ROOT / "dictionaries")
ALIGNMENT_TOOL_ARCHIVE = configured_path(
    "alignment_tool_archive",
    PROJECT_ROOT / "tools" / "ocr-nom-align-main.zip",
)

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
