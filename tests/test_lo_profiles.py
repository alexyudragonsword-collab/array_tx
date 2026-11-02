"""The shared LO from real pll_simulator clock profiles (bundled)."""
import numpy as np
import pytest

from arraytx import ArraySim, config_from_dict, load_config
from arraytx.lo import ClockProfileLO, list_bundled, resolve_profile


def test_all_bundled_profiles_are_pllsim_exports_at_the_pin():
    names = list_bundled()
    assert len(names) == 18
    for n in names:
        lo = ClockProfileLO(f"bundled:{n}", fout_hz=28e9)
        assert "commit 00e48a2" in lo.source and f"preset {n}" in lo.source
        assert lo.f_grid[0] == 100.0 and abs(lo.f_grid[-1] - lo.f0_hz / 2) < 1.0
        f = np.geomspace(1e2, lo.f0_hz / 2 * 0.99, 50)     # inside the profile
        s = lo.psd(f)
        assert np.all(np.isfinite(s)) and np.all(s > 0)
        assert lo.psd(np.array([lo.f0_hz]))[0] == 0.0


def test_scaling_to_the_carrier_is_20log_per_ratio():
    raw = ClockProfileLO("bundled:spll_100m_8g", fout_hz=8e9)
    at28 = ClockProfileLO("bundled:spll_100m_8g", fout_hz=28e9)
    f = np.geomspace(1e3, 1e8, 20)
    assert np.allclose(at28.psd(f) / raw.psd(f), (28 / 8) ** 2)
    assert raw.scale == 1.0 and abs(10 * np.log10(at28.scale) - 10.88) < 0.01
    keep = ClockProfileLO("bundled:spll_100m_8g", fout_hz=28e9, scale_to_fout=False)
    assert np.array_equal(keep.psd(f), raw.psd(f))


def test_rms_phase_helper():
    lo = ClockProfileLO("bundled:adpll_100m_10g", fout_hz=28e9)
    full = lo.rms_phase_rad(1e2, 1e9)
    flat = lo.rms_phase_rad(1e2, 1e9, flatten_below_hz=400e3)
    narrow = lo.rms_phase_rad(1e6, 1e9)
    assert full > narrow > 0 and flat > 0
    assert lo.rms_phase_rad(6e9, 7e9) == 0.0         # beyond the profile (f0/2 = 5.025 GHz)
    assert 0 < lo.integrated_jitter_s(1e3, 1e8) < 1e-11


def test_resolve_and_config_paths(tmp_path):
    with pytest.raises(FileNotFoundError, match="bundled"):
        ClockProfileLO("bundled:nope")
    assert resolve_profile("x.yaml", base_dir="/a/b") == "/a/b/x.yaml"
    assert resolve_profile("/abs/x.yaml", base_dir="/a/b") == "/abs/x.yaml"
    cfgfile = tmp_path / "c.yaml"
    cfgfile.write_text("arraytx_config: 1\nelement:\n  lo:\n    clock_profile: sub/prof.yaml\n")
    cfg = load_config(cfgfile)
    assert cfg.element.lo.clock_profile == str((tmp_path / "sub/prof.yaml").resolve())
    cfgfile.write_text("arraytx_config: 1\nelement:\n  lo:\n    clock_profile: 'bundled:ilcm_250m_12g'\n")
    assert load_config(cfgfile).element.lo.clock_profile == "bundled:ilcm_250m_12g"


def test_evm_follows_the_in_band_lo_phase_error():
    """With an ideal PA the FR2 EVM is LO-limited (cairn/LOG.md): three
    profiles with widely different IN-BAND rms phase (100 Hz .. BW/2, flat
    below the loop BW) order the OTA EVM the same way.  Integrating to fs/2
    would not: the ILCM's noise is far out, where it costs ACLR, not EVM."""
    out = []
    for name in ("ilcm_250m_12g", "adpll_100m_10g", "bench_dartizio23_adpllbb_500m_9p2515g"):
        cfg = config_from_dict({"element": {"errors": {"enabled": False}, "pa": {"amam": "ideal", "ampm_deg_at_fs": 0.0},
                                            "lo": {"clock_profile": f"bundled:{name}"}}})
        sim = ArraySim(cfg)
        lo = sim.elements[0].tx.phasemod.cfg.lo_pn
        assert isinstance(lo, ClockProfileLO) and lo.fout_hz == 28e9
        r = sim.run(30.0, "none")
        out.append((lo.rms_phase_rad(1e2, sim.wf.bw / 2, flatten_below_hz=cfg.element.lo.loop_bw_hz), r.beam.evm_db, name))
    out.sort()
    assert max(out)[0] / min(out)[0] > 2.0, "fixture profiles should differ a lot"
    evms = [e for _, e, _ in out]
    assert evms == sorted(evms), out


# ------------------------------------------------------------- spurs (B6)
PROFILE = """f0_hz: 7000000000.0
f_hz: [100.0, 1000.0, 10000.0, 100000.0, 1000000.0, 10000000.0, 100000000.0, 3500000000.0]
l_dbc_hz: [-60.0, -80.0, -95.0, -105.0, -115.0, -135.0, -150.0, -155.0]
spurs: {spurs}
source: "arraytx test fixture (synthetic)"
"""


