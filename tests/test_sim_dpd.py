"""ArraySim end to end and the three DPD schemes (acceptance items 2 and 3)."""
import numpy as np
import pytest

from arraytx import ArraySim, config_from_dict, load_config
from arraytx.dpd import SCHEMES, make_ila
from arraytx.vendor.polartx import nr_dtc
from arraytx.vendor.polartx.vendor.padpd.data.align import align_delay


def test_anchor_sim_equals_polartx_bitwise(anchor_sim):
    """Acceptance 1: sub-6, S = 0, one element -> one polar_tx chain, bit for bit,
    through the whole ArraySim path (CFR outside, pinned scale, steering,
    coupling short-circuit, far field)."""
    r = anchor_sim.run(0.0, "none")
    p = nr_dtc()
    ref = p.tx.run(anchor_sim.wf, noise=True, seed=anchor_sim.elements[0].run_seed)
    assert np.array_equal(r.ys[0], ref.y)
    assert np.array_equal(r.rs[0], ref.y)              # S = 0: same object through apply_coupling
    assert np.array_equal(r.far["beam"][1], ref.y)     # broadside, one element
    assert abs(r.beam.evm_db - ref.evm().db) < 1e-12


def test_three_schemes_converge_without_coupling():
    """Acceptance 2: coupling -> 0 makes the three schemes' OTA ACLR agree
    within 0.5 dB (the two DPDs are then the same device seen twice: with
    no leakage the far field at the beam is the per-element average)."""
    cfg = config_from_dict({"coupling": {"scale_db": "-inf"}, "element": {"errors": {"enabled": False}}})
    sim = ArraySim(cfg)
    assert sim.coupling.is_zero
    rs = {s: sim.run(30.0, s) for s in ("per_element", "array")}
    assert abs(rs["per_element"].beam.aclr1_db - rs["array"].beam.aclr1_db) < 0.5
    assert abs(rs["per_element"].beam.evm_db - rs["array"].beam.evm_db) < 0.5
    none = sim.run(30.0, "none")
    assert rs["array"].beam.aclr1_db < none.beam.aclr1_db - 3.0        # DPD does something


def test_dpd_improves_the_beam_with_coupling(fr2_sim):
    rs = {s: fr2_sim.run(30.0, s) for s in SCHEMES}
    n, pe, ar = (rs[s].beam.aclr1_db for s in SCHEMES)
    assert pe < n - 3.0 and ar < n - 3.0, (n, pe, ar)
    assert rs["per_element"].dpd.n_coeffs() == 4 * rs["array"].dpd.n_coeffs()
    assert set(rs["array"].engine_modes) == {"dtc_openloop"}
    assert "线性化引擎" in rs["array"].info["engine_line"]


def test_dpd_does_not_move_the_operating_point(fr2_sim):
    """The pinned full scale is the same object for every scheme; the DPD's
    peak expansion is visible in the drive, not absorbed by a re-normalisation."""
    r0 = fr2_sim.run(0.0, "none")
    r1 = fr2_sim.run(0.0, "array")
    fs0 = [e.info["element"]["fs_scale"] for e in r0.element_results]
    fs1 = [e.info["element"]["fs_scale"] for e in r1.element_results]
    assert fs0 == fs1 and len(set(fs0)) == 1
    assert np.abs(r1.drives[0]).max() > np.abs(r0.drives[0]).max()


def test_array_dpd_observation_is_aligned(fr2_sim):
    """The far field at the beam carries no delay relative to the drive (array
    phase centre at the origin, steering compensated): align_delay finds 0."""
    r = fr2_sim.run(60.0, "none")
    _, _, info = align_delay(fr2_sim.x, r.far["beam"][1], max_lag=64)
    assert info["lag"] == 0 and abs(info["lag_total"]) < 0.05


def test_per_element_antenna_port_observation_runs(fr2_sim):
    cfg = config_from_dict({"dpd": {"per_element_observe": "antenna_port"}})
    sim = ArraySim(cfg)
    r = sim.run(0.0, "per_element")
    assert r.dpd.info["observe"] == "antenna_port"
    none = sim.run(0.0, "none")
    assert r.beam.aclr1_db < none.beam.aclr1_db - 3.0


def test_squint_is_a_pointing_effect_not_a_beam_evm_effect():
    """Refuted expectation, kept as a test: for 4 elements at lambda/2 the
    band-edge squint at 60 deg (0.7 deg, see test_beam) leaves the beam-
    direction EVM untouched -- the array is centred on its phase centre, so
    the per-element band-edge phase errors (+-0.03 rad) cancel to a second-
    order amplitude loss.  Phase-shifter and TTD steering agree within
    0.05 dB at 60 deg; both sit within 0.3 dB of broadside."""
    off = {"element": {"errors": {"enabled": False}}}
    ph = ArraySim(config_from_dict({**off, "beam": {"steering": "phase"}})).run(60.0, "none")
    td = ArraySim(config_from_dict({**off, "beam": {"steering": "ttd"}})).run(60.0, "none")
    b0 = ArraySim(config_from_dict(off)).run(0.0, "none")
    assert abs(ph.beam.evm_db - td.beam.evm_db) < 0.05
    assert abs(td.beam.evm_db - b0.beam.evm_db) < 0.3
    assert abs(ph.beam.evm_db - b0.beam.evm_db) < 0.3


def test_run_matrix_and_switch_independence():
    """Invariant 5 at the system level: changing the coupling source leaves
    every element's conducted output bit for bit unchanged."""
    a = ArraySim(load_config("configs/fr2_4el_analytic.yaml")).run(30.0, "none")
    s = ArraySim(load_config("configs/fr2_4el_survey.yaml")).run(30.0, "none")
    assert np.array_equal(a.ys, s.ys)
    assert not np.array_equal(a.rs, s.rs)
    m = ArraySim(config_from_dict({"beam": {"scan_deg": [0.0, 60.0]}})).run_matrix(schemes=("none",))
    assert set(m) == {(0.0, "none"), (60.0, "none")}


def test_make_ila_uses_config_gmp():
    cfg = config_from_dict({"dpd": {"gmp": {"order": 3, "memory_depth": 2, "lag_order": 0, "lag_memory": 0, "lag_span": 0}}})
    ila = make_ila(cfg)
    m = ila.model_factory()
    assert m.n_coeffs == 6
    with pytest.raises(ValueError):
        config_from_dict({"dpd": {"scheme": "neural"}})
