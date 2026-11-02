"""Element count vs squint (ex06): the squint is a linear response at the
beam, invisible at 4 elements, a beam-EVM effect at 64, gone under a
per-tone equaliser."""
import numpy as np

from arraytx import ArraySim, config_from_dict
from arraytx.beam import (beam_response, beamwidth_3db_deg, far_field, squint_evm_closed_form_db, steer,
                          tone_frequencies_hz)
from arraytx.geometry import LinearArray
from arraytx.standards import get_standard
from arraytx.vendor.polartx.vendor.padpd.metrics import evm_of_signal

F0 = 28e9


def _wf(n_symbols=2, seed=7):
    return get_standard("fr2_nr400").make_waveform(n_symbols, seed)


def test_beamwidth_scales_as_one_over_n_and_one_over_cos():
    bw = {n: beamwidth_3db_deg(LinearArray(n, 0.5, F0), 0.0) for n in (4, 16, 64)}
    assert abs(bw[16] - np.degrees(0.886 / 8)) / np.degrees(0.886 / 8) < 0.10       # textbook 0.886 lambda / (n d)
    assert 3.5 < bw[4] / bw[16] < 4.5 and 3.5 < bw[16] / bw[64] < 4.5
    g = LinearArray(64, 0.5, F0)
    assert 1.8 < beamwidth_3db_deg(g, 60.0) / beamwidth_3db_deg(g, 0.0) < 2.3        # 1 / cos 60 = 2
    assert beamwidth_3db_deg(LinearArray(1, 0.5, F0), 0.0) == 180.0


def test_closed_form_squint_evm_matches_the_linear_far_field():
    """steer(phase) -> far_field at the beam with ideal elements IS H(f):
    the scalar-equalised EVM of that signal equals the closed form, the
    per-tone EVM is numerically zero, and TTD steering has no squint."""
    wf = _wf()
    f = tone_frequencies_hz(wf)
    for n in (16, 64):
        g = LinearArray(n, 0.5, F0)
        e = far_field(steer(wf.x, g, 60.0, wf.fs, "phase"), g, 60.0, wf.fs)
        meas = evm_of_signal(e, wf.require_ofdm_ref(), equalize="scalar").db
        pred = squint_evm_closed_form_db(g, 60.0, f)
        assert abs(meas - pred) < 0.2, (n, meas, pred)
        assert evm_of_signal(e, wf.require_ofdm_ref(), equalize="per_tone").db < -60
        e_t = far_field(steer(wf.x, g, 60.0, wf.fs, "ttd"), g, 60.0, wf.fs)
        assert evm_of_signal(e_t, wf.require_ofdm_ref(), equalize="scalar").db < -60
    assert squint_evm_closed_form_db(LinearArray(64, 0.5, F0), 60.0, f, equalize="per_tone") == -np.inf
    h = beam_response(LinearArray(64, 0.5, F0), 60.0, f, "phase")
    assert abs(h[np.argmin(np.abs(f))] - 1.0) < 1e-3 and h.real.min() < 0.95       # 1 at DC, drooping at the edges
    assert np.all(beam_response(LinearArray(64, 0.5, F0), 60.0, f, "ttd") == 1.0)


def test_squint_becomes_a_beam_evm_effect_at_64_elements():
    """The 4-element result (test_sim_dpd: squint is a pointing effect) is
    an n-dependent statement.  At 64 elements and 60 deg the phase-shifter
    array pays a measurable EVM penalty against TTD that the closed form
    predicts, and a per-tone equaliser removes."""
    off = {"element": {"errors": {"enabled": False}}, "array": {"n_elements": 64}}
    sp = ArraySim(config_from_dict({**off, "beam": {"steering": "phase"}}))
    st = ArraySim(config_from_dict({**off, "beam": {"steering": "ttd"}}))
    rp = sp.run(60.0, "none", conducted_diagnostics=False)
    rt = st.run(60.0, "none", conducted_diagnostics=False)
    sq = squint_evm_closed_form_db(sp.geom, 60.0, tone_frequencies_hz(sp.wf))
    pred = 10 * np.log10(10 ** (rt.beam.evm_db / 10) + 10 ** (sq / 10)) - rt.beam.evm_db
    meas = rp.beam.evm_db - rt.beam.evm_db
    assert meas > 0.3, (meas, pred)
    assert abs(meas - pred) < 1.0, (meas, pred)
    from arraytx.metrics import ota_metrics
    pt_p = ota_metrics(rp.far["beam"][1], sp.wf, 60.0, "beam", offsets=(1,), equalize="per_tone", with_sem=False).evm_db
    pt_t = ota_metrics(rt.far["beam"][1], st.wf, 60.0, "beam", offsets=(1,), equalize="per_tone", with_sem=False).evm_db
    assert abs(pt_p - pt_t) < 0.2, (pt_p, pt_t)
