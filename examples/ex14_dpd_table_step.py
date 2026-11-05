"""ex14 — how many predistorters does a scanning array need? (ROADMAP B8)

ex11: under load modulation one GMP cannot serve 0-60 deg (joint fit: worst
+7.2 dB), and a table on a 30 deg grid still loses 2.3 dB at 45 deg after
interpolating the coefficients.  The operating point moves with the active
reflection Gamma_k, and Gamma_k is set by the steering phases
exp(j k d sin theta): a function of sin theta, changing fastest at large
angles (|1+Gamma| 0.84 / 0.92 / 1.26 at 0 / 30 / 60 deg on 4 x 1).

A table is a set of grid angles, one predistorter trained at each (the
"retrained" bank there), and a rule for the angles in between:

  nearest   the grid bank closest in angle (ties: the larger |theta|);
  angle     coefficients blended linearly in theta between the neighbours;
  sin       blended linearly in sin theta;
  load      blended linearly in m(theta) = the mean |1 + Gamma_k| the
            undistorted steered drives produce (what the PA actually sees;
            a real system knows it per angle from calibration).

Every table is scored by its worst ACLR1 loss against retraining at each of
the evaluation angles (0-60 deg in 2.5 deg steps: most of them on no grid).
The question B8 asks: the fewest banks that keep the worst loss <= 0.5 dB.
Besides hand-made grids, ``curvature N`` places N grid angles by the
measured m(theta) itself: knot density sqrt|m''| (linear interpolation
error follows the curvature, not the slope).
4 x 1 full burst, load pull on, per-element DPD; the winner is then checked
with the array DPD and on 8 x 8.
"""
import numpy as np

from _common import SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.beam import steer
from arraytx.dpd import blend_banks, predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

EVAL = [0.0, 15.0, 30.0, 45.0, 60.0] if smoke() else list(np.arange(0.0, 60.0 + 1e-9, 2.5))
GRIDS = {
    "uniform 30": [0, 30, 60],
    "uniform 20": [0, 20, 40, 60],
    "uniform 15": [0, 15, 30, 45, 60],
    "uniform 10": [0, 10, 20, 30, 40, 50, 60],
    "uniform 7.5": [0, 7.5, 15, 22.5, 30, 37.5, 45, 52.5, 60],
    "uniform 5": [float(a) for a in np.arange(0.0, 60.0 + 1e-9, 5.0)],
    "dense top 4": [0, 30, 45, 60],
    "dense top 5": [0, 30, 40, 50, 60],
    "dense top 6": [0, 25, 40, 50, 55, 60],
    # rounded: arcsin(sin 60) is 59.99999999999999, which would be retrained as an angle of its own
    "uniform sin 5": [round(float(np.degrees(np.arcsin(u))), 6) for u in np.linspace(0, np.sin(np.radians(60)), 5)],
}
if smoke():
    GRIDS = {k: GRIDS[k] for k in ("uniform 30", "uniform 15", "dense top 4")}
MODES = ("nearest", "angle", "sin", "load")
TARGET_DB = 0.5


def sim_for(path, n_symbols=None):
    cfg = load_config(path)
    cfg.element.pa.load_pull.enabled = True
    return ArraySim(cfg, n_symbols=n_symbols)


def aclr_at(sim, bank, theta):
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False).aclr1_db


def table_bank(banks, grid, theta, mode, m):
    lo = max(g for g in grid if g <= theta + 1e-9)
    hi = min(g for g in grid if g >= theta - 1e-9)
    if abs(hi - lo) < 1e-9:
        return banks[lo]
    if mode == "nearest":
        return banks[hi] if hi - theta <= theta - lo else banks[lo]
    if mode == "angle":
        w = (theta - lo) / (hi - lo)
    elif mode == "sin":
        s = np.sin(np.radians([lo, theta, hi]))
        w = (s[1] - s[0]) / (s[2] - s[0])
    else:
        w = (m(theta) - m(lo)) / (m(hi) - m(lo)) if m(hi) != m(lo) else 0.5
    return blend_banks(banks[lo], banks[hi], float(np.clip(w, 0.0, 1.0)))


