"""Load modulation of the digital PA (ROADMAP A2; model in
``cairn/load-pull-proposal.md``).

Milestone 1's coupling is a linear leakage r_k = y_k + sum_j S_kj y_j, and a
phase-covariant DPA turns that into a linear combination of the elements'
nonlinear outputs -- which is why per-element and array DPD could not be
told apart.  For the coupled wave to reach the NONLINEARITY it has to move
the PA's operating point.  First-order, voltage-mode reading:

* the active reflection coefficient at port k is
  Gamma_k(t) = sum_j S_kj (*) y_j / y_k -- the leakage ``apply_coupling``
  already computes, divided by the element's own wave;
* a switched-capacitor / class-D DPA is a voltage source whose swing is
  limited by its supply rail, and the swing at the port is v_fwd (1 +
  Gamma).  So compression acts on the TOTAL swing: the Rapp law is fed
  ``drive * |1 + kappa_a Gamma| * r`` and the result is divided by
  |1 + kappa_a Gamma| again, because ``apply_coupling`` adds the coupled
  wave afterwards.  In the linear region this cancels (the gain does not
  move); at the knee the compression starts earlier when |1 + Gamma| > 1.
  AM-PM is read at the same total swing, ``r * |1 + kappa_p Gamma|``.
  kappa = 1 is the ideal voltage-source reading (source: assumed); a
  measured load-pull table would replace this mapping (source: measured).

An ``"ideal"`` AM-AM has no knee, so it has no load dependence here, and
the RF-DAC (no compression) and the outphasing combiner are not touched
(``element.py`` reports the switch as inert for them).

``LoadPulledDPA`` is an arraytx-side subclass of polar_tx's ``DPA``: the
chain keeps calling ``dpa(code, phase)``; ``set_load(gamma)`` (one complex
value per sample, or None) is what ``sim.ArraySim.radiate`` sets between
its fixed-point rounds.  With no load set it IS the vendored DPA, bit for
bit (the table path is untouched).
"""
from __future__ import annotations

import numpy as np

from .vendor.polartx.dpa.characteristics import ampm_curve
from .vendor.polartx.dpa.dpa import DPA, DPAConfig
from .vendor.polartx.dpa.mismatch import code_amplitude_table


def amam_loaded(amam, r: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Normalised AM-AM of the FORWARD wave under a load factor
    g = |1 + kappa Gamma| per sample: the device saturates on g * r, and
    the forward wave is that output divided by g.  g = 1 reproduces
    ``characteristics.amam_curve`` (same expression, same order)."""
    r = np.asarray(r, dtype=float)
    g = np.asarray(g, dtype=float)
    if amam == "ideal":
        return r
    kind = amam[0]
    if kind == "rapp":
        _, p, drive = amam
        x = drive * (g * r)
        y = x / (1.0 + x ** (2.0 * p)) ** (1.0 / (2.0 * p))
        y_fs = drive / (1.0 + drive ** (2.0 * p)) ** (1.0 / (2.0 * p))
        return y / y_fs / g
    if kind == "lut":
        _, r_in, r_out = amam
        r_in = np.asarray(r_in, float)
        r_out = np.asarray(r_out, float)
        y = np.interp(g * r, r_in, r_out)
        return y / np.interp(1.0, r_in, r_out) / g
    raise ValueError(f"unknown amam spec: {amam!r}")


class LoadPulledDPA(DPA):
    """polar_tx's DPA with a per-sample load factor on its nonlinearity."""

    def __init__(self, cfg: DPAConfig, kappa_amam: float = 1.0, kappa_ampm: float = 1.0):
        super().__init__(cfg)
        # the same normalised code amplitudes the base class built its
        # tables from (same seed, same draw)
        rng = np.random.default_rng(cfg.seed)
        raw = code_amplitude_table(cfg.n_bits, min(cfg.n_thermo, cfg.n_bits), cfg.sigma_cell, cfg.gradient, rng)
        self.r = raw / raw[-1]
        self.kappa_amam = float(kappa_amam)
        self.kappa_ampm = float(kappa_ampm)
        self.gamma: np.ndarray | None = None

    def set_load(self, gamma) -> None:
        """Active reflection coefficient per sample (complex), or None for
        the matched load (the plain table path)."""
        self.gamma = None if gamma is None else np.asarray(gamma, dtype=complex)

    @property
    def load_factors(self) -> tuple[np.ndarray, np.ndarray] | None:
        if self.gamma is None:
            return None
        return np.abs(1.0 + self.kappa_amam * self.gamma), np.abs(1.0 + self.kappa_ampm * self.gamma)

    def __call__(self, code: np.ndarray, phase: np.ndarray) -> np.ndarray:
        if self.gamma is None:
            return super().__call__(code, phase)
        code = np.asarray(code, dtype=np.int64)
        if self.gamma.shape[0] != code.shape[0]:
            raise ValueError(f"load has {self.gamma.shape[0]} samples, the code stream {code.shape[0]}")
        r = self.r[code]
        ga, gp = self.load_factors
        amp = amam_loaded(self.cfg.amam, r, ga)
        r_pm = r * gp
        if self.cfg.ampm_lut is not None:
            r_in, deg = self.cfg.ampm_lut
            ph = np.deg2rad(np.interp(r_pm, np.asarray(r_in, float), np.asarray(deg, float)))
        else:
            ph = ampm_curve(self.cfg.ampm_deg_poly, r_pm)
        return amp * np.exp(1j * (np.asarray(phase, float) + ph))


def active_reflection(ys: np.ndarray, rs: np.ndarray, floors, gamma_max: float) -> np.ndarray:
    """Gamma_k(t) = (r_k - y_k) / y_k per element and sample, with the two
    guards: 0 where |y_k| is below the element's floor (the ratio means
    nothing near an envelope zero), magnitude clipped to ``gamma_max``."""
    ys = np.asarray(ys)
    leak = np.asarray(rs) - ys
    mag = np.abs(ys)
    floors = np.asarray(floors, dtype=float).reshape(-1, 1)
    safe = np.where(mag > floors, ys, 1.0)
    gamma = np.where(mag > floors, leak / safe, 0.0 + 0.0j)
    g = np.abs(gamma)
    over = g > gamma_max
    gamma = np.where(over, gamma * (gamma_max / np.where(over, g, 1.0)), gamma)
    return gamma
