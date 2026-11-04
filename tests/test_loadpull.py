"""Load modulation (A2): the switch is inert bit for bit when off or when
there is nothing to pull with; on, the PA compresses on its total port swing;
under a single beam with identical elements Gamma_k is (nearly) constant,
so per-element DPD still compensates at its training angle -- the
prediction written in cairn/load-pull-proposal.md before the code."""
import numpy as np
import pytest

from arraytx import ArraySim, config_from_dict, load_config
from arraytx.guispec import controls
from arraytx.loadpull import LoadPulledDPA, active_reflection, amam_loaded, loaded_power_terms
from arraytx.vendor.polartx.dpa.characteristics import amam_curve, efficiency_curve
from arraytx.vendor.polartx.dpa.dpa import DPA, DPAConfig

ON = {"element": {"pa": {"load_pull": {"enabled": True}}}}


def test_loaded_amam_is_the_table_at_g_1_and_compresses_earlier_above():
    r = np.linspace(0, 1, 101)
    rapp = ("rapp", 2.0, 1.0)
    assert np.array_equal(amam_loaded(rapp, r, np.ones_like(r)), amam_curve(rapp, r))
    hi = amam_loaded(rapp, r, np.full_like(r, 1.3))
    lo = amam_loaded(rapp, r, np.full_like(r, 0.7))
    assert np.all(hi[1:] <= amam_curve(rapp, r)[1:] + 1e-15) and hi[-1] < amam_curve(rapp, r)[-1] - 0.02   # more swing: earlier knee
    assert lo[-1] > amam_curve(rapp, r)[-1] + 0.02                                                   # less swing: more linear
    assert abs(hi[5] / r[5] - lo[5] / r[5]) < 1e-3                                                  # small signal: the gain does not move
    assert np.array_equal(amam_loaded("ideal", r, np.full_like(r, 1.3)), r)                          # no knee, no load dependence


def test_load_pulled_dpa_is_the_vendored_dpa_with_no_load():
    cfg = DPAConfig(n_bits=8, n_thermo=4, sigma_cell=0.002, amam=("rapp", 2.0, 1.0), ampm_deg_poly=(0.0, 0.0, 8.0), seed=3)
    base, lp = DPA(cfg), LoadPulledDPA(cfg)
    code = np.arange(256)
    ph = np.linspace(-1, 1, 256)
    assert np.array_equal(base(code, ph), lp(code, ph))
    assert np.array_equal(lp.amp_table, base.amp_table) and np.array_equal(lp.phase_table, base.phase_table)
    lp.set_load(np.zeros(256, dtype=complex))
    assert np.allclose(lp(code, ph), base(code, ph), atol=1e-12)                 # Gamma = 0 through the loaded formula
    lp.set_load(np.full(256, 0.3 + 0j))
    y = lp(code, ph)
    assert abs(y[-1]) < abs(base(code, ph)[-1]) and abs(np.angle(y[-1])) > abs(base.phase_table[-1])   # more swing: compressed, more AM-PM
    with pytest.raises(ValueError):
        lp(code[:10], ph[:10])
    lp.set_load(None)
    assert np.array_equal(base(code, ph), lp(code, ph))


def test_active_reflection_guards():
    ys = np.array([[1.0, 0.001, 2.0]], dtype=complex)
    rs = ys + np.array([[0.2j, 0.5, 2.0]])
    g = active_reflection(ys, rs, [0.01], 0.5)
    assert g[0, 0] == 0.2j and g[0, 1] == 0 and abs(abs(g[0, 2]) - 0.5) < 1e-12                   # plain, floored, clipped


def test_switch_is_bitwise_inert_when_off_or_without_coupling():
    base = ArraySim(load_config("configs/fr2_4el_survey.yaml"))
    assert not base.load_pull_active
    zero_on = ArraySim(config_from_dict({**ON, "coupling": {"scale_db": "-inf"}}))
    zero_off = ArraySim(config_from_dict({"coupling": {"scale_db": "-inf"}}))
    assert not zero_on.load_pull_active
    assert np.array_equal(zero_on.run(30.0, "none").ys, zero_off.run(30.0, "none").ys)
    ideal = ArraySim(config_from_dict({**ON, "element": {"pa": {"amam": "ideal", "ampm_deg_at_fs": 0.0, "load_pull": {"enabled": True}}}}))
    assert not ideal.load_pull_active                                     # no knee, nothing to pull
    rf = ArraySim(config_from_dict({**ON, "standard": "sub6_nr100", "element": {"topology": "rfdac", "pa": {"load_pull": {"enabled": True}}}}))
    assert not rf.load_pull_active and rf.elements[0].run(rf.x, rf.wf).info["element"]["load_pull_effective"] is False


