"""Array geometry: a uniform linear array with its phase centre at the
middle, so a far-field observation at any angle carries no net delay.

The element pattern is an input, not a computation (ROADMAP D: no EM here):
``isotropic`` (source: assumed) or ``cos`` (a cos(theta) element factor,
the textbook patch-like envelope; source: assumed).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

C0 = 299_792_458.0   # m/s, exact by definition of the metre


@dataclass(frozen=True)
class LinearArray:
    n: int
    spacing_lambda: float
    f0_hz: float
    element_pattern: str = "isotropic"

    def __post_init__(self):
        if self.n < 1:
            raise ValueError("n must be >= 1")
        if self.element_pattern not in ("isotropic", "cos"):
            raise ValueError(f"unknown element pattern {self.element_pattern!r}")

    @property
    def wavelength_m(self) -> float:
        return C0 / self.f0_hz

    @property
    def spacing_m(self) -> float:
        return self.spacing_lambda * self.wavelength_m

    @property
    def positions_m(self) -> np.ndarray:
        """Element x positions, centred: (k - (n-1)/2) * d.  For n = 1 the
        single element sits at exactly 0.0."""
        k = np.arange(self.n, dtype=float)
        return (k - (self.n - 1) / 2.0) * self.spacing_m

    def delays_s(self, theta_deg: float) -> np.ndarray:
        """Arrival-time ADVANCE of element k's wave at a far-field observer in
        direction theta (from broadside, positive towards +x): the path is
        shorter by x_k sin(theta), so tau_k = x_k sin(theta) / c0 and the
        observer sees r_k(t + tau_k).  Exactly 0.0 at broadside."""
        s = np.sin(np.deg2rad(theta_deg))
        if s == 0.0:
            return np.zeros(self.n)
        return self.positions_m * s / C0

    def element_gain(self, theta_deg: float) -> float:
        if self.element_pattern == "isotropic":
            return 1.0
        return float(max(np.cos(np.deg2rad(theta_deg)), 0.0))