def _write_profile(tmp_path, name, spurs):
    rows = "[]" if not spurs else "\n" + "\n".join(f"  - {{f_hz: {f}, dbc: {d}}}" for f, d in spurs)
    p = tmp_path / f"{name}.yaml"
    p.write_text(PROFILE.format(spurs=rows))
    return str(p)


def test_spur_level_convention_and_carrier_scaling(tmp_path):
    """dbc is the single-sideband level of a sinusoidal PM: peak phase
    a = 2 * 10^(dbc/20) at the profile's f0, times fout/f0 at the carrier
    (the offset does not move).  Synthesise one spur and read the sideband
    back off the spectrum."""
    from arraytx.lo import spur_phase_rad
    fs, n = 1e8, 1 << 16
    f_spur = 50 * fs / n                                         # on-bin, 76.3 kHz
    path = _write_profile(tmp_path, "one", [(f_spur, -40.0)])
    lo = ClockProfileLO(path, fout_hz=7e9)
    (f, a), = lo.spurs_at_carrier()
    assert f == f_spur and abs(a - 2 * 10 ** (-40 / 20)) < 1e-15
    t = np.arange(n) / fs
    x = np.exp(1j * spur_phase_rad(t, [(f, a)], [0.3]))
    X = 20 * np.log10(np.abs(np.fft.fft(x)) / n)
    assert abs(X[50] - (-40.0)) < 0.1 and abs(X[-50] - (-40.0)) < 0.1 and X[0] > -0.01
    at28 = ClockProfileLO(path, fout_hz=28e9)
    (f28, a28), = at28.spurs_at_carrier()
    assert f28 == f_spur and abs(20 * np.log10(a28 / a) - 20 * np.log10(28 / 7)) < 1e-9
    assert abs(at28.spur_rms_rad() - a28 / np.sqrt(2)) < 1e-15 and at28.spur_rms_rad(1e6, 2e6) == 0.0


def test_spur_rotation_of_the_output_equals_an_lo_phase_added_at_the_drive(tmp_path):
    """The chain applies the spur as exp(j phi(t)) on its output.  Driving
    the SAME chain (spurs off) with x * exp(j phi) instead -- the phase
    entering through the DTC -- gives the same signal to the DTC's
    re-quantisation of a different phase sequence (10-bit DTC: ~ -50 dB)."""
    path = _write_profile(tmp_path, "two", [(23040.0, -52.0), (4805760.0, -58.5)])
    off = {"element": {"errors": {"enabled": False}, "lo": {"clock_profile": path}}}
    on = ArraySim(config_from_dict(off))
    el_on = on.elements[0]
    assert len(el_on.spurs) == 2 and el_on.run(on.x, on.wf).info["element"]["lo_spurs"] == 2
    cfg_off = config_from_dict({"element": {"errors": {"enabled": False},
                                            "lo": {"clock_profile": path, "spurs": False}}})
    el_off = ArraySim(cfg_off).elements[0]
    assert el_off.spurs == []
    from arraytx.lo import spur_phase_rad
    from arraytx.vendor.polartx.waveforms.base import Waveform
    from dataclasses import replace
    t = np.arange(on.x.size) / on.fs
    phi = spur_phase_rad(t, [(f, a) for f, a, _ in el_on.spurs], [p for _, _, p in el_on.spurs])
    y_on = el_on.run(on.x, on.wf).y
    y_rot = el_off.run(on.x * np.exp(1j * phi), replace(on.wf, x=on.x * np.exp(1j * phi))).y
    rel = 20 * np.log10(np.linalg.norm(y_on - y_rot) / np.linalg.norm(y_on))
    assert rel < -40.0, rel
    assert isinstance(on.wf, Waveform)
    # and the two are far from each other without the rotation: the spurs are not a no-op
    y_plain = el_off.run(on.x, on.wf).y
    assert 20 * np.log10(np.linalg.norm(y_on - y_plain) / np.linalg.norm(y_on)) > -45.0


def test_spur_phases_are_drawn_then_zeroed_and_shared_with_the_lo(tmp_path):
    path = _write_profile(tmp_path, "three", [(62400.0, -65.6), (1e6, -90.0)])
    none = _write_profile(tmp_path, "none", [])
    base = {"array": {"n_elements": 3}, "element": {"lo": {"clock_profile": path}}}
    shared = ArraySim(config_from_dict(base))
    assert shared.elements[0].spurs == shared.elements[1].spurs == shared.elements[2].spurs
    own = ArraySim(config_from_dict({"array": {"n_elements": 3},
                                     "element": {"lo": {"clock_profile": path, "shared": False}}}))
    assert own.elements[0].spurs != own.elements[1].spurs
    assert [f for f, _, _ in own.elements[0].spurs] == [62400.0, 1e6]
    # switch off: the element equals one built from a profile without spurs, bit for bit
    off = ArraySim(config_from_dict({"array": {"n_elements": 3},
                                     "element": {"lo": {"clock_profile": path, "spurs": False}}}))
    ref = ArraySim(config_from_dict({"array": {"n_elements": 3}, "element": {"lo": {"clock_profile": none}}}))
    assert off.elements[1].spurs == [] and ref.elements[1].spurs == []
    assert np.array_equal(off.run(30.0, "none").ys, ref.run(30.0, "none").ys)
    # and the other draws never moved: errors are the same with spurs on or off
    assert shared.elements[2].errors == off.elements[2].errors
