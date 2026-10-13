"""Standards: FR2 numerology and the sub-6 anchor delegate to polar_tx."""
import numpy as np

from arraytx.standards import FR2_NR400, STANDARDS, SUB6_NR100, Sourced, get_standard
import pytest


def test_every_number_has_a_source():
    for st in STANDARDS.values():
        for name, s in st.numbers().items():
            assert isinstance(s, Sourced), (st.name, name)
            assert s.source in ("survey", "derived", "assumed", "measured")
            if s.source in ("survey", "measured"):
                assert s.ref, (st.name, name)


def test_fr2_numerology():
    st = FR2_NR400
    assert st.n_active_tones == 3168                     # 264 RB x 12
    assert st.fs_hz == 4096 * 120e3 * 4                   # 1.96608 GS/s
    assert st.fs_hz >= 4.9 * st.bandwidth_hz.value        # aclr_multi needs it for ACLR2
    assert 0.014 < st.bandwidth_hz.value / st.carrier_hz.value < 0.015   # 1.43 % relative BW


def test_fr2_waveform_shape():
    wf = FR2_NR400.make_waveform(n_symbols=2, seed=0)
    assert wf.fs == FR2_NR400.fs_hz and wf.bw == 400e6 and wf.kind == "ofdm"
    assert wf.meta["scs_hz"] == 120e3
    assert abs(np.mean(np.abs(wf.x) ** 2) - 1.0) < 1e-9     # unit average power
    # occupied bandwidth ~ 3168 x 120 kHz = 380 MHz: the band edge tones exist
    spec = np.abs(np.fft.fftshift(np.fft.fft(wf.x))) ** 2
    f = np.fft.fftshift(np.fft.fftfreq(wf.n, 1 / wf.fs))
    inband = spec[np.abs(f) < 185e6].mean()
    guard = spec[(np.abs(f) > 200e6) & (np.abs(f) < 240e6)].mean()
    assert 10 * np.log10(inband / guard) > 40


def test_sub6_anchor_is_polartx_verbatim():
    from arraytx.vendor.polartx import nr_dtc
    p = nr_dtc()                            # polar_tx FR1 default
    wf_ref = p.make_waveform(n_symbols=2, seed=0)
    wf = SUB6_NR100.make_waveform(n_symbols=2, seed=0)
    assert np.array_equal(wf.x, wf_ref.x) and wf.fs == wf_ref.fs


def test_unknown_standard():
    with pytest.raises(KeyError):
        get_standard("fr3")


def test_sourced_requires_ref_for_survey():
    with pytest.raises(ValueError):
        Sourced(1.0, "survey")
    with pytest.raises(ValueError):
        Sourced(1.0, "guess")
