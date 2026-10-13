"""Shared bits for the examples: output dir, smoke flag, plot style, the
engine line every example prints first."""
from __future__ import annotations

import os
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

#: categorical slots (fixed order, never cycled) for the three DPD schemes
SCHEME_COLORS = {"none": "#2a78d6", "per_element": "#eb6834", "array": "#1baf7a"}
SCHEME_LABELS = {"none": "no DPD", "per_element": "per-element ILA-GMP", "array": "array ILA-GMP (OTA)"}
#: and for the three coupling sources (a separate figure, so the same slots)
SOURCE_COLORS = {"analytic": "#2a78d6", "survey": "#eb6834", "touchstone": "#1baf7a"}

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 130, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e3e2dd", "grid.linewidth": 0.6,
    "axes.edgecolor": "#8a8a85", "lines.linewidth": 1.6,
    "legend.frameon": False,
})


def smoke() -> bool:
    return os.environ.get("ARRAYTX_SMOKE", "") not in ("", "0")


def banner(title: str, sim) -> float:
    print("=" * 78)
    print(title)
    print("=" * 78)
    print(sim.run(sim.cfg.beam.scan_deg[0], "none", conducted_diagnostics=False).info["engine_line"]
          if False else _engine(sim))
    print(f"standard {sim.standard.name}: f0 {sim.f0 / 1e9:.1f} GHz, BW {sim.wf.bw / 1e6:.0f} MHz, "
          f"fs {sim.fs / 1e9:.5f} GS/s, {sim.n_symbols} OFDM symbols ({sim.wf.n} samples)"
          + ("  [ARRAYTX_SMOKE: short burst]" if smoke() else ""))
    print(f"array: {sim.geom.n} x lambda/2 linear, coupling {sim.coupling.source}, "
          f"max |S_kj| {sim.coupling.max_offdiag_db():.1f} dB")
    return time.time()


def _engine(sim) -> str:
    from arraytx.report import engine_line
    r = sim.elements[0].run(sim.x, sim.wf, noise=sim.cfg.sim.noise)
    return engine_line([r.phasemod_mode], sim.cfg.element.topology)


def done(t0: float, fig, name: str) -> None:
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches="tight")
    print(f"\nplots -> {path}   ({time.time() - t0:.1f} s)")
    sys.stdout.flush()


def diagnostic_table(result) -> str:
    from arraytx.report import table
    rows = [c.row() for c in result.conducted]
    return "conducted PA-output metrics — DIAGNOSTIC ONLY (invariant 2: not acceptance numbers)\n" + table(rows)
