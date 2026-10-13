"""Invariant 3: coupling enters the chain through one path, three sources."""
import numpy as np
import pytest

from arraytx import coupling as cp
from arraytx.config import config_from_dict, load_config
from arraytx.coupling import (CouplingMatrix, analytic_matrix, apply_coupling,
                              build_coupling, survey_matrix, touchstone_matrix,
                              write_matrix_touchstone)
from arraytx.geometry import C0, LinearArray
from arraytx.touchstone import read_touchstone, write_touchstone

F0, FS = 28e9, 1.96608e9
G4 = LinearArray(4, 0.5, F0)


def _ys(n=4, N=2048, seed=0):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((n, N)) + 1j * rng.standard_normal((n, N))


def test_zero_coupling_returns_the_input_object():
    m = analytic_matrix(4, -16.0, 180.0, -6.0, F0 - FS / 2, F0 + FS / 2).scaled(-np.inf)
    assert m.is_zero
    ys = _ys()
    assert apply_coupling(ys, m, FS, F0) is ys
    m1 = analytic_matrix(1, -16.0, 180.0, -6.0, F0 - 1e9, F0 + 1e9)
    y1 = ys[:1]
    assert m1.is_zero and apply_coupling(y1, m1, FS, F0) is y1


def test_analytic_shape_flat_and_reciprocal():
    m = analytic_matrix(4, -16.0, 180.0, -6.0, F0 - 1e9, F0 + 1e9)
    s = m.at(np.array([F0 - 0.3e9, F0, F0 + 0.7e9]))
    assert np.array_equal(s[0], s[1]) and np.array_equal(s[1], s[2])
    s0 = s[0]
    assert np.allclose(s0, s0.T)                               # passive, reciprocal
    assert abs(20 * np.log10(abs(s0[0, 1])) + 16) < 1e-9
    assert abs(20 * np.log10(abs(s0[0, 2])) + 22) < 1e-9
    assert s0[0, 3] == 0 and np.all(np.diag(s0) == 0)
    assert abs(m.max_offdiag_db() + 16) < 1e-9


def test_survey_phase_is_linear_with_the_path_delay():
    d = G4.spacing_m
    grid = np.linspace(F0 - FS / 2, F0 + FS / 2, 257)
    m = survey_matrix(4, -16.0, 180.0, -6.0, F0, d, grid)
    ph = np.unwrap(np.angle(m.s[:, 0, 1]))
    slope = np.polyfit(grid - F0, ph, 1)[0]                   # rad/Hz
    assert abs(slope - (-2 * np.pi * d / C0)) < 1e-15
    ph2 = np.unwrap(np.angle(m.s[:, 0, 2]))
    assert abs(np.polyfit(grid - F0, ph2, 1)[0] - (-2 * np.pi * 2 * d / C0)) < 1e-15
    assert abs(np.angle(m.at(F0)[0, 1]) - np.pi) < 1e-9
    flat = survey_matrix(4, -16.0, 180.0, -6.0, F0, d, grid, path_delay=False)
    assert np.allclose(np.angle(flat.s[:, 0, 1]), np.pi)


def test_touchstone_roundtrip_is_bitwise(tmp_path):
    m = analytic_matrix(4, -16.0, 180.0, -6.0, F0 - FS / 2, F0 + FS / 2)
    p = tmp_path / "a.s4p"
    write_matrix_touchstone(str(p), m)
    back = touchstone_matrix(str(p))
    assert np.array_equal(back.freqs_hz, m.freqs_hz)
    assert np.array_equal(back.s, m.s)
    f_rf = F0 + np.fft.fftfreq(4096, 1 / FS)
    assert np.array_equal(back.at(f_rf), m.at(f_rf))
    ys = _ys()
    assert np.array_equal(apply_coupling(ys, back, FS, F0), apply_coupling(ys, m, FS, F0))


