"""Beam steering and far-field synthesis (invariant 4: the squint is
computed, not corrected for).

Far field
---------
E(theta, f) = g(theta) / n * sum_k R_k(f) * exp(+j 2 pi (f0 + f) tau_k(theta))

with tau_k(theta) = x_k sin(theta) / c0 (see ``geometry.LinearArray``) and f
the BASEBAND frequency of the FFT bin.  Every baseband frequency gets its own
phase, so a phase-shifter-steered array points each subcarrier somewhere
slightly different, which is the squint; a true-time-delay array does not.
The 1/n keeps the beam-direction gain at 1 so EVM / ACLR do not depend on n
(``normalize=False`` returns the coherent sum, 20 log10(n) dB up).

Steering
--------
``phase``: w_k = exp(-j 2 pi f0 tau_k(theta0)) — a complex weight, flat over
frequency (aligned at the carrier only).
``ttd``:   W_k(f) = exp(-j 2 pi (f0 + f) tau_k(theta0)) — a delay of
tau_k(theta0) plus the carrier phase, applied in the frequency domain.
Both go through ``steer``; with theta0 = 0 both are the identity and the
drive is returned unchanged (the 1-element anchor relies on that).

Bit-exactness notes: when every tau is exactly 0.0 (broadside, or n = 1)
the synthesis is a plain sum without an FFT round trip, so a single element
at broadside returns its own output bit for bit.
"""
from __future__ import annotations

import numpy as np

from .geometry import LinearArray

TWO_PI = 2.0 * np.pi


def _bb_freqs(n_samples: int, fs: float) -> np.ndarray:
    return np.fft.fftfreq(n_samples, 1.0 / fs)


def steering_phase_weights(geom: LinearArray, theta0_deg: float) -> np.ndarray:
    """Phase-shifter weights (complex, per element), aligned at f0."""
    tau = geom.delays_s(theta0_deg)
    return np.exp(-1j * TWO_PI * geom.f0_hz * tau)


def steer(x: np.ndarray, geom: LinearArray, theta0_deg: float, fs: float,
          mode: str) -> list[np.ndarray]:
    """Per-element drives for the common signal ``x`` steered to theta0."""
    if mode not in ("phase", "ttd"):
        raise ValueError(f"steering must be phase or ttd, got {mode!r}")
    tau = geom.delays_s(theta0_deg)
    if np.all(tau == 0.0):
        return [x for _ in range(geom.n)]        # identity: same array, bit for bit
    if mode == "phase":
        w = np.exp(-1j * TWO_PI * geom.f0_hz * tau)
        return [x * wk for wk in w]
    X = np.fft.fft(x)
    f = _bb_freqs(x.size, fs)
    return [np.fft.ifft(X * np.exp(-1j * TWO_PI * (geom.f0_hz + f) * tk)) for tk in tau]


def far_field(ys, geom: LinearArray, theta_deg: float, fs: float,
              *, normalize: bool = True) -> np.ndarray:
    """Far-field signal in direction ``theta_deg`` from the radiated element
    signals ``ys`` (list or (n, N) array), as a complex baseband burst."""
    ys = np.asarray(ys)
    if ys.ndim != 2 or ys.shape[0] != geom.n:
        raise ValueError(f"ys must be (n={geom.n}, N), got {ys.shape}")
    g = geom.element_gain(theta_deg)
    tau = geom.delays_s(theta_deg)
    scale = (g / geom.n) if normalize else g
    if np.all(tau == 0.0):
        e = ys[0] if geom.n == 1 else ys.sum(axis=0)
        return e if scale == 1.0 else e * scale
    Y = np.fft.fft(ys, axis=1)
    f = _bb_freqs(ys.shape[1], fs)
    ph = np.exp(1j * TWO_PI * np.outer(tau, geom.f0_hz + f))    # (n, N)
    return np.fft.ifft((Y * ph).sum(axis=0)) * scale


