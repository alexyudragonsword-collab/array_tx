"""Element chains: bit-identical to polar_tx at the anchor, pinned full
scale, draw-then-zero errors, shared LO."""
from dataclasses import replace

import numpy as np
import pytest

from arraytx.config import load_config, config_from_dict
from arraytx.element import (build_elements, draw_element_errors,
                             reference_full_scale)
from arraytx.lo import ClockProfileLO
from arraytx.seeds import SeedTree
from arraytx.standards import get_standard
from arraytx.vendor.polartx import nr_dtc
from arraytx.vendor.polartx.vendor.padpd.cfr import cfr_clip_filter

NSYM = 2


def _anchor():
    cfg = load_config("configs/sub6_1el_anchor.yaml")
    st = get_standard(cfg.standard)
    tree = SeedTree(cfg.seed, cfg.array.n_elements)
    wf = st.make_waveform(NSYM, tree.int_seed("waveform"))
    x = cfr_clip_filter(wf.x, cfg.sim.cfr_papr_db, wf.fs, wf.bw)
    return cfg, st, tree, wf, x


def test_anchor_element_equals_polartx_bitwise():
    """sub-6, S irrelevant here (no coupling in this module), one element,
    errors off: the element's conducted output IS polar_tx's nr_dtc() run."""
    cfg, st, tree, wf, x = _anchor()
    els = build_elements(cfg, st, tree, x, wf)
    r = els[0].run(x, wf, noise=cfg.sim.noise)
    p = nr_dtc()                                   # polar_tx default, CFR inside
    ref = p.tx.run(wf, noise=True, seed=els[0].run_seed)
    assert np.array_equal(r.y, ref.y)
    assert r.phasemod_mode == "dtc_openloop"


def test_pinned_full_scale_equals_polartx_auto():
    cfg, st, tree, wf, x = _anchor()
    tx_auto = st.preset(cfr_papr_db=None).tx
    fs = reference_full_scale(tx_auto, "polar", x, wf)
    tx_pin = st.preset(cfr_papr_db=None).tx
    tx_pin.cfg = replace(tx_pin.cfg, fs_scale_fixed=fs)
    wf_c = replace(wf, x=x)
    a = tx_auto.run(wf_c, seed=3).y
    b = tx_pin.run(wf_c, seed=3).y
    assert np.array_equal(a, b)
    # and a peak-expanded drive does NOT move the pinned chain's scale
    x2 = x * 1.3
    assert tx_pin.cfg.fs_scale_fixed == fs
    assert reference_full_scale(tx_auto, "polar", x2, wf) > fs


def test_errors_drawn_then_zeroed():
    on = config_from_dict({"array": {"n_elements": 3}})
    off = config_from_dict({"array": {"n_elements": 3}, "element": {"errors": {"enabled": False}}})
    t = SeedTree(1, 3)
    for k in range(3):
        e_on, e_off = draw_element_errors(on, t, k), draw_element_errors(off, t, k)
        assert e_off.is_identity and e_off.pa_dev == 0.0
        assert not e_on.is_identity
    # independent of n_elements and of other elements
    e1 = draw_element_errors(on, SeedTree(1, 8), 1)
    assert e1 == draw_element_errors(on, t, 1)


def test_other_switches_do_not_change_element_draws():
    """Invariant 5: coupling source, DPD scheme, steering, scale do not touch
    the element errors or the chain's seeds."""
    base = {"array": {"n_elements": 2}}
    variants = [
        {"coupling": {"source": "analytic"}}, {"dpd": {"scheme": "array"}},
        {"beam": {"steering": "ttd"}}, {"coupling": {"scale_db": -40.0}},
        {"element": {"pa": {"amam": "ideal"}}},
    ]
    ref_cfg = config_from_dict(base)
    t = SeedTree(ref_cfg.seed, 2)
    ref = [(draw_element_errors(ref_cfg, t, k), t.int_seed("run", k), t.int_seed("dpa_mismatch", k)) for k in range(2)]
    for v in variants:
        d = {**base, **v}
        cfg = config_from_dict(d)
        t2 = SeedTree(cfg.seed, 2)
        got = [(draw_element_errors(cfg, t2, k), t2.int_seed("run", k), t2.int_seed("dpa_mismatch", k)) for k in range(2)]
        assert got == ref, v


