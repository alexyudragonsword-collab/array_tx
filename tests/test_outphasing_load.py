"""ROADMAP B3, option A (cairn/outphasing-load-proposal.md): a finite branch
source impedance rho in the Chireix combiner.  The closed form is checked
against a numerical solve of the series-transformer network; the shape of the
distortion against the lambda/4-line network as well; the array's Gamma is a
complex gain (Thevenin); rho = 0 is polar_tx's combiner bit for bit."""
import numpy as np
import pytest

from arraytx import ArraySim, config_from_dict
from arraytx.loadpull import SourceImpedanceCombiner
from arraytx.vendor.polartx.dpa.combiner import OutphasingCombiner

THETA = np.deg2rad(np.linspace(0.0, 85.0, 18))
B = 0.5 * np.sin(2.0 * np.deg2rad(60.0))


def _series(theta, rho, gam):
    """Branch k: v_k behind rho, node shunt jB_k; series combining into Z_L."""
    zl = 2 * (1 + gam) / (1 - gam)
    out = []
    for th in theta:
        v = 0.5 * np.exp(1j * np.array([th, -th]))
        a = np.array([[1 / rho + 1j * B, 0, 1], [0, 1 / rho - 1j * B, 1], [1, 1, -zl]], dtype=complex)
        u1, u2, i = np.linalg.solve(a, np.array([v[0] / rho, v[1] / rho, 0], dtype=complex))
        out.append(i * zl)
    return np.array(out)


def _quarter_wave(theta, rho, gam, zt=1.0, rl=0.5):
    """Branch k: v_k behind rho, node shunt jB_k, lambda/4 line to the common node, Z_L there."""
    zl = rl * (1 + gam) / (1 - gam)
    out = []
    for th in theta:
        v = 0.5 * np.exp(1j * np.array([th, -th]))
        a = np.zeros((5, 5), complex)
        r = np.zeros(5, complex)
        for k, bk in enumerate((B, -B)):
            a[k, k], a[k, 2], r[k] = 1 / rho + 1j * bk, 1j / zt, v[k] / rho
            a[2 + k, k], a[2 + k, 3 + k] = 1, -1j * zt
        a[4, 3] = a[4, 4] = 1
        a[4, 2] = -1 / zl
        out.append(np.linalg.solve(a, r)[2])
    return np.array(out)


def _closed(theta, rho, gam):
    c = SourceImpedanceCombiner(mode="chireix", source_impedance_rel=rho, combiner_loss_db=0.0)
    c.set_load(np.full(theta.size, gam, dtype=complex))
    return c.combine(0.5 * np.exp(1j * theta), 0.5 * np.exp(-1j * theta))


@pytest.mark.parametrize("rho", [0.02, 0.05, 0.1])
@pytest.mark.parametrize("gam", [0.0, -0.16, 0.26, 0.26j, 0.2 - 0.1j])
def test_closed_form_is_the_series_network(rho, gam):
    ref = _series(THETA, rho, gam) / _series(np.zeros(1), rho, 0.0)[0]
    assert np.allclose(_closed(THETA, rho, gam), ref, rtol=1e-12, atol=1e-14)


@pytest.mark.parametrize("rho", [0.05, 0.1])
def test_the_distortion_does_not_depend_on_gamma_in_either_topology(rho):
    """Thevenin: the load is a theta-independent complex factor.  The shape
    y(theta) / y(0) is the same for every Gamma, in the series network and in
    the lambda/4 one, and the two topologies agree on it."""
    shape = lambda y: y / y[0]                                   # noqa: E731
    base = shape(_closed(THETA, rho, 0.0))
    for gam in (-0.16, 0.26, 0.26j):
        assert np.allclose(shape(_closed(THETA, rho, gam)), base, rtol=1e-12)
        assert np.allclose(shape(_quarter_wave(THETA, rho, gam)), base, rtol=1e-10)
    ripple = 20 * np.log10(np.abs(base / np.cos(THETA)).max() / np.abs(base / np.cos(THETA)).min())
    assert 1.0 < ripple < 5.0 and np.ptp(np.angle(base)) < 1e-12          # AM-AM only, no AM-PM


