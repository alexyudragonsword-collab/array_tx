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
    print(_engine(sim))
    print(f"standard {sim.standard.name}: f0 {sim.f0 / 1e9:.1f} GHz, BW {sim.wf.bw / 1e6:.0f} MHz, "
          f"fs {sim.fs / 1e9:.5f} GS/s, {sim.n_symbols} OFDM symbols ({sim.wf.n} samples)"
          + ("  [ARRAYTX_SMOKE: short burst]" if smoke() else ""))
    g = sim.geom
    shape = f"{g.n_x} x lambda/2 linear" if g.is_linear else f"{g.n_x} x {g.n_y} grid ({g.spacing_lambda:g} / {g.spacing_y_lambda:g} lambda), scan plane phi {g.plane_phi_deg:g} deg"
    print(f"array: {shape}, coupling {sim.coupling.source}, max |S_kj| {sim.coupling.max_offdiag_db():.1f} dB")
    return time.time()


def _engine(sim) -> str:
    from arraytx.report import engine_line
    return engine_line([e.engine for e in sim.elements], sim.cfg.element.topology)


def done(t0: float, fig, name: str) -> None:
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches="tight")
    print(f"\nplots -> {path}   ({time.time() - t0:.1f} s)")
    sys.stdout.flush()


def diagnostic_table(result) -> str:
    from arraytx.report import table
    rows = [c.row() for c in result.conducted]
    return "conducted PA-output metrics — DIAGNOSTIC ONLY (invariant 2: not acceptance numbers)\n" + table(rows)


# ---- DPD-table helpers shared by ex13 / ex14 / ex15 (one definition, so the 4 x 1
# and 8 x 8 table answers are scored the same way)

def aclr_at(sim, bank, theta):
    """OTA ACLR1 at the beam when ``bank`` predistorts the drives for ``theta``."""
    from arraytx.dpd import predistort_drives
    from arraytx.metrics import ota_metrics
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False).aclr1_db


def bracket(grid, theta):
    """The grid angles just below and just above ``theta`` (equal on a grid angle)."""
    lo = max(g for g in grid if g <= theta + 1e-9)
    hi = min(g for g in grid if g >= theta - 1e-9)
    return lo, hi


def element_loads(sim, theta):
    """|1 + Gamma_k| per element under the undistorted steered drives (one radiate)."""
    import numpy as np
    from arraytx.beam import steer
    sim.radiate(steer(sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering))
    return np.array(sim.last_load_pull["abs_1pg_mean"])


def edge_mask(geom):
    """True for the elements on the grid's border."""
    return (geom.ix == 0) | (geom.ix == geom.n_x - 1) | (geom.iy == 0) | (geom.iy == geom.n_y - 1)


# ---- scan-design helpers shared by ex16 / ex17

#: design targets (source: assumed -- design choices, not specification limits)
ACLR_TARGET_DBC = -45.0
EVM_TARGET_DB = -25.0
#: the DPD table's worst interpolation loss, per array (ex14: 4 x 1 nine banks;
#: ex15: 8 x 8 ten banks) -- carried as an ACLR margin
TABLE_MARGIN_DB = {"4 x 1": 0.30, "8 x 8": 0.35}


def design_sweep(cfg_path, angles, backoffs, cfrs, *, n_symbols=None, label="", tweak=None):
    """Per-element DPD retrained at each angle (the table entry), load pull on,
    over CFR x output backoff.  ``tweak(cfg)`` adjusts the config (a sensitivity
    case).  Rows: beam deg, CFR, backoff, ACLR1, EVM, loaded array efficiency."""
    from arraytx import ArraySim, load_config
    rows = []
    for cfr in cfrs:
        for bo in backoffs:
            cfg = load_config(cfg_path)
            cfg.element.pa.load_pull.enabled = True
            cfg.element.pa.backoff_db = bo
            cfg.sim.cfr_papr_db = cfr
            if tweak is not None:
                tweak(cfg)
            sim = ArraySim(cfg, n_symbols=n_symbols)
            for th in angles:
                r = sim.run(th, "per_element", conducted_diagnostics=False)
                rows.append({"array": label, "beam deg": th, "CFR dB": cfr, "backoff dB": bo, "ACLR1": r.beam.aclr1_db,
                             "EVM": r.beam.evm_db, "eta %": 100 * r.info["efficiency"]["eta_array_loaded"]})
            print(f"  {label} CFR {cfr:.1f} backoff {bo:.0f}: " + "  ".join(
                f"{x['beam deg']:.0f}deg {x['ACLR1']:.1f}/{x['eta %']:.1f}%" for x in rows[-len(angles):]), flush=True)
    return rows