def test_load_pull_moves_the_knee_and_converges_in_two_rounds():
    on = ArraySim(config_from_dict(ON))
    assert on.load_pull_active
    r = on.run(30.0, "none")
    off = ArraySim(load_config("configs/fr2_4el_survey.yaml")).run(30.0, "none")
    lp = r.info["load_pull"]
    assert lp["iterations"] == 2 and lp["deltas"][1] < 0.1 * lp["deltas"][0] < 0.1         # contraction
    assert max(lp["clip_fraction"]) == 0.0                                 # the |Gamma| guard does not act on 4 x 1 (ex13)
    assert all(0.5 <= m <= 1.5 for m in lp["abs_1pg_mean"]) and all(s < 0.05 for s in lp["abs_1pg_std"])
    # adjacent coupling at 180 deg opposes the forward wave: less swing, a later knee, better conducted ACLR
    assert abs(r.conducted[1].aclr1_db - off.conducted[1].aclr1_db) > 0.3
    assert r.element_results[1].info["element"]["load"]["abs_1pg_mean"] == pytest.approx(lp["abs_1pg_mean"][1])
    assert r.element_results[1].info["element"]["load_pull_effective"] is True


def test_single_beam_identical_elements_gamma_is_constant_and_per_element_dpd_still_works():
    """Prediction 1 of the proposal: with the element errors and PA
    deviations off, Gamma_k is the scan-dependent active impedance -- a
    constant per element -- so the two DPDs end within a fraction of a dB."""
    cfg = config_from_dict({**ON, "element": {"errors": {"enabled": False}, "pa": {"load_pull": {"enabled": True}}}})
    sim = ArraySim(cfg)
    r = sim.run(30.0, "none")
    assert max(r.info["load_pull"]["abs_1pg_std"]) < 0.02 * min(r.info["load_pull"]["abs_1pg_mean"])
    pe = sim.run(30.0, "per_element").beam.aclr1_db
    ar = sim.run(30.0, "array").beam.aclr1_db
    assert abs(pe - ar) < 0.5 and pe < r.beam.aclr1_db - 4.0


def test_controls_for_load_pull_follow_the_switch():
    by = {c.path: c for c in controls()}
    assert by["element.pa.load_pull.enabled"].visible_when is None
    assert by["element.pa.load_pull.kappa_amam"].visible_when == ("element.pa.load_pull.enabled", (True,))
    assert by["element.pa.load_pull.kappa_amam"].source == "assumed" and "voltage" in by["element.pa.load_pull.kappa_amam"].ref
    with pytest.raises(ValueError):
        config_from_dict({"element": {"pa": {"load_pull": {"gamma_max": 0.0}}}})


def test_backoff_raises_the_pinned_full_scale_and_costs_efficiency():
    """element.pa.backoff_db: 0 is polar_tx's pin (bit for bit, fingerprint);
    3 dB puts the undistorted peak at 10^(-3/20) of the code range, which the
    polar_tx DPA law prices as lower average drain efficiency; the report
    carries that number, matched-load and loaded."""
    base = ArraySim(load_config("configs/fr2_4el_survey.yaml"))
    bo = ArraySim(config_from_dict({"element": {"pa": {"backoff_db": 3.0}}}))
    assert bo.elements[0].fs_scale == pytest.approx(base.elements[0].fs_scale * 10 ** (3 / 20))
    r0, r3 = base.run(60.0, "none"), bo.run(60.0, "none")
    e0, e3 = r0.info["efficiency"], r3.info["efficiency"]
    assert e0["law"][0] == "scpa" and e3["eta_avg_mean"] < e0["eta_avg_mean"] - 0.05
    assert r3.beam.aclr1_db < r0.beam.aclr1_db - 2.0                     # the PA is driven less deep
    assert r0.element_results[0].info["element"]["efficiency"]["load"] == "matched"
    b0 = r0.element_results[0].info["element"]["efficiency"]["backoff_db"]
    b3 = r3.element_results[0].info["element"]["efficiency"]["backoff_db"]
    assert b3 - b0 == pytest.approx(3.0, abs=0.3)                       # polar_tx's own backoff reading moves by the 3 dB
    assert np.abs(r3.ys).max() > np.abs(r0.ys).max()                    # output gain stays 1: the less compressed PA keeps its peaks
    with pytest.raises(ValueError):
        config_from_dict({"element": {"pa": {"backoff_db": -1.0}}})


