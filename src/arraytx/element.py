"""One array element = one polar_tx chain plus its element-level errors.

What this module adds on top of polar_tx:

* the chain is built from the config's standard and PA block through
  polar_tx's own preset factories (``nr_dtc``, ``wifi_outphasing``,
  ``wifi_rfdac``), never re-implemented;
* the CFR is taken OUT of the chain (``cfr_papr_db=None``) and applied once
  to the common signal in ``sim.py``, so a DPD can sit between CFR and the
  element — same function, same arguments, same order as polar_tx, hence
  bit-identical when there is no DPD;
* the chain's envelope full scale is PINNED (``fs_scale_fixed``) to the
  value polar_tx would have computed for the undistorted drive.  polar_tx
  re-normalises the envelope to its peak on every run; a DPD expands peaks,
  so without the pin every DPD run would move the operating point;
* per-element gain / phase / delay errors and a PA deviation are drawn from
  the element's own seed streams (invariant 5).  When ``errors.enabled`` is
  false they are still drawn, then zeroed — the draw order never changes;
* the LO is shared across elements through ``DTCPMConfig.lo_pn_seed``.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from .config import ArrayConfig
from .lo import ClockProfileLO
from .seeds import SeedTree
from .standards import Standard
from .vendor.polartx import DPAConfig
from .vendor.polartx.impairments import fractional_delay
from .vendor.polartx.polar.split import polar_split
from .vendor.polartx.presets import wifi_outphasing, wifi_rfdac
from .vendor.polartx.rfdac import RFDACConfig
from .vendor.polartx.vendor.pllsim.blocks.oscillator import OscConfig
from .vendor.polartx.waveforms.base import Waveform

TOPOLOGIES = ("polar", "outphasing", "rfdac")


@dataclass(frozen=True)
class ElementErrors:
    """The drawn (and possibly zeroed) element-level errors."""
    gain_db: float
    phase_deg: float
    delay_s: float
    pa_dev: float        # relative deviation of the PA knee / AM-PM scale

    @property
    def is_identity(self) -> bool:
        return self.gain_db == 0.0 and self.phase_deg == 0.0 and self.delay_s == 0.0


def draw_element_errors(cfg: ArrayConfig, tree: SeedTree, k: int) -> ElementErrors:
    """Draw element ``k``'s errors from its own streams; zero them if the
    switch is off (draw-then-zero keeps every other stream untouched — and
    these streams are independent anyway)."""
    e = cfg.element.errors
    g = float(tree.rng("gain", k).standard_normal()) * e.gain_sigma_db
    p = float(tree.rng("phase", k).standard_normal()) * e.phase_sigma_deg
    d = float(tree.rng("delay", k).standard_normal()) * e.delay_sigma_ps * 1e-12
    v = float(tree.rng("pa_dev", k).standard_normal()) * e.pa_dev_sigma
    if not e.enabled:
        g, p, d, v = 0.0, 0.0, 0.0, 0.0
    return ElementErrors(g, p, d, v)


def dpa_config(cfg: ArrayConfig, err: ElementErrors, mismatch_seed: int) -> DPAConfig:
    """polar_tx DPAConfig for one element: the config's PA with this
    element's deviation folded into the compression knee and AM-PM scale."""
    pa = cfg.element.pa
    dev = 1.0 + err.pa_dev
    if pa.amam == "ideal":
        amam: Any = "ideal"
    elif pa.amam == "rapp":
        amam = ("rapp", float(pa.rapp_p), float(pa.rapp_drive) * dev)
    else:
        raise ValueError(f"unknown amam {pa.amam!r}")
    ampm = () if pa.ampm_deg_at_fs == 0.0 else (0.0, 0.0, float(pa.ampm_deg_at_fs) * dev)
    return DPAConfig(n_bits=pa.n_bits, n_thermo=pa.n_thermo,
                     sigma_cell=pa.sigma_cell, amam=amam,
                     ampm_deg_poly=ampm, seed=int(mismatch_seed))


def fr2_lo_like_polartx(fout: float) -> OscConfig:
    """polar_tx nr_dtc's FR2 LO (its presets.py), for the topologies whose
    factories do not know about FR2 (outphasing / rfdac go via wifi_dtc)."""
    return OscConfig(f0=fout, gain=1.0, pn_dbchz=-100.0, pn_foffset=1e6,
                     pn_f1f3=300e3, pn_floor_dbchz=-140.0)