def same_setting(a, b):
    """True when two design-table rows picked the same (CFR, backoff); two
    angles where nothing met the targets (NaN) count as the same."""
    import math
    key = lambda x: tuple("none" if math.isnan(x[k]) else x[k] for k in ("CFR dB", "backoff dB"))  # noqa: E731
    return key(a) == key(b)


def meets(x, margin, aclr_target=ACLR_TARGET_DBC, evm_target=EVM_TARGET_DB):
    return x["ACLR1"] + margin <= aclr_target and x["EVM"] <= evm_target


def design_table(rows, angles, label, margin, aclr_target=ACLR_TARGET_DBC, evm_target=EVM_TARGET_DB):
    """Per angle the most efficient setting that meets the targets, and what the
    60 deg (largest-angle) setting would give there.  The fixed setting is checked
    against the targets at every angle: where it fails, its efficiency is not a
    fair baseline and the gain is left out (NaN) and flagged."""
    nan = float("nan")
    ok_ = lambda x: meets(x, margin, aclr_target, evm_target)  # noqa: E731
    pick = {}
    for th in angles:
        ok = [x for x in rows if x["beam deg"] == th and ok_(x)]
        pick[th] = max(ok, key=lambda x: x["eta %"]) if ok else None
    fixed = pick[max(angles)]
    out = []
    for th in angles:
        p = pick[th]
        same = None if fixed is None else next(x for x in rows if x["beam deg"] == th and x["CFR dB"] == fixed["CFR dB"]
                                               and x["backoff dB"] == fixed["backoff dB"])
        same_ok = same is not None and ok_(same)
        out.append({"array": label, "beam deg": th, "CFR dB": p["CFR dB"] if p else nan, "backoff dB": p["backoff dB"] if p else nan,
                    "ACLR1": p["ACLR1"] if p else nan, "EVM": p["EVM"] if p else nan, "eta %": p["eta %"] if p else nan,
                    "eta fixed %": same["eta %"] if same else nan, "fixed meets": bool(same_ok),
                    "adaptive gain pts": (p["eta %"] - same["eta %"]) if (p and same_ok) else nan})
    return out, pick


# ---- the |1 + Gamma| backoff rule shared by ex19 / ex20 / ex21

def least_backoff(rows, theta, margin):
    """The least backoff at ``theta`` that meets the targets (NaN if none in the sweep)."""
    ok = sorted(x["backoff dB"] for x in rows if x["beam deg"] == theta and meets(x, margin))
    return ok[0] if ok else float("nan")


def backoff_rule(ms, bs, tol=0.0):
    """backoff(m) from training pairs: monotone (cumulative max in m), the
    nearest trained point at or above m - tol; above the range, the fitted dB
    per unit m, rounded up.  ``tol`` reads an m within tol of a trained point
    as that point (|1 + Gamma| repeats to ~0.002 across operating points; 0 =
    ex19's rule).  Returns (rule, sorted m, monotone backoffs, slope);
    rule(m) -> (backoff dB, extrapolated?)."""
    import math

    import numpy as np
    order = np.argsort(ms)
    m_sorted = np.asarray(ms)[order]
    b_mono = np.maximum.accumulate(np.asarray(bs)[order])
    slope = float(np.polyfit(m_sorted, b_mono, 1)[0]) if np.ptp(m_sorted) > 0 else 0.0

    def rule(m):
        i = int(np.searchsorted(m_sorted, m - tol - 1e-9))
        if i < len(m_sorted):
            return float(b_mono[i]), False
        return float(b_mono[-1] + math.ceil(max(slope, 0.0) * (m - tol - m_sorted[-1]) - 1e-9)), True
    return rule, m_sorted, b_mono, slope
