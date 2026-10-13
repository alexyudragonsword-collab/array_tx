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
