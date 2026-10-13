"""ArraySim: one config in, far-field metrics out.

Data flow for one run (one scan angle, one DPD scheme)::

    standard -> waveform x (unit power) -> CFR (common) -> [DPD] -> steer
      -> element k chain -> y_k (conducted, diagnostic)
      -> apply_coupling -> r_k (radiated)
      -> far_field(theta) for theta in {beam, sidelobe} -> OTA metrics

Everything random comes from ``SeedTree(cfg.seed)``; nothing here draws.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .beam import far_field, far_field_many, highest_sidelobe_direction
from .config import ArrayConfig
from .coupling import CouplingMatrix, apply_coupling, build_coupling
from .dpd import DPDBank, predistort_drives, train
from .element import ElementChain, ElementResult, build_elements
from .geometry import LinearArray
from .metrics import DirectionMetrics, conducted_metrics, ota_metrics
from .report import engine_line
from .seeds import SeedTree
from .standards import Standard, get_standard
from .vendor.polartx.vendor.padpd.cfr import cfr_clip_filter
from .vendor.polartx.waveforms.base import Waveform


def smoke() -> bool:
    return os.environ.get("ARRAYTX_SMOKE", "") not in ("", "0")


@dataclass
class ArrayResult:
    theta0_deg: float
    scheme: str
    sidelobe_deg: float | None
    drives: list[np.ndarray]
    element_results: list[ElementResult]
    ys: np.ndarray                      # (n, N) conducted
    rs: np.ndarray                      # (n, N) radiated (after coupling)
    far: dict[str, tuple[float, np.ndarray]]     # label -> (theta, far-field burst)
    ota: dict[str, DirectionMetrics]             # label -> metrics (acceptance)
    conducted: list[DirectionMetrics]            # per element (diagnostic)
    dpd: DPDBank
    engine_modes: list[str]
    seconds: float
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def beam(self) -> DirectionMetrics:
        return self.ota["beam"]

    @property
    def sidelobe(self) -> DirectionMetrics | None:
        return self.ota.get("sidelobe")


class ArraySim:
    def __init__(self, cfg: ArrayConfig, *, n_symbols: int | None = None):
        self.cfg = cfg
        self.standard: Standard = get_standard(cfg.standard)
        self.tree = SeedTree(cfg.seed, cfg.array.n_elements)
        self.geom = LinearArray(cfg.array.n_elements, cfg.array.spacing_lambda,
                                float(self.standard.carrier_hz.value), cfg.array.element_pattern)
        if n_symbols is None:
            n_symbols = cfg.sim.smoke_n_symbols if smoke() else cfg.sim.n_symbols
        self.n_symbols = int(n_symbols)
        self.wf: Waveform = self.standard.make_waveform(self.n_symbols, self.tree.int_seed("waveform"))
        x = self.wf.x
        if cfg.sim.cfr_papr_db is not None:
            x = cfr_clip_filter(x, cfg.sim.cfr_papr_db, self.wf.fs, self.wf.bw)
        self.x = x
        self.coupling: CouplingMatrix = build_coupling(cfg, self.geom, self.wf.fs)
        self.elements: list[ElementChain] = build_elements(cfg, self.standard, self.tree, self.x, self.wf)

    # ------------------------------------------------------------- pieces
    @property
    def fs(self) -> float:
        return self.wf.fs

    @property
    def f0(self) -> float:
        return self.geom.f0_hz

    def sidelobe_direction(self, theta0_deg: float) -> float | None:
        if self.cfg.beam.sidelobe == "auto":
            return highest_sidelobe_direction(self.geom, theta0_deg, self.cfg.beam.steering)
        return float(self.cfg.beam.sidelobe)

    def radiate(self, drives: list[np.ndarray]) -> tuple[list[ElementResult], np.ndarray, np.ndarray]:
        res = [el.run(d, self.wf, noise=self.cfg.sim.noise) for el, d in zip(self.elements, drives)]
        ys = np.stack([r.y for r in res])
        rs = apply_coupling(ys, self.coupling, self.fs, self.f0)
        return res, ys, rs

    def far_field(self, rs: np.ndarray, theta_deg: float) -> np.ndarray:
        return far_field(rs, self.geom, theta_deg, self.fs)

    def far_field_many(self, rs: np.ndarray, thetas_deg) -> np.ndarray:
        return far_field_many(rs, self.geom, thetas_deg, self.fs)

    # ---------------------------------------------------------------- run
    def run(self, theta0_deg: float | None = None, scheme: str | None = None,
            *, extra_directions: dict[str, float] | None = None,
            conducted_diagnostics: bool = True) -> ArrayResult:
        t0 = time.time()
        cfg = self.cfg
        theta0 = float(cfg.beam.scan_deg[0] if theta0_deg is None else theta0_deg)
        scheme = scheme or cfg.dpd.scheme
        bank = train(cfg, scheme, elements=self.elements, x=self.x, wf=self.wf, geom=self.geom,
                     coupling=self.coupling, theta0_deg=theta0)
        drives = predistort_drives(bank, self.x, self.geom, theta0, self.fs, cfg.beam.steering)
        res, ys, rs = self.radiate(drives)
        sl = self.sidelobe_direction(theta0)
        dirs: dict[str, float] = {"beam": theta0}
        if sl is not None:
            dirs["sidelobe"] = sl
        if extra_directions:
            dirs.update(extra_directions)
        far = {k: (th, self.far_field(rs, th)) for k, th in dirs.items()}
        offsets = tuple(cfg.metrics.aclr_offsets)
        ota = {k: ota_metrics(e, self.wf, th, k, offsets=offsets, equalize=cfg.metrics.evm_equalize)
               for k, (th, e) in far.items()}
        cond = []
        if conducted_diagnostics:
            cond = [conducted_metrics(ys[k], self.wf, k, offsets=offsets, equalize=cfg.metrics.evm_equalize)
                    for k in range(self.geom.n)]
        modes = [r.phasemod_mode for r in res]
        return ArrayResult(theta0, scheme, sl, drives, res, ys, rs, far, ota, cond, bank, modes,
                           time.time() - t0,
                           info={"coupling_source": self.coupling.source,
                                 "coupling_max_offdiag_db": self.coupling.max_offdiag_db(),
                                 "n_symbols": self.n_symbols, "fs": self.fs,
                                 "engine_line": engine_line(modes, cfg.element.topology)})

    def run_matrix(self, scan_deg=None, schemes=None) -> dict[tuple[float, str], ArrayResult]:
        scan = list(self.cfg.beam.scan_deg if scan_deg is None else scan_deg)
        schemes = list(schemes or ("none", "per_element", "array"))
        return {(float(th), s): self.run(th, s) for th in scan for s in schemes}