def far_field_many(ys, geom: LinearArray, thetas_deg, fs: float,
                   *, normalize: bool = True) -> np.ndarray:
    """``far_field`` for many directions with the element FFTs done once.
    Returns (len(thetas), N)."""
    ys = np.asarray(ys)
    Y = np.fft.fft(ys, axis=1)
    f = _bb_freqs(ys.shape[1], fs)
    out = np.empty((len(thetas_deg), ys.shape[1]), dtype=complex)
    for i, th in enumerate(thetas_deg):
        tau = geom.delays_s(th)
        g = geom.element_gain(th)
        scale = (g / geom.n) if normalize else g
        ph = np.exp(1j * TWO_PI * np.outer(tau, geom.f0_hz + f))
        out[i] = np.fft.ifft((Y * ph).sum(axis=0)) * scale
    return out


# ------------------------------------------------------------ CW analysis
def array_factor_cw(geom: LinearArray, theta0_deg: float, f_offset_hz: float,
                    thetas_deg, mode: str) -> np.ndarray:
    """|AF(theta)| (normalised to 1 at a perfectly coherent sum) for a CW tone
    at f0 + f_offset after steering to theta0 — the same phase model
    ``steer`` + ``far_field`` apply to a waveform, evaluated in closed form."""
    thetas = np.atleast_1d(np.asarray(thetas_deg, dtype=float))
    tau0 = geom.delays_s(theta0_deg)
    f_rf = geom.f0_hz + f_offset_hz
    if mode == "phase":
        w = np.exp(-1j * TWO_PI * geom.f0_hz * tau0)
    elif mode == "ttd":
        w = np.exp(-1j * TWO_PI * f_rf * tau0)
    else:
        raise ValueError(mode)
    af = np.empty(thetas.size)
    for i, th in enumerate(thetas):
        tau = geom.delays_s(th)
        af[i] = abs(np.sum(w * np.exp(1j * TWO_PI * f_rf * tau))) / geom.n * geom.element_gain(th)
    return af


def peak_direction_cw(geom: LinearArray, theta0_deg: float, f_offset_hz: float,
                      mode: str, *, search_deg: float = 15.0, step_deg: float = 0.01) -> float:
    """Direction of the main-lobe peak for a CW tone at f0 + f_offset, by a
    fine grid around theta0 plus a parabolic refinement."""
    th = np.arange(theta0_deg - search_deg, theta0_deg + search_deg + step_deg / 2, step_deg)
    th = th[(th > -90.0) & (th < 90.0)]
    af = array_factor_cw(geom, theta0_deg, f_offset_hz, th, mode)
    i = int(np.argmax(af))
    if 0 < i < th.size - 1:
        y0, y1, y2 = af[i - 1], af[i], af[i + 1]
        denom = (y0 - 2 * y1 + y2)
        if denom != 0.0:
            return float(th[i] + 0.5 * (y0 - y2) / denom * step_deg)
    return float(th[i])


def squint_analytic_deg(theta0_deg: float, f0_hz: float, f_offset_hz: float) -> float:
    """Phase-shifter squint: the beam aligned at f0 points, at f0 + df, where
    sin(theta) = sin(theta0) * f0 / (f0 + df); for small df this is
    d theta ~ -(df / f0) tan(theta0)."""
    s = np.sin(np.deg2rad(theta0_deg)) * f0_hz / (f0_hz + f_offset_hz)
    return float(np.degrees(np.arcsin(np.clip(s, -1.0, 1.0))) - theta0_deg)


def highest_sidelobe_direction(geom: LinearArray, theta0_deg: float, mode: str,
                               *, step_deg: float = 0.1) -> float | None:
    """Direction of the highest sidelobe of |AF| at f0 for the beam steered to
    theta0, or None when the pattern has no sidelobe (n = 1)."""
    if geom.n < 2:
        return None
    th = np.arange(-89.9, 89.9 + step_deg / 2, step_deg)
    af = array_factor_cw(geom, theta0_deg, 0.0, th, mode)
    # local maxima
    peaks = [i for i in range(1, th.size - 1) if af[i] >= af[i - 1] and af[i] > af[i + 1]]
    if not peaks:
        return None
    main = min(peaks, key=lambda i: abs(th[i] - theta0_deg))
    side = [i for i in peaks if i != main]
    if not side:
        return None
    best = max(side, key=lambda i: af[i])
    return float(th[best])
