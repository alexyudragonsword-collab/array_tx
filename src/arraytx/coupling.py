"""Mutual coupling as a complex N x N matrix that enters the CHAIN
(invariant 3), from one of three sources that all produce the same object
and all go through the one ``apply_coupling``.

Model (milestone 1: linear leakage)
-----------------------------------
radiated_k(f) = y_k(f) + sum_{j != k} S_kj(f) * y_j(f)

* ``y_j`` is element j's PA forward output (conducted port).
* ``S_kj(f)`` is the coupled transfer from port j to port k at RF frequency
  f; the diagonal (return loss) is carried but NOT applied — a load
  mismatch needs a PA model with load dependence (ROADMAP A2).
* S == 0 (all off-diagonal exactly zero) returns the input array object
  itself, so one element with no coupling is bit-identical to polar_tx.

Sources
-------
``analytic``   flat c1 (adjacent), c2 = c1 * ratio (next-adjacent), 0 beyond.
``survey``     c1 magnitude from the published lambda/2 patch-array values,
               phase linear in frequency = the free-space delay over the
               distance between the two elements (source: assumed; the
               papers do not publish the phase).
``touchstone`` an N-port .sNp file, interpolated onto the baseband grid.

All three put the matrix on a frequency grid and ``CouplingMatrix.at``
interpolates it (real and imaginary parts separately, ends held) onto the
burst's RF grid f0 + fftfreq.  The analytic source uses a two-point grid so
that writing it to .sNp and reading it back is bit-identical.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import ArrayConfig
from .geometry import C0, LinearArray
from .touchstone import read_touchstone, write_touchstone

TWO_PI = 2.0 * np.pi


@dataclass
class CouplingMatrix:
    freqs_hz: np.ndarray        # (F,) RF, increasing
    s: np.ndarray               # (F, n, n) complex
    source: str

    def __post_init__(self):
        self.freqs_hz = np.asarray(self.freqs_hz, dtype=float)
        self.s = np.asarray(self.s, dtype=complex)
        if self.s.ndim != 3 or self.s.shape[1] != self.s.shape[2] or self.s.shape[0] != self.freqs_hz.size:
            raise ValueError(f"s must be (F, n, n) with F = len(freqs); got {self.s.shape}")
        if self.freqs_hz.size > 1 and np.any(np.diff(self.freqs_hz) <= 0):
            raise ValueError("freqs_hz must be strictly increasing")

    @property
    def n(self) -> int:
        return int(self.s.shape[1])

    def offdiag(self) -> np.ndarray:
        m = self.s.copy()
        idx = np.arange(self.n)
        m[:, idx, idx] = 0.0
        return m

    @property
    def is_zero(self) -> bool:
        return bool(np.all(self.offdiag() == 0.0))

    def max_offdiag_db(self) -> float:
        mx = float(np.abs(self.offdiag()).max()) if self.n > 1 else 0.0
        return -np.inf if mx == 0.0 else 20.0 * np.log10(mx)

    def at(self, f_rf) -> np.ndarray:
        """Interpolate onto RF frequencies ``f_rf`` (any shape); ends held."""
        f_rf = np.asarray(f_rf, dtype=float)
        if self.freqs_hz.size == 1:
            return np.broadcast_to(self.s[0], f_rf.shape + self.s.shape[1:]).copy()
        out = np.empty(f_rf.shape + self.s.shape[1:], dtype=complex)
        for k in range(self.n):
            for j in range(self.n):
                re = np.interp(f_rf, self.freqs_hz, self.s[:, k, j].real)
                im = np.interp(f_rf, self.freqs_hz, self.s[:, k, j].imag)
                out[..., k, j] = re + 1j * im
        return out

    def scaled(self, db: float) -> "CouplingMatrix":
        """Off-diagonal terms scaled by ``db`` (``-inf`` -> zero coupling)."""
        if db == 0.0:
            return self
        g = 0.0 if db == -np.inf else 10.0 ** (db / 20.0)
        idx = np.arange(self.n)
        s = self.offdiag() * g
        s[:, idx, idx] = self.s[:, idx, idx]
        return CouplingMatrix(self.freqs_hz, s, f"{self.source}*{db:+g}dB")


# ------------------------------------------------------------- the sources
def _neighbour_shape(n: int, c1: complex, c2_rel: float) -> np.ndarray:
    m = np.zeros((n, n), dtype=complex)
    for k in range(n):
        for j in range(n):
            d = abs(k - j)
            if d == 1:
                m[k, j] = c1
            elif d == 2:
                m[k, j] = c1 * c2_rel
    return m


def analytic_matrix(n: int, c1_db: float, c1_deg: float, c2_rel_db: float,
                    f_lo: float, f_hi: float) -> CouplingMatrix:
    c1 = 10.0 ** (c1_db / 20.0) * np.exp(1j * np.deg2rad(c1_deg))
    m = _neighbour_shape(n, c1, 10.0 ** (c2_rel_db / 20.0))
    return CouplingMatrix(np.array([f_lo, f_hi]), np.stack([m, m]), "analytic")


def survey_matrix(n: int, c1_db: float, c1_deg_at_f0: float, c2_rel_db: float,
                  f0: float, spacing_m: float, f_grid, *, path_delay: bool = True) -> CouplingMatrix:
    """Published-magnitude coupling with a linear-phase (pure delay) frequency
    dependence: phi_kj(f) = phi0 - 2 pi (f - f0) * |k - j| d / c0."""
    f_grid = np.asarray(f_grid, dtype=float)
    a1 = 10.0 ** (c1_db / 20.0)
    r2 = 10.0 ** (c2_rel_db / 20.0)
    s = np.zeros((f_grid.size, n, n), dtype=complex)
    for k in range(n):
        for j in range(n):
            d = abs(k - j)
            if d not in (1, 2):
                continue
            mag = a1 if d == 1 else a1 * r2
            tau = (d * spacing_m / C0) if path_delay else 0.0
            ph = np.deg2rad(c1_deg_at_f0) - TWO_PI * (f_grid - f0) * tau
            s[:, k, j] = mag * np.exp(1j * ph)
    return CouplingMatrix(f_grid, s, "survey")


def touchstone_matrix(path: str) -> CouplingMatrix:
    ts = read_touchstone(path)
    return CouplingMatrix(ts.freqs_hz, ts.s, f"touchstone:{path}")


def write_matrix_touchstone(path: str, m: CouplingMatrix, comments=()) -> str:
    write_touchstone(path, m.freqs_hz, m.s, comments=tuple(comments) + (f"arraytx coupling source: {m.source}",))
    return str(path)


def build_coupling(cfg: ArrayConfig, geom: LinearArray, fs: float) -> CouplingMatrix:
    """The config's coupling matrix on a grid covering the burst (f0 +- fs/2),
    scaled by ``coupling.scale_db``.  One entry point for all three sources."""
    c = cfg.coupling
    f0 = geom.f0_hz
    f_lo, f_hi = f0 - fs / 2.0, f0 + fs / 2.0
    if c.source == "analytic":
        a = c.analytic
        m = analytic_matrix(geom.n, a.c1_db, a.c1_deg, a.c2_rel_db, f_lo, f_hi)
    elif c.source == "survey":
        s = c.survey
        grid = np.linspace(f_lo, f_hi, 257)
        m = survey_matrix(geom.n, s.c1_db, s.c1_deg_at_f0, s.c2_rel_db, f0,
                          geom.spacing_m, grid, path_delay=s.path_delay_from_spacing)
    elif c.source == "touchstone":
        m = touchstone_matrix(c.touchstone.path)
        if m.n != geom.n:
            raise ValueError(f"touchstone has {m.n} ports, array has {geom.n} elements")
    else:
        raise ValueError(f"unknown coupling source {c.source!r}")
    return m.scaled(float(c.scale_db))


# ------------------------------------------------------------ the one path
def apply_coupling(ys, m: CouplingMatrix, fs: float, f0: float) -> np.ndarray:
    """radiated = ys + S_offdiag(f) @ ys, in the frequency domain.

    ``ys`` is (n, N).  When the matrix has no coupling at all the INPUT
    OBJECT is returned (no FFT round trip): S = 0 is bit-identical to no
    array.  The diagonal is never applied (see the module docstring).
    """
    ys = np.asarray(ys)
    if ys.ndim != 2 or ys.shape[0] != m.n:
        raise ValueError(f"ys must be (n={m.n}, N), got {ys.shape}")
    if m.is_zero:
        return ys
    Y = np.fft.fft(ys, axis=1)                                  # (n, N)
    f_rf = f0 + np.fft.fftfreq(ys.shape[1], 1.0 / fs)
    s = m.at(f_rf)                                              # (N, n, n)
    idx = np.arange(m.n)
    s[:, idx, idx] = 0.0
    leak = np.einsum("fkj,jf->kf", s, Y)
    return np.fft.ifft(Y + leak, axis=1)
