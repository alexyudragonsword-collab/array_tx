"""Invariant 6: the fingerprint tool records and compares bit for bit."""
import json
import subprocess
import sys

TOOL = "tools/fingerprint.py"


def test_record_twice_is_bit_identical(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for p in (a, b):
        r = subprocess.run([sys.executable, TOOL, "record", str(p)], capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stderr[-2000:]
    da = json.loads(a.read_text())
    assert not any(isinstance(v, dict) and "error" in v for v in da.values()), "a scenario raised"
    assert len(da) > 20
    r = subprocess.run([sys.executable, TOOL, "compare", str(a), str(b)], capture_output=True, text=True)
    assert r.returncode == 0 and "bit-identical" in r.stdout


def test_compare_reports_a_difference(tmp_path):
    a = tmp_path / "a.json"
    subprocess.run([sys.executable, TOOL, "record", str(a)], check=True, capture_output=True, timeout=900)
    d = json.loads(a.read_text())
    d["anchor.0.none"]["far_beam"] = "0000000000000000"
    b = tmp_path / "b.json"
    b.write_text(json.dumps(d))
    r = subprocess.run([sys.executable, TOOL, "compare", str(a), str(b)], capture_output=True, text=True)
    assert r.returncode == 1 and "DIFF anchor.0.none.far_beam" in r.stdout
