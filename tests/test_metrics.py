"""Invariant 2: acceptance metrics are read in space; conducted ones are
labelled diagnostic."""
import numpy as np

from arraytx.metrics import (aclr1_vs_direction, conducted_metrics, ota_metrics,
                             power_vs_direction_db)
from arraytx.report import DISCLAIMER, engine_line, table


def test_domains_are_labelled(fr2_sim):
    r = fr2_sim.run(0.0, "none")
    assert r.beam.domain == "ota" and r.beam.where.startswith("beam")
    assert r.sidelobe is not None and r.sidelobe.domain == "ota"
    assert all(c.domain == "conducted" and "diagnostic" in c.where for c in r.conducted)
    assert conducted_metrics.__name__.startswith("conducted_")
    assert r.beam.sem and r.beam.sem["spec_source"] == "stylized"
    row = r.beam.row()
    assert {"domain", "where", "evm_db", "evm_pct", "aclr1_dbc", "aclr2_dbc", "sem_margin_db"} <= set(row)


def test_single_element_broadside_ota_equals_conducted(anchor_sim):
    """One element at broadside: the far field IS the conducted output, so the
    OTA and the diagnostic numbers coincide bit for bit."""
    r = anchor_sim.run(0.0, "none")
    assert np.array_equal(r.far["beam"][1], r.ys[0])
    assert r.beam.evm_db == r.conducted[0].evm_db
    assert r.beam.aclr_db == r.conducted[0].aclr_db
    assert r.sidelobe is None


def test_ota_metrics_reject_misaligned_shapes(fr2_sim):
    wf = fr2_sim.wf
    try:
        ota_metrics(wf.x[:-1], wf, 0.0, "beam")
    except ValueError:
        pass
    else:
        raise AssertionError("shape mismatch must raise")


def test_aclr_vs_direction_curve(fr2_sim):
    r = fr2_sim.run(0.0, "none")
    thetas = np.array([-60.0, -30.0, 0.0, 30.0, 60.0])
    e = fr2_sim.far_field_many(r.rs, thetas)
    a = aclr1_vs_direction(e, fr2_sim.wf, thetas)
    p = power_vs_direction_db(e)
    assert a.shape == (5,) and np.all(np.isfinite(a))
    assert p[2] == max(p)                               # the beam is at 0
    # the beam-direction value equals the single-direction metric
    assert abs(a[2] - r.beam.aclr1_db) < 1e-9


def test_engine_line_and_table():
    s = engine_line(["dtc_openloop"], "polar")
    assert "dtc_openloop" in s and DISCLAIMER in s
    assert DISCLAIMER not in engine_line(["event"], "polar")
    t = table([{"a": 1.23456, "b": "x"}, {"a": 2.0, "b": "yy"}])
    assert "1.23" in t and "yy" in t