def m_of(sim, theta):
    """m(theta): the mean |1 + Gamma_k| the undistorted steered drives put on the
    PAs -- one radiate, no metrics."""
    sim.radiate(steer(sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering))
    return float(np.mean(sim.last_load_pull["abs_1pg_mean"]))


def curvature_grid(mload, n):
    """n grid angles placed where m(theta) BENDS: piecewise-linear interpolation
    error goes with the second derivative, so the knots follow the density
    sqrt|m''| (the classic optimal-knot rule), snapped to the evaluation
    angles (whose banks are trained anyway), endpoints kept."""
    th = np.array(sorted(mload))
    m = np.array([mload[t] for t in th])
    d2 = np.zeros_like(m)
    d2[1:-1] = np.abs(m[2:] - 2 * m[1:-1] + m[:-2])
    d2[0], d2[-1] = d2[1], d2[-2]
    dens = np.sqrt(d2) + 1e-3 * np.sqrt(d2).max()
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(th))])
    targets = np.interp(np.linspace(0, cum[-1], n), cum, th)
    out = sorted({float(th[np.argmin(np.abs(th - t))]) for t in targets} | {float(th[0]), float(th[-1])})
    return out


def study(path, scheme, grids, evals, n_symbols=None, label="", curvature=(), modes=MODES):
    sim = sim_for(path, n_symbols)
    mload = {}
    for th in sorted({float(a) for a in evals}):
        mload[th] = m_of(sim, th)
    grids = dict(grids)
    for n in curvature:
        grids[f"curvature {n}"] = curvature_grid(mload, n)
        print(f"  {label}: curvature {n} grid = {', '.join(f'{a:g}' for a in grids[f'curvature {n}'])}", flush=True)
    angles = sorted({float(a) for g in grids.values() for a in g} | {float(a) for a in evals})
    retrained = {}
    for th in angles:
        r = sim.run(th, scheme, conducted_diagnostics=False)
        retrained[th] = (r.dpd, r.beam.aclr1_db)            # only what the tables use: not the 64-element results
        if th not in mload:
            mload[th] = m_of(sim, th)
    print(f"  {label}: m(theta) = mean |1+Gamma|: " + "  ".join(f"{t:.1f}:{mload[t]:.3f}" for t in angles if t in evals[::2]), flush=True)
    xs = sorted(mload)
    m = lambda t: mload[float(t)] if float(t) in mload else float(np.interp(t, xs, [mload[x] for x in xs]))  # noqa: E731
    rows = []
    for name, grid in grids.items():
        grid = [float(g) for g in grid]
        banks = {g: retrained[g][0] for g in grid}
        for mode in modes:
            losses = []
            for th in evals:
                ref = retrained[float(th)][1]
                losses.append(aclr_at(sim, table_bank(banks, grid, float(th), mode, m), float(th)) - ref)
            worst = int(np.argmax(losses))
            rows.append({"table": name, "banks": len(grid), "rule": mode, "worst loss dB": losses[worst], "at deg": evals[worst],
                         "mean loss dB": float(np.mean(losses)), "losses": losses})
        best = min((r for r in rows if r["table"] == name), key=lambda r: r["worst loss dB"])
        print(f"  {label} {name:14} ({len(grid)} banks): best rule {best['rule']:7} worst {best['worst loss dB']:+.2f} dB at {best['at deg']:.1f} deg", flush=True)
    return rows, retrained, grids


s0 = sim_for("configs/fr2_4el_survey.yaml")
t0 = banner("ex14  how many predistorters does a scanning array need? (ROADMAP B8)", s0)

print(f"\nPart 1 — 4 x 1, {SCHEME_LABELS['per_element']}, worst ACLR1 loss vs retraining over {EVAL[0]:.0f}-{EVAL[-1]:.0f} deg ({len(EVAL)} angles):")
rows1, ret1, GRIDS = study("configs/fr2_4el_survey.yaml", "per_element", GRIDS, EVAL, label="4 x 1",
                           curvature=(5,) if smoke() else (5, 6, 7))