def test_pa_deviation_changes_dpa_tables_only_when_enabled():
    cfg = config_from_dict({"array": {"n_elements": 2}})
    st = get_standard(cfg.standard)
    t = SeedTree(cfg.seed, 2)
    wf = st.make_waveform(NSYM, 0)
    els = build_elements(cfg, st, t, wf.x, wf)
    assert not np.array_equal(els[0].tx.dpa.amp_table, els[1].tx.dpa.amp_table)
    off = config_from_dict({"array": {"n_elements": 2}, "element": {"errors": {"enabled": False}}})
    els2 = build_elements(off, st, SeedTree(off.seed, 2), wf.x, wf)
    assert np.array_equal(els2[0].tx.dpa.amp_table, els2[1].tx.dpa.amp_table)
    assert np.array_equal(els2[0].tx.dpa.phase_table, els2[1].tx.dpa.phase_table)


def test_shared_lo_gives_identical_lo_sample():
    """With errors off and jitter zero, two elements on one LO produce the
    same phase trajectory; two LOs do not."""
    def run(shared):
        cfg = config_from_dict({"array": {"n_elements": 2}, "element": {"errors": {"enabled": False},
                                                                        "lo": {"shared": shared}}})
        st = get_standard(cfg.standard)
        t = SeedTree(cfg.seed, 2)
        wf = st.make_waveform(NSYM, 0)
        els = build_elements(cfg, st, t, wf.x, wf)
        for e in els:   # kill the per-element jitter so only the LO differs
            pm = e.tx.phasemod
            pm.cfg = replace(pm.cfg, jitter_rms_s=0.0, dither=False)
        outs = [e.run(wf.x, wf).raw.phase_out for e in els]
        return outs, els
    (a, b), els = run(True)
    assert els[0].lo_pn_seed == els[1].lo_pn_seed is not None
    assert np.array_equal(a, b)
    (c, d), els2 = run(False)
    assert els2[0].lo_pn_seed is None
    assert not np.array_equal(c, d)


def test_clock_profile_lo_psd():
    lo = ClockProfileLO("tests/data/clock_profile_test.yaml", fout_hz=28e9)
    f = np.array([1e3, 1e6, 5e9])
    s = lo.psd(f)
    # L = -80 dBc/Hz at 1 kHz -> S_phi = 2e-8 rad^2/Hz at 7 GHz, x (28/7)^2 = 16 at 28 GHz
    assert abs(s[0] / (2 * 10 ** (-80 / 10) * 16) - 1) < 1e-12
    assert s[2] == 0.0                        # beyond f0/2
    assert lo.leeson("lo") is lo
    raw = ClockProfileLO("tests/data/clock_profile_test.yaml", fout_hz=7e9)
    assert abs(raw.psd(np.array([1e6]))[0] / (2 * 10 ** (-115 / 10)) - 1) < 1e-12


def test_clock_profile_drives_the_element():
    cfg = config_from_dict({"array": {"n_elements": 1}, "element": {"lo": {"clock_profile": "tests/data/clock_profile_test.yaml"}}})
    st = get_standard(cfg.standard)
    t = SeedTree(cfg.seed, 1)
    wf = st.make_waveform(NSYM, 0)
    els = build_elements(cfg, st, t, wf.x, wf)
    assert isinstance(els[0].tx.phasemod.cfg.lo_pn, ClockProfileLO)
    r = els[0].run(wf.x, wf)
    assert r.info["phasemod"].get("lo_pn") is True


@pytest.mark.parametrize("topology", ["polar", "outphasing", "rfdac"])
def test_three_topologies_run_sub6(topology):
    cfg = config_from_dict({"standard": "sub6_nr100", "array": {"n_elements": 2},
                           "element": {"topology": topology}})
    st = get_standard(cfg.standard)
    t = SeedTree(cfg.seed, 2)
    wf = st.make_waveform(NSYM, 0)
    els = build_elements(cfg, st, t, wf.x, wf)
    r = els[1].run(wf.x, wf)
    assert r.y.shape == wf.x.shape and np.isfinite(r.y).all()
    assert els[1].engine in ("dtc_openloop", "rfdac", "DTCPhaseModulator")