def reference_full_scale(tx: Any, topology: str, x: np.ndarray, wf: Waveform) -> float:
    """The envelope full scale polar_tx would pin for drive ``x`` on this run
    — the same expression as ``PolarTX.run`` (chain.py), evaluated once on
    the undistorted common drive and then frozen for every element and
    every DPD scheme."""
    if topology == "polar":
        c = tx.cfg
        env, _, _ = polar_split(x, c.env_floor, phase_slew_max_hz=c.phase_slew_max_hz,
                                fs=wf.fs, phase_interp_win=c.phase_interp_win,
                                phase_interp=c.phase_interp)
        return c.env_headroom * float(env.max())
    if topology == "outphasing":
        return float(np.abs(x).max())            # OutphasingTX.a_max
    # rfdac: CartesianTX's per-axis full scale (polar_tx@008cc90 reads
    # fs_scale_fixed, so this is pinnable like the others)
    return float(max(np.abs(x.real).max(), np.abs(x.imag).max()))


class ElementChain:
    """Element ``k``: a polar_tx TX built from the config, pinned and seeded."""

    def __init__(self, cfg: ArrayConfig, standard: Standard, tree: SeedTree, k: int,
                 *, fs_scale: float | None, lo_pn_seed: int | None,
                 lo_obj: ClockProfileLO | None):
        self.k = k
        self.cfg = cfg
        self.topology = cfg.element.topology
        if self.topology not in TOPOLOGIES:
            raise ValueError(f"unknown topology {self.topology!r}")
        self.errors = draw_element_errors(cfg, tree, k)
        mismatch_seed = tree.int_seed("dpa_mismatch", k) if cfg.element.errors.enabled else 0
        self.dpa_cfg = dpa_config(cfg, self.errors, mismatch_seed)
        self.run_seed = tree.int_seed("run", k)
        self.lo_pn_seed = lo_pn_seed
        self.fs_scale = fs_scale

        kw: dict[str, Any] = dict(cfr_papr_db=None, dpa=self.dpa_cfg,
                                  lo_loop_bw=cfg.element.lo.loop_bw_hz)
        if lo_obj is not None:
            kw["lo_pn"] = lo_obj
        if self.topology == "polar":
            self.preset = standard.preset(**kw)
            self.tx = self.preset.tx
        else:
            fout = float(standard.carrier_hz.value)
            kw2 = dict(kw, bw=float(standard.bandwidth_hz.value), qam=int(standard.qam.value),
                       fout=fout, oversampling=int(standard.oversampling.value))
            if lo_obj is None and not standard.polartx_native:
                kw2["lo_pn"] = fr2_lo_like_polartx(fout)
            if self.topology == "outphasing":
                self.preset = wifi_outphasing(**kw2)
            else:
                # the RF-DAC is the element's array: the config's PA block
                # (bits, thermometer MSBs, mismatch) and THIS element's
                # mismatch seed, on the plan's LO.  wifi_rfdac's own default
                # would give every element the same seed-0 array.
                probe = wifi_rfdac(**kw2)
                pm_cfg = probe.polar_tx.phasemod.cfg
                pa = cfg.element.pa
                kw2["rfdac"] = RFDACConfig(
                    n_bits=pa.n_bits, n_thermo=pa.n_thermo, sigma_cell=pa.sigma_cell,
                    seed=int(mismatch_seed), jitter_rms_s=pm_cfg.jitter_rms_s,
                    fout=pm_cfg.fout, lo_pn=pm_cfg.lo_pn, lo_loop_bw=pm_cfg.lo_loop_bw)
                self.preset = wifi_rfdac(**kw2)
            self.tx = self.preset.tx
        self._pin()

    # ------------------------------------------------------------ wiring
    def _pin(self) -> None:
        """Freeze the full scale and set the LO seed on the chain in place."""
        tx = self.tx
        if self.fs_scale is not None:
            base = tx.tx if self.topology == "outphasing" else tx      # OutphasingTX wraps a PolarTX
            base.cfg = replace(base.cfg, fs_scale_fixed=float(self.fs_scale))
        if self.lo_pn_seed is not None and self.topology == "polar":
            pm: Any = copy.copy(tx.phasemod)
            if hasattr(pm, "cfg") and hasattr(pm.cfg, "lo_pn_seed"):
                pm.cfg = replace(pm.cfg, lo_pn_seed=int(self.lo_pn_seed))
                tx.phasemod = pm
        # outphasing pins its own branches to the run seed (polar_tx), and the
        # RF-DAC's LO lives on its own config: both are reported, not forced
        self.shared_lo_effective = (self.lo_pn_seed is not None and self.topology == "polar")

    @property
    def engine(self) -> str:
        """The phase-modulation engine name as the run diagnostics report it
        (``dtc_openloop`` / ``response`` / ``event``), or ``rfdac``."""
        if self.topology == "rfdac":
            return "rfdac"
        pm = getattr(self.tx, "phasemod", None) or getattr(getattr(self.tx, "tx", None), "phasemod", None)
        mode = getattr(getattr(pm, "cfg", None), "mode", None)
        if mode:
            return str(mode)
        return "dtc_openloop" if type(pm).__name__ == "DTCPhaseModulator" else type(pm).__name__

    @property
    def pa_deviation_effective(self) -> bool:
        """The PA deviation applies to the DPA's AM-AM / AM-PM; the RF-DAC has
        neither, so for rfdac the draw is made (stream stability) but inert."""
        return self.topology != "rfdac"

    # --------------------------------------------------------------- run
    def run(self, x_drive: np.ndarray, wf: Waveform, *, noise: bool = True) -> "ElementResult":
        """Run the chain on this element's drive and apply its errors at the
        PA output (an analog path error: amplitude, phase, delay)."""
        wf_k = wf if x_drive is wf.x else replace(wf, x=x_drive)
        r = self.tx.run(wf_k, noise=noise, seed=self.run_seed)
        y = r.y
        e = self.errors
        if e.gain_db != 0.0 or e.phase_deg != 0.0:
            y = y * (10.0 ** (e.gain_db / 20.0) * np.exp(1j * np.deg2rad(e.phase_deg)))
        if e.delay_s != 0.0:
            y = fractional_delay(y, e.delay_s * wf.fs)
        info = dict(r.info)
        info["element"] = {"k": self.k, "errors": e, "run_seed": self.run_seed,
                           "lo_pn_seed": self.lo_pn_seed, "fs_scale": self.fs_scale,
                           "dpa_mismatch_seed": self.dpa_cfg.seed,
                           "pa_deviation_effective": self.pa_deviation_effective,
                           "shared_lo_effective": self.shared_lo_effective}
        return ElementResult(y=y, info=info, raw=r)


