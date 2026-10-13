"""Invariant 4: squint from the true bandwidth; far-field synthesis."""
import numpy as np
import pytest

from arraytx.beam import (array_factor_cw, far_field, far_field_many,
                          highest_sidelobe_direction, peak_direction_cw,
                          squint_analytic_deg, steer)
from arraytx.geometry import C0, LinearArray

F0 = 28e9
FS = 1.96608e9


def _geom(n=4, pattern="isotropic"):
    return LinearArray(n=n, spacing_lambda=0.5, f0_hz=F0, element_pattern=pattern)


def test_geometry_centred_and_delays():
    g = _geom(4)
    x = g.positions_m
    assert abs(x.sum()) < 1e-18 and abs(x[1] - x[0] - 0.5 * C0 / F0) < 1e-15
    assert np.all(g.delays_s(0.0) == 0.0)
    tau = g.delays_s(30.0)
    assert abs(tau[3] - x[3] * 0.5 / C0) < 1e-24
    assert LinearArray(1, 0.5, F0).positions_m[0] == 0.0
    with pytest.raises(ValueError):
        LinearArray(4, 0.5, F0, element_pattern="patch")


def test_single_element_broadside_is_bitwise_identity():
    g = _geom(1)
    rng = np.random.default_rng(0)
    y = rng.standard_normal(1000) + 1j * rng.standard_normal(1000)
    e = far_field([y], g, 0.0, FS)
    assert e is y or np.array_equal(e, y)
    assert steer(y, g, 0.0, FS, "phase")[0] is y
    assert steer(y, g, 30.0, FS, "ttd")[0] is y          # one element at x=0: tau = 0


def test_coherent_gain_is_20log10_n():
    g = _geom(4)
    rng = np.random.default_rng(1)
    x = rng.standard_normal(4096) + 1j * rng.standard_normal(4096)
    for mode in ("phase", "ttd"):
        for th0 in (0.0, 30.0, 60.0):
            ys = steer(x, g, th0, FS, mode)
            e = far_field(ys, g, th0, FS, normalize=False)
            p_in = np.mean(np.abs(x) ** 2)
            p_out = np.mean(np.abs(e) ** 2)
            gain_db = 10 * np.log10(p_out / p_in)
            # phase steering: only the carrier is aligned, so a wideband burst
            # loses a little; ttd: exactly 12.04 dB
            tol = 0.3 if mode == "phase" else 1e-6
            assert abs(gain_db - 20 * np.log10(4)) < tol, (mode, th0, gain_db)
            en = far_field(ys, g, th0, FS)
            assert abs(10 * np.log10(np.mean(np.abs(en) ** 2) / p_in)) < tol


@pytest.mark.parametrize("theta0", [30.0, 60.0])
def test_squint_phase_steering_matches_analytic_within_10pct(theta0):
    g = _geom(4)
    for df in (-200e6, 200e6):                       # the FR2 band edges
        meas = peak_direction_cw(g, theta0, df, "phase") - theta0
        ana = squint_analytic_deg(theta0, F0, df)
        assert abs(meas - ana) <= 0.10 * abs(ana), (theta0, df, meas, ana)
        # small-angle form the prompt quotes: d theta ~ -(df/f0) tan(theta0)
        small = -np.degrees(df / F0 * np.tan(np.radians(theta0)))
        assert abs(ana - small) <= 0.10 * abs(small)


def test_ttd_has_no_squint():
    g = _geom(4)
    for theta0 in (30.0, 60.0):
        for df in (-200e6, 200e6):
            meas = peak_direction_cw(g, theta0, df, "ttd") - theta0
            ana = squint_analytic_deg(theta0, F0, df)
            assert abs(meas) < 0.05 * abs(ana)


def test_far_field_of_steered_tone_squints_like_the_closed_form():
    """The waveform path (steer -> far_field, frequency domain) and the CW
    closed form agree: a tone at +200 MHz steered with phase shifters to 60
    deg peaks away from 60 deg by the analytic squint."""
    g = _geom(4)
    n = 8192
    t = np.arange(n) / FS
    df = FS / n * round(200e6 / (FS / n))            # on-bin tone, 200 MHz-ish
    x = np.exp(2j * np.pi * df * t)
    ys = steer(x, g, 60.0, FS, "phase")
    thetas = np.arange(55.0, 65.0, 0.01)
    e = far_field_many(ys, g, thetas, FS)
    p = np.mean(np.abs(e) ** 2, axis=1)
    peak = thetas[np.argmax(p)]
    ana = squint_analytic_deg(60.0, F0, df)
    assert abs((peak - 60.0) - ana) <= 0.10 * abs(ana), (peak, ana)
    assert abs(ana) > 0.5                              # it is a visible effect at 60 deg


def test_highest_sidelobe_direction_and_element_pattern():
    g = _geom(4)
    sl = highest_sidelobe_direction(g, 0.0, "phase")
    # 4-element lambda/2: first sidelobe near sin(theta) ~ 0.72 -> ~46 deg
    assert sl is not None and 40.0 < abs(sl) < 52.0
    af = array_factor_cw(g, 0.0, 0.0, [0.0, sl], "phase")
    assert af[0] > 0.999 and 0.2 < af[1] < 0.4          # -13.5 dB class sidelobe... for 4 elements ~ -11.3 dB
    assert highest_sidelobe_direction(_geom(1), 0.0, "phase") is None
    gc = _geom(4, "cos")
    assert gc.element_gain(60.0) == pytest.approx(0.5)
    assert array_factor_cw(gc, 60.0, 0.0, [60.0], "phase")[0] == pytest.approx(0.5)
