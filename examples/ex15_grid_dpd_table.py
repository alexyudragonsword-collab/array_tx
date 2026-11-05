"""ex15 — the DPD table on the 8 x 8 grid (the former ROADMAP B8, second half; closed).

ex14 answered B8 for 4 x 1 (nine predistorters on a 7.5 deg grid keep the
worst scan-angle ACLR1 loss <= 0.5 dB) and found the same table 0.87 dB short
on 8 x 8, at 56.25 deg: the grid compresses harder at large angles, and its
interior and edge elements see different active impedances (|1 + Gamma_k|
0.63 / 0.73 at broadside, 1.30 / 1.20 at 60 deg).  ex14 also refuted using
the ARRAY-mean |1 + Gamma| to place grid angles.

This example asks the 8 x 8 question with one more interpolation rule:

  angle     coefficients blended linearly in theta (the 4 x 1 winner);
  load      blended by the array-mean m(theta) = mean_k |1 + Gamma_k|;
  element   each element blended by ITS OWN m_k(theta) = |1 + Gamma_k|
            (``dpd.blend_banks`` with one weight per element): edge and
            interior elements interpolate on their own operating points.

Grids: the 7.5 deg table, 5 deg, and 7.5 deg refined to 5 / 2.5 deg above 45
deg.  Every angle 0-60 deg in 2.5 deg steps is evaluated against retraining
there (4 symbols per run; one 8 x 8 per-element training is ~35 s).
"""
import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.beam import steer
from arraytx.dpd import blend_banks, predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

CFG = "configs/fr2_8x8_survey.yaml"
N_SYMBOLS = 2 if smoke() else 4
EVAL = [0.0, 22.5, 45.0] if smoke() else [float(a) for a in np.arange(0.0, 60.0 + 1e-9, 2.5)]
G75 = [0.0, 7.5, 15.0, 22.5, 30.0, 37.5, 45.0, 52.5, 60.0]
GRIDS = {
    "uniform 7.5": G75,
    "uniform 5": [float(a) for a in np.arange(0.0, 60.0 + 1e-9, 5.0)],
    "7.5, 5 above 45": [0.0, 7.5, 15.0, 22.5, 30.0, 37.5, 45.0, 50.0, 55.0, 60.0],
    "7.5, 2.5 above 45": [0.0, 7.5, 15.0, 22.5, 30.0, 37.5, 45.0, 47.5, 50.0, 52.5, 55.0, 57.5, 60.0],
    # the first run found every 7.5 deg table worst at 40 deg, whatever was added above 45:
    # the bend is 30-45 deg, where edge and interior |1+Gamma_k| cross.  Refine there instead.
    "7.5, 5 in 30-45": [0.0, 7.5, 15.0, 22.5, 30.0, 35.0, 40.0, 45.0, 52.5, 60.0],
    "7.5, 2.5 in 30-45": [0.0, 7.5, 15.0, 22.5, 30.0, 32.5, 35.0, 37.5, 40.0, 42.5, 45.0, 52.5, 60.0],
    "10, 5 in 30-50": [0.0, 10.0, 20.0, 30.0, 35.0, 40.0, 45.0, 50.0, 60.0],
    # run 2: refining 30-45 moved the worst to 55 deg (52.5-60), so both bands need 5 deg
    "7.5, 5 above 30": [0.0, 7.5, 15.0, 22.5, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0],
    "10, 5 above 30": [0.0, 10.0, 20.0, 30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0],
}
#: the mid-band grids only with the angle rule: on the first four, load / element never beat it (ex15 run 1)
ANGLE_ONLY = {"7.5, 5 in 30-45", "7.5, 2.5 in 30-45", "10, 5 in 30-50", "7.5, 5 above 30", "10, 5 above 30"}
if smoke():
    GRIDS = {"uniform 45": [0.0, 45.0]}                     # smoke: the flow, not the answer
    ANGLE_ONLY = set()
RULES = ("angle", "load", "element")
TARGET_DB = 0.5


def m_elements(sim, theta):
    """|1 + Gamma_k| per element under the undistorted steered drives."""
    sim.radiate(steer(sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering))
    return np.array(sim.last_load_pull["abs_1pg_mean"])


def aclr_at(sim, bank, theta):
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False).aclr1_db


def weight(mk, lo, hi, theta, rule):
    if rule == "angle":
        return (theta - lo) / (hi - lo)
    if rule == "load":
        a, b, c = mk[lo].mean(), mk[theta].mean(), mk[hi].mean()
        return float(np.clip((b - a) / (c - a), 0.0, 1.0)) if c != a else 0.5
    d = mk[hi] - mk[lo]                                               # per element
    w = np.where(np.abs(d) > 1e-9, (mk[theta] - mk[lo]) / np.where(np.abs(d) > 1e-9, d, 1.0), (theta - lo) / (hi - lo))
    return np.clip(w, 0.0, 1.0)