@dataclass
class ElementResult:
    y: np.ndarray            # conducted PA output (diagnostic port), complex baseband @ wf.fs
    info: dict
    raw: Any                 # the polar_tx result object

    @property
    def phasemod_mode(self) -> str:
        pm = self.info.get("phasemod")
        if isinstance(pm, tuple):
            pm = pm[0]
        return (pm or {}).get("mode", "n/a") if isinstance(pm, dict) else "n/a"


def build_elements(cfg: ArrayConfig, standard: Standard, tree: SeedTree,
                   x_ref: np.ndarray, wf: Waveform) -> list[ElementChain]:
    """All elements, sharing one pinned full scale (from the undistorted
    common drive) and, if configured, one LO."""
    lo_obj = None
    if cfg.element.lo.clock_profile:
        lo_obj = ClockProfileLO(cfg.element.lo.clock_profile, fout_hz=float(standard.carrier_hz.value))
    lo_seed = tree.int_seed("lo") if cfg.element.lo.shared else None
    # full scale: build element 0's chain unpinned just to read its ChainConfig
    probe = ElementChain(cfg, standard, tree, 0, fs_scale=None, lo_pn_seed=None, lo_obj=lo_obj)
    fs_scale = reference_full_scale(probe.tx, cfg.element.topology, x_ref, wf)
    if np.isnan(fs_scale):
        fs_scale = None
    return [ElementChain(cfg, standard, tree, k, fs_scale=fs_scale, lo_pn_seed=lo_seed, lo_obj=lo_obj)
            for k in range(cfg.array.n_elements)]
