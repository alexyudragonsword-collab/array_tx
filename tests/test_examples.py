"""Every example runs at smoke size and writes its plot."""
import glob
import os
import subprocess
import sys

import pytest

EXAMPLES = sorted(glob.glob("examples/ex*.py"))


def test_the_examples_are_numbered_without_gaps():
    assert [os.path.basename(p)[:4] for p in EXAMPLES] == [f"ex{i:02d}" for i in range(len(EXAMPLES))]
    assert len(EXAMPLES) >= 6


@pytest.mark.parametrize("path", EXAMPLES, ids=[os.path.basename(p) for p in EXAMPLES])
def test_example_runs_in_smoke_mode(path):
    env = dict(os.environ, ARRAYTX_SMOKE="1", MPLBACKEND="Agg")
    r = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=600, env=env)
    assert r.returncode == 0, r.stdout[-2000:] + "\n" + r.stderr[-2000:]
    assert "engine:" in r.stdout and "线性化引擎" in r.stdout, "every example prints its engine and the disclaimer"
    assert "plots ->" in r.stdout