def test_touchstone_formats_and_errors(tmp_path):
    f = np.array([27e9, 28e9, 29e9])
    rng = np.random.default_rng(3)
    s = rng.standard_normal((3, 2, 2)) * 0.1 + 1j * rng.standard_normal((3, 2, 2)) * 0.1
    p = tmp_path / "x.s2p"
    write_touchstone(p, f, s, comments=("hello",))
    t = read_touchstone(p)
    assert t.n_ports == 2 and np.array_equal(t.s, s) and "hello" in t.comments
    # MA and DB variants, GHz unit, wrapped rows
    ma = ["# GHz S MA R 50"]
    for fi in range(3):
        row = [f"{float(f[fi] / 1e9)!r}"]
        for k in range(2):
            for j in range(2):
                row.append(f"{float(abs(s[fi, k, j]))!r} {float(np.degrees(np.angle(s[fi, k, j])))!r}")
        ma.append(" ".join(row))
    (tmp_path / "y.s2p").write_text("\n".join(ma) + "\n")
    t2 = read_touchstone(tmp_path / "y.s2p")
    assert np.allclose(t2.s, s) and np.allclose(t2.freqs_hz, f)
    with pytest.raises(ValueError):
        write_touchstone(tmp_path / "bad.s3p", f, s)
    with pytest.raises(ValueError):
        read_touchstone(tmp_path / "nothing.txt")


def test_scaling_and_leakage_arithmetic():
    m = analytic_matrix(3, -20.0, 0.0, -np.inf, F0 - 1e9, F0 + 1e9)   # c2 = 0: only neighbours, real +0.1
    ys = _ys(3)
    r = apply_coupling(ys, m, FS, F0)
    assert not np.array_equal(r, ys)
    # linear leakage: r_k = y_k + 0.1 * (y_{k-1} + y_{k+1})
    expect = ys.copy()
    expect[0] += 0.1 * ys[1]
    expect[1] += 0.1 * (ys[0] + ys[2])
    expect[2] += 0.1 * ys[1]
    assert np.allclose(r, expect, atol=1e-12)
    m6 = m.scaled(-6.0)
    assert abs(m6.max_offdiag_db() - (-26.0)) < 1e-9
    assert m.scaled(0.0) is m


def test_three_sources_share_one_path_and_one_type(tmp_path, monkeypatch):
    base = {"array": {"n_elements": 4}}
    cfgs = {
        "analytic": config_from_dict({**base, "coupling": {"source": "analytic"}}),
        "survey": config_from_dict({**base, "coupling": {"source": "survey"}}),
    }
    m_a = build_coupling(cfgs["analytic"], G4, FS)
    p = tmp_path / "t.s4p"
    write_matrix_touchstone(str(p), m_a)
    cfgs["touchstone"] = config_from_dict({**base, "coupling": {"source": "touchstone", "touchstone": {"path": str(p)}}})
    mats = {k: build_coupling(c, G4, FS) for k, c in cfgs.items()}
    assert all(isinstance(m, CouplingMatrix) for m in mats.values())
    calls = []
    real = cp.apply_coupling

    def spy(ys, m, fs, f0):
        calls.append(m.source)
        return real(ys, m, fs, f0)
    monkeypatch.setattr(cp, "apply_coupling", spy)
    ys = _ys()
    outs = {k: cp.apply_coupling(ys, m, FS, F0) for k, m in mats.items()}
    assert len(calls) == 3
    assert np.array_equal(outs["analytic"], outs["touchstone"])
    assert not np.array_equal(outs["analytic"], outs["survey"])     # frequency-dependent phase differs
    # ...but at f0 the survey equals the analytic value (same c1 at the carrier)
    assert np.allclose(mats["survey"].at(F0), mats["analytic"].at(F0))


def test_shipped_touchstone_config_matches_analytic():
    """configs/fr2_4el_touchstone.yaml reads tests/data/analytic_4el.s4p,
    which this test regenerates from the analytic config; the two configs
    must produce bit-identical matrices."""
    ca = load_config("configs/fr2_4el_analytic.yaml")
    ct = load_config("configs/fr2_4el_touchstone.yaml")
    m_a = build_coupling(ca, G4, FS)
    write_matrix_touchstone(ct.coupling.touchstone.path, m_a,
                            comments=("generated by tests/test_coupling.py from configs/fr2_4el_analytic.yaml",))
    m_t = build_coupling(ct, G4, FS)
    assert np.array_equal(m_a.s, m_t.s) and np.array_equal(m_a.freqs_hz, m_t.freqs_hz)