print(table([{k: v for k, v in r.items() if k != "losses"} for r in rows1]))
ok = [r for r in rows1 if r["worst loss dB"] <= TARGET_DB]
winner = min(ok, key=lambda r: (r["banks"], r["worst loss dB"])) if ok else min(rows1, key=lambda r: r["worst loss dB"])
for mode in MODES:
    hit = [r for r in rows1 if r["rule"] == mode and r["worst loss dB"] <= TARGET_DB]
    few = min(hit, key=lambda r: (r["banks"], r["worst loss dB"])) if hit else None
    print(f"  rule {mode:7}: " + (f"fewest banks with worst <= {TARGET_DB} dB: {few['banks']} ({few['table']}, worst {few['worst loss dB']:+.2f} dB)"
                                  if few else f"no table here reaches {TARGET_DB} dB (best {min(r['worst loss dB'] for r in rows1 if r['rule'] == mode):+.2f} dB)"))
print(f"  -> winner: {winner['table']} with rule {winner['rule']} ({winner['banks']} banks, worst {winner['worst loss dB']:+.2f} dB at {winner['at deg']:.1f} deg)")

rows2 = []
if not smoke():
    chosen = {winner["table"]: GRIDS[winner["table"]], "uniform 30": GRIDS["uniform 30"]}
    print(f"\nPart 2 — the winner with the {SCHEME_LABELS['array']} (4 x 1):")
    rows2, _, _ = study("configs/fr2_4el_survey.yaml", "array", chosen, EVAL, label="4 x 1 array")
    print(table([{k: v for k, v in r.items() if k != "losses"} for r in rows2 if r["rule"] == winner["rule"]]))
    # 8 x 8: evaluated on the winner's grid angles AND halfway between them (an
    # evaluation set equal to the grid would score every table 0 dB by construction)
    wg = [float(a) for a in GRIDS[winner["table"]]]
    ev8 = sorted(set(wg) | {0.5 * (a + b) for a, b in zip(wg[:-1], wg[1:])})
    print(f"\nPart 3 — the winner on 8 x 8 (4 symbols, per-element DPD, at its {len(wg)} grid angles and the {len(wg) - 1} midpoints):")
    rows3, _, _ = study("configs/fr2_8x8_survey.yaml", "per_element", {winner["table"]: wg}, ev8, n_symbols=4, label="8 x 8",
                        modes=("nearest", winner["rule"]) if winner["rule"] != "nearest" else ("nearest",))
    print(table([{k: v for k, v in r.items() if k != "losses"} for r in rows3 if r["rule"] == winner["rule"]]))
    rows2 += rows3

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
names = list(GRIDS)
for mode, mk in zip(MODES, ("v:", "o-", "s-", "^-")):
    pts = sorted((next(r for r in rows1 if r["table"] == n and r["rule"] == mode) for n in names), key=lambda r: r["banks"])
    # several grids share a bank count: points only, no line through them
    ax[0].plot([p["banks"] for p in pts], [p["worst loss dB"] for p in pts], mk[0], label=mode, ms=5, alpha=0.8)
ax[0].axhline(TARGET_DB, color="#8a8a85", lw=0.8, ls="--")
ax[0].set(xlabel="predistorters in the table (grid angles)", ylabel="worst ACLR1 loss vs retraining [dB]",
          title="4 x 1, per-element DPD, load pull on" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7, title="rule between grid angles", title_fontsize=7)
for name, col in ((winner["table"], "#2a78d6"), ("uniform 30", "#d6652a")):
    r = next(x for x in rows1 if x["table"] == name and x["rule"] == winner["rule"])
    ax[1].plot(EVAL, r["losses"], "o-", ms=3, color=col, label=f"{name} ({r['banks']} banks)")
    for g in GRIDS[name]:
        ax[1].axvline(g, color=col, lw=0.5, alpha=0.3)
ax[1].axhline(TARGET_DB, color="#8a8a85", lw=0.8, ls="--")
ax[1].set(xlabel="beam [deg]", ylabel="ACLR1 loss vs retraining [dB]", title=f"rule '{winner['rule']}': where the loss sits")
ax[1].legend(fontsize=7)
done(t0, fig, "ex14_dpd_table_step.png")
