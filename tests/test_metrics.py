"""Invariant 2: acceptance metrics are read in space; conducted ones are
labelled diagnostic."""
import numpy as np

from arraytx.metrics import (aclr1_vs_direction, conducted_metrics, ota_metrics,
                             power_vs_direction_db)
from arraytx.report import CONVERGED_HOLD, CONVERGED_NOTE, DISCLAIMERS, NOT_EVIDENCE, disclaimer_for, engine_line, table


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
    s = engine_line(["dtc_openloop"], "polar", 4)
    assert "dtc_openloop" in s and "os 4" in s and DISCLAIMERS["dtc_openloop"] in s
    assert NOT_EVIDENCE not in engine_line(["event"], "polar", 4)
    t = table([{"a": 1.23456, "b": "x"}, {"a": 2.0, "b": "yy"}])
    assert "1.23" in t and "yy" in t


def test_evm_equalize_follows_polartx_convention(fr2_sim):
    """metrics.evm_equalize is PolarResult.evm's equalize: per_tone gives a
    different (per-tone-equalised) number than scalar, as in polar_tx."""
    r = fr2_sim.run(0.0, "none")
    e = r.far["beam"][1]
    scalar = ota_metrics(e, fr2_sim.wf, 0.0, "beam", equalize="scalar", with_sem=False)
    tone = ota_metrics(e, fr2_sim.wf, 0.0, "beam", equalize="per_tone", with_sem=False)
    assert scalar.evm_db != tone.evm_db
    assert abs(scalar.evm_db - fr2_sim.elements[0].run(fr2_sim.x, fr2_sim.wf).raw.evm("scalar").db) > 0   # different signals
    assert tone.evm_db < scalar.evm_db                                   # equalising can only help


def test_disclaimer_follows_the_engine_and_the_grid():
    """Break-check (cairn/dtc-openloop-grid.md): the response engine is
    linearised and stays disclaimed on ANY grid -- dropping its disclaimer must
    turn this red; rfdac likewise.  dtc_openloop is cleared only where ex22
    (reading P) checked it: the polar chain, its 4x clock held >= 4 grid
    samples per update.  Below that, on an unknown grid, or on a topology
    whose clock follows the grid, it keeps a disclaimer that says why; the
    full-span mask is never cleared."""
    for hold in (None, 1, 4, 16):
        assert disclaimer_for("response", "polar", hold) == DISCLAIMERS["response"]
        assert NOT_EVIDENCE in engine_line(["response"], "polar", None, hold) and "线性化" in engine_line(["response"], "polar", None, hold)
        assert disclaimer_for("rfdac", "rfdac", hold) is not None
        # outphasing's clock follows the grid (polar_tx splits it for the polar chain only)
        assert disclaimer_for("dtc_openloop", "outphasing", hold) == DISCLAIMERS["dtc_openloop_tied"]
    for hold in (None, 1, 2, CONVERGED_HOLD - 1):
        assert disclaimer_for("dtc_openloop", "polar", hold) == DISCLAIMERS["dtc_openloop"]
    assert disclaimer_for("dtc_openloop", "polar", CONVERGED_HOLD) is None
    line = engine_line(["dtc_openloop"], "polar", 32, 8)
    assert CONVERGED_NOTE in line and DISCLAIMERS["full_span"] in line and DISCLAIMERS["dtc_openloop"] not in line
    # dtc_openloop is not called linearised; every disclaimer says it is not evidence
    assert "线性化" not in DISCLAIMERS["dtc_openloop"] and all(NOT_EVIDENCE in d for d in DISCLAIMERS.values())
    # a mixed run is as weak as its weakest engine
    assert DISCLAIMERS["response"] in engine_line(["dtc_openloop", "response"], "polar", 32, 8)
    # the same threshold and phrase as polar_tx's own grid note (vendored polartx.grid)
    from arraytx.vendor.polartx import grid as pt_grid
    assert CONVERGED_HOLD == pt_grid.CONVERGED_HOLD and NOT_EVIDENCE == pt_grid.NOT_EVIDENCE


def test_the_run_carries_its_grid_into_the_engine_line():
    from arraytx import ArraySim, load_config
    cfg = load_config("configs/fr2_4el_survey.yaml")
    r = ArraySim(cfg, n_symbols=2).run(0.0, "none", conducted_diagnostics=False)
    assert "os 4" in r.info["engine_line"] and DISCLAIMERS["dtc_openloop"] in r.info["engine_line"]
    cfg.sim.oversampling = 16
    r = ArraySim(cfg, n_symbols=2).run(0.0, "none", conducted_diagnostics=False)
    line = r.info["engine_line"]
    assert "os 16, 4 grid samples per update" in line and CONVERGED_NOTE in line
    assert DISCLAIMERS["dtc_openloop"] not in line and DISCLAIMERS["full_span"] in line
