"""The element's update clock and the simulation grid (polar_tx@0e7b7ac).

A polar element's DTC and DPA update at a clock -- 4 x the FFT rate,
polar_tx ``nr_dtc``'s ``update_oversampling`` -- and the simulation grid may
be finer: ``sim.oversampling = 4 m`` holds each update for ``m`` grid
samples.  What is digital runs at the clock: the waveform (polar_tx
``burst_on_grid``), CFR, DPD, and inside polar_tx the polar split,
quantization and DPA encode.  What is analog runs on the grid: the held
output and its images, steering and true-time delay, coupling, the far
field and the metrics.  ``m = 1`` is the grid at the clock, the behaviour
before 0e7b7ac, and every function here is then the identity.

The waveform carries ``m`` as ``wf.meta["clock_hold"]`` (set by
``Standard.make_waveform``), so a function that receives the waveform knows
the clock without another argument.  polar_tx models the split for the
polar chain only; outphasing and the RF-DAC keep the clock on the grid
(m = 1 at any grid, their presets' ``update_oversampling=None``).
"""
from __future__ import annotations

import numpy as np

# polar_tx's own band-limited interpolation, the one burst_on_grid uses: the
# drives the front end builds at the clock land on the grid the same way the
# waveform did (private in polar_tx; tests/test_clock.py pins the contract)
from .vendor.polartx.presets import _interp
from .vendor.polartx.waveforms.base import Waveform


def clock_hold(wf: Waveform) -> int:
    """Grid samples per update of the element clock (1: the grid is the clock)."""
    return int(wf.meta.get("clock_hold", 1))


def to_grid(x_c: np.ndarray, m: int) -> np.ndarray:
    """A clock-rate signal on the m-fold grid: periodic band-limited
    interpolation that passes through every input sample exactly, so the
    chain -- which reads every m-th grid sample -- sees ``x_c`` bit for bit."""
    if m == 1:
        return x_c
    x = _interp(np.asarray(x_c), m)
    x[::m] = x_c
    return x


def to_clock(y: np.ndarray, m: int) -> np.ndarray:
    """A grid signal observed at the clock: an ideal anti-alias filter
    (every bin above the clock's Nyquist dropped, the Nyquist bin's two
    halves summed) and the update instants -- what a DPD observation
    receiver sampling at the update clock delivers.  The hold's images sit
    at multiples of the clock and are filtered out, its in-band droop stays.
    The inverse of ``to_grid`` up to FFT rounding."""
    if m == 1:
        return y
    y = np.asarray(y)
    n = y.size
    if n % m:
        raise ValueError(f"{n} grid samples do not hold a whole number of updates of {m}")
    nc = n // m
    ys = np.fft.fft(y) / m
    zs = np.zeros(nc, dtype=complex)
    h = nc // 2
    zs[:h] = ys[:h]
    neg = nc - h - 1
    if neg:
        zs[-neg:] = ys[-neg:]
    zs[h] = ys[h] + ys[-h] if nc % 2 == 0 else ys[h]
    return np.fft.ifft(zs)