cfg = load_config(CFG)
cfg.element.pa.load_pull.enabled = True
if smoke():
    cfg.array.n_elements, cfg.array.n_rows = 4, 4         # CI time: the 8 x 8 answer comes from the full run
sim = ArraySim(cfg, n_symbols=N_SYMBOLS)
t0 = banner("ex15  the DPD table on the 8 x 8 grid: step and interpolation rule (the former ROADMAP B8, closed by ex15)", sim)

angles = sorted({a for g in GRIDS.values() for a in g} | set(EVAL))
mk, retrained = {}, {}
for th in angles:
    mk[th] = m_elements(sim, th)
    r = sim.run(th, "per_element", conducted_diagnostics=False)
    retrained[th] = (r.dpd, r.beam.aclr1_db)
    edge = (sim.geom.ix == 0) | (sim.geom.ix == sim.geom.n_x - 1) | (sim.geom.iy == 0) | (sim.geom.iy == sim.geom.n_y - 1)
    print(f"  {th:5.1f} deg: retrained ACLR1 {r.beam.aclr1_db:7.2f} dBc   |1+G| edge {mk[th][edge].mean():.3f}  inner {mk[th][~edge].mean():.3f}"
          f"   [{r.seconds:.0f} s]", flush=True)

rows = []
for name, grid in GRIDS.items():
    for rule in (("angle",) if name in ANGLE_ONLY else RULES):
        losses = []
        for th in EVAL:
            lo = max(g for g in grid if g <= th + 1e-9)
            hi = min(g for g in grid if g >= th - 1e-9)
            bank = retrained[lo][0] if hi == lo else blend_banks(retrained[lo][0], retrained[hi][0], weight(mk, lo, hi, th, rule))
            losses.append(aclr_at(sim, bank, th) - retrained[th][1])
        i = int(np.argmax(losses))
        rows.append({"table": name, "banks": len(grid), "rule": rule, "worst loss dB": losses[i], "at deg": EVAL[i],
                     "mean loss dB": float(np.mean(losses)), "losses": losses})
        print(f"  {name:18} ({len(grid):2d} banks) rule {rule:7}: worst {losses[i]:+.2f} dB at {EVAL[i]:.1f} deg, mean {np.mean(losses):+.2f}", flush=True)

print(table([{k: v for k, v in r.items() if k != "losses"} for r in rows]))
ok = [r for r in rows if r["worst loss dB"] <= TARGET_DB]
if ok:
    best = min(ok, key=lambda r: (r["banks"], r["worst loss dB"]))
    print(f"  -> fewest banks with worst <= {TARGET_DB} dB on 8 x 8: {best['banks']} ({best['table']}, rule {best['rule']}, worst {best['worst loss dB']:+.2f} dB)")
else:
    best = min(rows, key=lambda r: r["worst loss dB"])
    print(f"  -> no table here reaches {TARGET_DB} dB on 8 x 8; best {best['table']} / {best['rule']} at {best['worst loss dB']:+.2f} dB")
for rule in RULES:
    rr = [r for r in rows if r["rule"] == rule]
    if not rr:
        continue
    print(f"  rule {rule:7}: " + ", ".join(f"{r['table']} {r['worst loss dB']:+.2f}" for r in rr))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
for rule, mk_ in zip(RULES, ("o", "s", "^")):
    rr = sorted((r for r in rows if r["rule"] == rule), key=lambda r: r["banks"])
    ax[0].plot([r["banks"] for r in rr], [r["worst loss dB"] for r in rr], mk_, ms=6, alpha=0.8, label=rule)
ax[0].axhline(TARGET_DB, color="#8a8a85", lw=0.8, ls="--")
ax[0].set(xlabel="predistorters in the table", ylabel="worst ACLR1 loss vs retraining [dB]",
          title="8 x 8, per-element DPD, load pull on" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7, title="rule between grid angles", title_fontsize=7)
r = min(rows, key=lambda r: r["worst loss dB"]) if not ok else best
for rule, col in zip(RULES, ("#2a78d6", "#d6652a", "#5a9e3c")):
    rr = next((x for x in rows if x["table"] == r["table"] and x["rule"] == rule), None)
    if rr is None:
        continue
    ax[1].plot(EVAL, rr["losses"], "o-", ms=3, color=col, label=rule)
for g in GRIDS[r["table"]]:
    ax[1].axvline(g, color="#e2e2dd", lw=0.8, zorder=0)
ax[1].axhline(TARGET_DB, color="#8a8a85", lw=0.8, ls="--")
ax[1].set(xlabel="beam [deg]", ylabel="ACLR1 loss vs retraining [dB]", title=f"{r['table']} ({r['banks']} banks): where the loss sits")
ax[1].legend(fontsize=7)
done(t0, fig, "ex15_grid_dpd_table.png")