@pytest.mark.parametrize("scheme,observe", [("per_element", "pa_output"), ("per_element", "antenna_port"), ("array", "pa_output")])
def test_joint_training_over_one_angle_is_training_at_the_beam(scheme, observe):
    """dpd.train_angles_deg = [theta] runs the joint ILA (stacked bases) over
    a single pair: the same least-squares problem as training at theta, so
    the drives come out bit for bit -- with load modulation on, where the
    per-angle operating point has to be captured and restored."""
    on = {"element": {"pa": {"load_pull": {"enabled": True}}}, "dpd": {"per_element_observe": observe}}
    plain = ArraySim(config_from_dict(on))
    joint = ArraySim(config_from_dict({**on, "dpd": {"per_element_observe": observe, "train_angles_deg": [30.0]}}))
    a, b = plain.run(30.0, scheme, conducted_diagnostics=False), joint.run(30.0, scheme, conducted_diagnostics=False)
    assert all(np.array_equal(p, q) for p, q in zip(a.drives, b.drives)) and np.array_equal(a.ys, b.ys)
    assert b.dpd.info["train_angles_deg"] == [30.0]


def test_joint_bank_is_trained_once_and_reused_at_every_angle():
    sim = ArraySim(config_from_dict({"dpd": {"train_angles_deg": [0.0, 60.0]}}))
    r0, r60 = sim.run(0.0, "array", conducted_diagnostics=False), sim.run(60.0, "array", conducted_diagnostics=False)
    assert r0.dpd is r60.dpd and r60.dpd.info["train_angles_deg"] == [0.0, 60.0]
    assert r60.seconds < r0.seconds                      # no ILA on the second call
    with pytest.raises(ValueError):
        config_from_dict({"dpd": {"train_angles_deg": [95.0]}})



def test_loaded_power_terms_are_the_scpa_law_at_gamma_0_and_cost_1_minus_gamma2():
    """cairn/loaded-efficiency-proposal.md: switching loss set by the code,
    net port power |a|^2 (1 - |Gamma|^2).  At Gamma = 0 the ratio is the
    matched SCPA average; a constant |Gamma| = 0.3 keeps the loss and takes
    9 % of the net power; |Gamma| > 1 samples count zero and are reported."""
    a = np.linspace(0.05, 1.0, 200)
    law = ("scpa", 0.67, 0.85)
    t0 = loaded_power_terms(a, a, None, law)
    p = a * a
    assert t0["p_net"] == pytest.approx(p.sum()) and t0["p_matched"] == pytest.approx(p.sum())
    assert t0["p_net"] / (t0["p_net"] + t0["p_loss"]) == pytest.approx(p.sum() / (p / efficiency_curve(law, a)).sum())
    t3 = loaded_power_terms(a, a, np.full(a.size, 0.3j), law)
    assert t3["p_loss"] == t0["p_loss"] and t3["p_net"] == pytest.approx(0.91 * t0["p_net"])
    tb = loaded_power_terms(a, a, np.r_[np.zeros(199), 1.2], law)
    assert tb["n_backflow"] == 1 and tb["p_net"] == pytest.approx(t0["p_net"] - p[-1])


def test_loaded_efficiency_is_polar_tx_number_without_load_and_drops_with_it():
    off = ArraySim(load_config("configs/fr2_4el_survey.yaml")).run(60.0, "none", conducted_diagnostics=False)
    e = off.info["efficiency"]
    assert e["eta_loaded_per_element"] == [r.info["element"]["efficiency"]["eta_avg"] for r in off.element_results]
    assert e["eta_array_loaded"] == e["eta_array_matched"] and e["n_backflow"] == 0
    on = ArraySim(config_from_dict(ON)).run(60.0, "none", conducted_diagnostics=False).info["efficiency"]
    assert on["eta_array_loaded"] < on["eta_array_matched"] - 0.01          # |Gamma|^2 ~ 0.08 at 60 deg on 4 x 1
    assert on["eta_avg_mean"] == pytest.approx(e["eta_avg_mean"])           # no DPD: same codes, same matched law



def test_joint_bank_cache_follows_the_dpd_config():
    sim = ArraySim(config_from_dict({"dpd": {"train_angles_deg": [0.0, 60.0]}}))
    a = sim.run(30.0, "array", conducted_diagnostics=False).dpd
    sim.cfg.dpd.train_angles_deg = [0.0, 30.0, 60.0]
    b = sim.run(30.0, "array", conducted_diagnostics=False).dpd
    assert b is not a and b.info["train_angles_deg"] == [0.0, 30.0, 60.0]
    assert sim.run(0.0, "array", conducted_diagnostics=False).dpd is b
