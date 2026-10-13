"""The shared LO: one phase-noise profile for every element.

polar_tx's DTC phase modulator draws its LO phase noise from
``DTCPMConfig.lo_pn``, any object whose ``.leeson(name)`` returns something
with ``.psd(f)`` (double-sided S_phi in rad^2/Hz; polar_tx passes a pllsim
``OscConfig``).  :class:`ClockProfileLO` duck-types that interface from a
pll_simulator clock profile (``export/clock_profile.py``: single-sideband
L(f) in dBc/Hz on a log grid), so a measured or exported PLL profile can
drive every element without touching polar_tx.

Sharing itself is polar_tx's ``lo_pn_seed`` mechanism: every element's
modulator gets the SAME integer, so they draw the identical LO sample while
their DTC edge jitter stays per element (see ``element.py``).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .vendor.polartx.vendor.pllsim.export.clock_profile import read_clock_profile


@dataclass
class ClockProfileLO:
    """A pll_simulator clock profile as a polar_tx ``lo_pn`` object.

    ``fout_hz`` is the carrier the LO actually runs at; when it differs from
    the profile's ``f0_hz`` the profile is treated as the reference of an
    ideal multiplier/divider and S_phi is scaled by ``(fout/f0)^2``
    (20 log10 per frequency ratio) — the usual way a sub-6 PLL profile is
    read at a mmWave carrier.  ``scale_to_fout=False`` uses it as is.
    """
    path: str
    fout_hz: float | None = None
    scale_to_fout: bool = True

    def __post_init__(self):
        d = read_clock_profile(self.path)
        self.f0_hz = float(d["f0_hz"])
        self.f_grid = np.asarray(d["f_hz"], dtype=float)
        self.l_dbc = np.asarray(d["l_dbc_hz"], dtype=float)
        self.spurs = list(d["spurs"])
        self.source = d["source"]
        if self.f_grid.size < 2 or np.any(np.diff(self.f_grid) <= 0):
            raise ValueError(f"{self.path}: f_hz must be increasing")
        self.scale = 1.0
        if self.scale_to_fout and self.fout_hz is not None:
            self.scale = (float(self.fout_hz) / self.f0_hz) ** 2

    # polar_tx / pllsim duck typing -------------------------------------
    def leeson(self, name: str = "lo") -> "ClockProfileLO":
        return self

    def psd(self, f) -> np.ndarray:
        """Double-sided S_phi(f) [rad^2/Hz] = 2 * 10^(L(f)/10), interpolated in
        (log f, dB); held flat below the grid, zero above the profile's f0/2
        (the profile does not describe anything beyond its Nyquist)."""
        f = np.asarray(f, dtype=float)
        fl = np.log10(np.maximum(f, self.f_grid[0]))
        l_db = np.interp(fl, np.log10(self.f_grid), self.l_dbc)
        s = 2.0 * 10.0 ** (l_db / 10.0) * self.scale
        return np.where(f > self.f0_hz / 2.0, 0.0, s)

    def integrated_jitter_s(self, f_lo: float, f_hi: float, n: int = 4000) -> float:
        """rms jitter from the profile between two offsets (diagnostic)."""
        f = np.geomspace(max(f_lo, self.f_grid[0]), min(f_hi, self.f0_hz / 2), n)
        var = np.trapezoid(self.psd(f) / self.scale, f)      # rad^2, at f0
        return float(np.sqrt(var) / (2 * np.pi * self.f0_hz))
