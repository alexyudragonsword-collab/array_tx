"""The three DPD schemes, side by side (milestone 1).

``none``         the drives go to the elements as steered.
``per_element``  one ILA-GMP per element, trained at that element's
                 CONDUCTED port — by default its own PA forward output
                 (``per_element_observe: pa_output``: a forward coupler
                 does not see the wave coupled back from the neighbours),
                 optionally the antenna port including the leakage.
``array``        one ILA-GMP for the whole array, trained on the OTA
                 observation in the beam direction: the far-field burst at
                 theta0 after coupling.  Every element then transmits the
                 same predistorted signal, steered.

The predistorter is PA_DPD's ``ILAPredistorter`` over its ``GMPModel``
(vendored through polar_tx), untouched: the "PA" it sees is a callable that
runs the element chain(s) and, for the array scheme, the far-field
synthesis.  Nothing in the chain moves between training and use: the
envelope full scale is pinned (element.py) and each element's run seed is
fixed, so the ILA iterates against one deterministic device.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .beam import far_field, steer
from .config import ArrayConfig
from .coupling import CouplingMatrix, apply_coupling
from .element import ElementChain
from .geometry import LinearArray
from .vendor.polartx.vendor.padpd.dpd import ILAPredistorter
from .vendor.polartx.vendor.padpd.pa.gmp import GMPModel
from .vendor.polartx.waveforms.base import Waveform

SCHEMES = ("none", "per_element", "array")


def make_ila(cfg: ArrayConfig) -> ILAPredistorter:
    g = cfg.dpd.gmp
    kw = dict(order=g.order, memory_depth=g.memory_depth,
              lag_order=g.lag_order, lag_memory=g.lag_memory, lag_span=g.lag_span,
              lead_order=g.lead_order, lead_memory=g.lead_memory, lead_span=g.lead_span)
    return ILAPredistorter(model_factory=lambda: GMPModel(**kw),
                           n_iterations=cfg.dpd.n_iterations,
                           fit_kwargs={"regularization": cfg.dpd.regularization})


@dataclass
class DPDBank:
    scheme: str
    per_element: list[ILAPredistorter] = field(default_factory=list)
    array: ILAPredistorter | None = None
    info: dict[str, Any] = field(default_factory=dict)

    def n_coeffs(self) -> int:
        if self.scheme == "per_element":
            return sum(d.dpd_model.n_coeffs for d in self.per_element)
        if self.scheme == "array" and self.array is not None:
            return int(self.array.dpd_model.n_coeffs)
        return 0


def _run_all(elements: list[ElementChain], drives: list[np.ndarray], wf: Waveform, noise: bool) -> np.ndarray:
    return np.stack([el.run(d, wf, noise=noise).y for el, d in zip(elements, drives)])


def train(cfg: ArrayConfig, scheme: str, *, elements: list[ElementChain], x: np.ndarray,
          wf: Waveform, geom: LinearArray, coupling: CouplingMatrix, theta0_deg: float) -> DPDBank:
    """Train the scheme's predistorter(s) for the beam at theta0."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown DPD scheme {scheme!r}; one of {SCHEMES}")
    noise = cfg.sim.noise
    fs, f0 = wf.fs, geom.f0_hz
    bank = DPDBank(scheme)
    if scheme == "none":
        return bank
    if cfg.element.topology == "rfdac":
        # CartesianTX re-derives its full scale from each burst's peak and
        # has no fs_scale_fixed: a predistorted (peak-expanded) drive would be
        # re-normalised and the DPD silently undone.  Refuse rather than
        # report a number that means nothing (ROADMAP B3).
        raise ValueError("DPD schemes need a pinned full scale; the rfdac topology "
                         "re-normalises per burst (polar_tx CartesianTX) -- use dpd.scheme: none")
    drives = steer(x, geom, theta0_deg, fs, cfg.beam.steering)

    if scheme == "per_element":
        observe = cfg.dpd.per_element_observe
        ys_fixed = None
        if observe == "antenna_port":
            # the neighbours' drives do not change while element k trains:
            # run them once and substitute row k inside the loop (O(n), not O(n^2))
            ys_fixed = _run_all(elements, drives, wf, noise)
        for k, el in enumerate(elements):
            if observe == "pa_output":
                pa: Callable[[np.ndarray], np.ndarray] = lambda u, el=el: el.run(u, wf, noise=noise).y
            else:   # antenna_port: own PA plus the leakage from the neighbours' steered drives
                def pa(u, k=k, el=el):
                    ys = ys_fixed.copy()
                    ys[k] = el.run(u, wf, noise=noise).y
                    return apply_coupling(ys, coupling, fs, f0)[k]
            ila = make_ila(cfg)
            ila.fit(pa, drives[k])
            bank.per_element.append(ila)
        bank.info = {"observe": observe, "target_gain": [complex(d.target_gain) for d in bank.per_element]}
        return bank

    # array: one DPD, trained on the far field at the beam
    def pa_array(u):
        ds = steer(u, geom, theta0_deg, fs, cfg.beam.steering)
        rs = apply_coupling(_run_all(elements, ds, wf, noise), coupling, fs, f0)
        return far_field(rs, geom, theta0_deg, fs)
    ila = make_ila(cfg)
    ila.fit(pa_array, x)
    bank.array = ila
    bank.info = {"observe": f"far field {theta0_deg:+.1f} deg", "target_gain": complex(ila.target_gain)}
    return bank


def predistort_drives(bank: DPDBank, x: np.ndarray, geom: LinearArray, theta0_deg: float,
                      fs: float, steering: str) -> list[np.ndarray]:
    """The element drives for the common signal ``x`` under the bank's scheme."""
    if bank.scheme == "none":
        return steer(x, geom, theta0_deg, fs, steering)
    if bank.scheme == "per_element":
        drives = steer(x, geom, theta0_deg, fs, steering)
        return [d(dr) for d, dr in zip(bank.per_element, drives)]
    assert bank.array is not None
    return steer(bank.array(x), geom, theta0_deg, fs, steering)