def test_rho_zero_and_isolated_mode():
    y1, y2 = np.exp(1j * THETA), np.exp(-1j * THETA)
    for mode in ("chireix", "isolated"):
        ref = OutphasingCombiner(mode=mode).combine(y1, y2)
        assert np.array_equal(SourceImpedanceCombiner(mode=mode, source_impedance_rel=0.0).combine(y1, y2), ref)
    with pytest.raises(TypeError):
        SourceImpedanceCombiner(mode="chireix")                              # no default of its own (AGENTS rule 1)
    iso = SourceImpedanceCombiner(mode="isolated", source_impedance_rel=0.1)
    assert np.allclose(iso.combine(y1, y2), OutphasingCombiner(mode="isolated").combine(y1, y2))   # B = 0: no distortion


OUT = {"standard": "sub6_nr100", "element": {"topology": "outphasing"}}


def test_rho_zero_is_bit_identical_and_rho_distorts_a_single_element():
    a = ArraySim(config_from_dict(OUT)).run(0.0, "none", conducted_diagnostics=False)
    b = ArraySim(config_from_dict({**OUT, "element": {"topology": "outphasing", "outphasing": {"source_impedance_rel": 0.0}}})).run(0.0, "none", conducted_diagnostics=False)
    assert np.array_equal(a.ys, b.ys)
    c = ArraySim(config_from_dict({**OUT, "element": {"topology": "outphasing", "outphasing": {"source_impedance_rel": 0.05}}})).run(0.0, "none", conducted_diagnostics=False)
    assert c.beam.aclr1_db > a.beam.aclr1_db + 3.0
    with pytest.raises(ValueError):
        config_from_dict({"element": {"outphasing": {"source_impedance_rel": -0.1}}})


def test_load_pull_reaches_outphasing_only_through_rho():
    lp = {"pa": {"load_pull": {"enabled": True}}}
    off = ArraySim(config_from_dict({**OUT, "element": {"topology": "outphasing", **lp}}))
    assert not off.load_pull_active                                       # rho = 0: nothing to pull with
    on = ArraySim(config_from_dict({**OUT, "element": {"topology": "outphasing", "outphasing": {"source_impedance_rel": 0.05}, **lp}}))
    assert on.load_pull_active
    r = on.run(30.0, "none", conducted_diagnostics=False)
    assert r.info["load_pull"]["iterations"] == 2 and r.element_results[0].info["element"]["load_pull_effective"] is True


def test_the_combiner_is_the_presets_own_with_rho_added_and_reports_its_own_load_gain():
    cfg = {**OUT, "element": {"topology": "outphasing", "outphasing": {"source_impedance_rel": 0.05},
                              "pa": {"load_pull": {"enabled": True}}}}
    sim = ArraySim(config_from_dict(cfg))
    c = sim.elements[0].tx.combiner
    ref = ArraySim(config_from_dict(OUT)).elements[0].tx.combiner
    assert isinstance(c, SourceImpedanceCombiner) and type(ref) is OutphasingCombiner
    assert (c.mode, c.chireix_theta_c_deg, c.combiner_loss_db) == (ref.mode, ref.chireix_theta_c_deg, ref.combiner_loss_db)
    lp = sim.run(60.0, "none", conducted_diagnostics=False).info["load_pull"]
    # what acts is |F(Gamma)| ~ 1 +- rho |Gamma|, not the polar DPA's |1 + Gamma|
    assert all(abs(g - 1.0) < 0.05 * 0.6 for g in lp["load_gain_mean"])
    assert max(abs(m - 1.0) for m in lp["abs_1pg_mean"]) > 3 * max(abs(g - 1.0) for g in lp["load_gain_mean"])
