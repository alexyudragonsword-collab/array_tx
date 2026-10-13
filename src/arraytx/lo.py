"""The shared LO: one phase-noise profile for every element.

polar_tx's DTC phase modulator draws its LO phase noise from
``DTCPMConfig.lo_pn``, any object whose ``.leeson(name)`` returns something
with ``.psd(f)`` (double-sided S_phi in rad^2/Hz; polar_tx passes a pllsim
``OscConfig``).  :class:`ClockProfileLO` duck-types that interface from a
pll_simulator clock profile (``export/clock_profile.py``: single-sideband
L(f) in dBc/Hz on a log grid), so a measured or exported PLL profile can
drive every element without touching polar_tx.

Only the L(f) curve is used; the profile's discrete ``spurs`` entries are
read but not injected (ROADMAP B6).

Sharing itself is polar_tx's ``lo_pn_seed`` mechanism: every element's
modulator gets the SAME integer, so they draw the identical LO sample while
their DTC edge jitter stays per element (see ``element.py``).
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np

from .vendor.polartx.vendor.pllsim.export.clock_profile import read_clock_profile


BUNDLED_PREFIX = "bundled:"


def bundled_dir() -> Path:
    return Path(str(resources.files("arraytx.data").joinpath("clock_profiles")))


def list_bundled() -> list[str]:
    """Names of the clock profiles shipped with the package."""
    return sorted(p.stem for p in bundled_dir().glob("*.yaml"))


def resolve_profile(spec: str, *, base_dir: str | Path | None = None) -> str:
    """``bundled:<name>`` -> the packaged file; a relative path -> relative to
    ``base_dir`` (the config file's directory) when given."""
    if spec.startswith(BUNDLED_PREFIX):
        name = spec[len(BUNDLED_PREFIX):]
        path = bundled_dir() / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"no bundled clock profile {name!r}; one of {list_bundled()}")
        return str(path)
    path = Path(spec)
    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir) / path
    return str(path)


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
        self.path = resolve_profile(str(self.path))
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

    def rms_phase_rad(self, f_lo: float, f_hi: float, n: int = 4000, *,
                      flatten_below_hz: float | None = None) -> float:
        """rms phase error at the OUTPUT carrier (scaled) between two offsets,
        from the double-sided S_phi.  ``flatten_below_hz`` applies the
        locked-LO approximation polar_tx's DTC uses (PSD held flat below the
        loop bandwidth), so the number matches what the chain injects."""
        f = np.geomspace(max(f_lo, self.f_grid[0]), min(f_hi, self.f0_hz / 2), n)
        if f.size < 2 or f[-1] <= f[0]:
            return 0.0
        fe = f if flatten_below_hz is None else np.maximum(f, flatten_below_hz)
        trap = getattr(np, "trapezoid", None) or np.trapz    # numpy 1.x has only trapz
        return float(np.sqrt(trap(self.psd(fe), f)))

    def integrated_jitter_s(self, f_lo: float, f_hi: float, n: int = 4000) -> float:
        """rms jitter of the PROFILE (at its own f0) between two offsets."""
        return self.rms_phase_rad(f_lo, f_hi, n) / np.sqrt(self.scale) / (2 * np.pi * self.f0_hz)
