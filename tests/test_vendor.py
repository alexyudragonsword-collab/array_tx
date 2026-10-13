"""Structural vendor checks that need no sibling checkout (the drift check
itself runs in CI with the siblings)."""
import json
import re
from pathlib import Path

VENDOR = Path("src/arraytx/vendor")
HEADER = re.compile(r"^# (Vendored|Extracted) from (polar_tx|PA_DPD|pll_simulator)@[0-9a-f]{7,40}: \S+")


def test_every_vendored_file_has_a_header():
    files = [f for f in VENDOR.rglob("*.py") if f.name != "__init__.py"]
    assert len(files) > 80
    for f in files:
        first = f.read_text().splitlines()[0]
        assert HEADER.match(first), f


def test_manifest_entries_have_files_and_hashes():
    m = json.loads(Path("tools/vendor_manifest.json").read_text())
    assert len(m["files"]) == 3
    for rel, e in m["files"].items():
        assert (VENDOR / rel).exists(), rel
        assert re.fullmatch(r"[0-9a-f]{64}", e["body_sha256"])
        assert e["mode"] in ("extended", "extracted") and e["reason"]


def test_no_gui_surface_vendored_and_clock_profile_present():
    assert not (VENDOR / "polartx" / "guiqt").exists()
    assert not (VENDOR / "polartx" / "guiutil.py").exists()
    cp = VENDOR / "polartx" / "vendor" / "pllsim" / "export" / "clock_profile.py"
    assert cp.exists() and "pll_simulator@00e48a2" in cp.read_text().splitlines()[0]


def test_outside_code_imports_only_through_arraytx_vendor():
    for f in Path("src/arraytx").glob("*.py"):
        t = f.read_text()
        assert "from polartx" not in t and "import polartx" not in t, f
        assert "from padpd" not in t and "from pllsim" not in t, f
