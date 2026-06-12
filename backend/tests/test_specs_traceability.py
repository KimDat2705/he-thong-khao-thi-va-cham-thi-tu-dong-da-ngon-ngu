"""
Meta-test truy vết 2 chiều giữa catalog spec (specs/specs.json) và bộ test.

Harness Engineering: specs/specs.json là NGUỒN SỰ THẬT DUY NHẤT của mọi bảo chứng
kiến trúc. File này đảm bảo:
- Chiều xuôi: mọi spec verify bằng pytest đều trỏ tới test thực sự tồn tại.
- Chiều ngược: mọi mã spec xuất hiện trong các file test đều có trong catalog
  (không có "spec ma" được test mà không được đặc tả).
"""
import json
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
SPECS_PATH = REPO_ROOT / "specs" / "specs.json"
TESTS_DIR = BACKEND_DIR / "tests"

ID_FORMAT = re.compile(r"^SPEC-[A-Z0-9]+-\d{3}$")
TOKEN_FORMAT = re.compile(r"SPEC[-_]([A-Z0-9]+)[-_](\d{3})")

VALID_VERIFICATION = {"pytest", "load-test", "manual"}
VALID_STATUS = {"active", "gap", "planned"}


def load_catalog() -> dict:
    with open(SPECS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def catalog_ids(catalog: dict) -> set:
    return {spec["id"] for spec in catalog["specs"]}


def spec_test_files():
    """Các file test spec, trừ chính file meta-test này."""
    return [
        p for p in TESTS_DIR.glob("test_specs_*.py")
        if p.name != Path(__file__).name
    ]


def test_SPEC_catalog_schema_valid():
    """Catalog phải là JSON hợp lệ, ID đúng định dạng và duy nhất, enum hợp lệ."""
    catalog = load_catalog()
    assert isinstance(catalog["specs"], list) and len(catalog["specs"]) > 0

    seen_ids = set()
    for spec in catalog["specs"]:
        for field in ("id", "domain", "title", "statement", "acceptance_criteria", "verification", "status", "tests"):
            assert field in spec, f"Spec thiếu trường bắt buộc '{field}': {spec.get('id', '<không id>')}"

        assert ID_FORMAT.match(spec["id"]), f"ID sai định dạng: {spec['id']}"
        assert spec["id"] not in seen_ids, f"ID trùng lặp: {spec['id']}"
        seen_ids.add(spec["id"])

        assert spec["verification"] in VALID_VERIFICATION, f"{spec['id']}: verification không hợp lệ"
        assert spec["status"] in VALID_STATUS, f"{spec['id']}: status không hợp lệ"
        assert isinstance(spec["acceptance_criteria"], list) and len(spec["acceptance_criteria"]) > 0, \
            f"{spec['id']}: acceptance_criteria phải là list không rỗng"


def test_SPEC_catalog_forward_refs():
    """Chiều xuôi: spec pytest nào cũng phải trỏ tới file test và hàm test tồn tại."""
    catalog = load_catalog()
    for spec in catalog["specs"]:
        if spec["verification"] != "pytest":
            continue
        assert len(spec["tests"]) > 0, f"{spec['id']}: verification=pytest nhưng tests[] rỗng"

        for ref in spec["tests"]:
            assert "::" in ref, f"{spec['id']}: tham chiếu test sai định dạng (cần file::hàm): {ref}"
            rel_path, func_name = ref.split("::", 1)
            test_file = BACKEND_DIR / rel_path
            assert test_file.is_file(), f"{spec['id']}: file test không tồn tại: {rel_path}"
            source = test_file.read_text(encoding="utf-8")
            assert f"def {func_name}(" in source, \
                f"{spec['id']}: hàm '{func_name}' không có trong {rel_path}"


def test_SPEC_catalog_reverse_refs():
    """Chiều ngược: mọi token SPEC-XXX-NNN trong các file test phải có trong catalog."""
    ids = catalog_ids(load_catalog())
    for test_file in spec_test_files():
        source = test_file.read_text(encoding="utf-8")
        for match in TOKEN_FORMAT.finditer(source):
            normalized = f"SPEC-{match.group(1)}-{match.group(2)}"
            assert normalized in ids, \
                f"'Spec ma' {normalized} xuất hiện trong {test_file.name} nhưng không có trong specs/specs.json"


def test_SPEC_pytest_specs_tokened():
    """Mỗi spec pytest phải xuất hiện dưới dạng token trong ít nhất 1 file test được tham chiếu."""
    catalog = load_catalog()
    for spec in catalog["specs"]:
        if spec["verification"] != "pytest":
            continue
        token_found = False
        for ref in spec["tests"]:
            rel_path = ref.split("::", 1)[0]
            test_file = BACKEND_DIR / rel_path
            if not test_file.is_file():
                continue
            source = test_file.read_text(encoding="utf-8")
            for match in TOKEN_FORMAT.finditer(source):
                if f"SPEC-{match.group(1)}-{match.group(2)}" == spec["id"]:
                    token_found = True
                    break
            if token_found:
                break
        assert token_found, \
            f"{spec['id']}: không tìm thấy token spec trong bất kỳ file test nào được tham chiếu"
