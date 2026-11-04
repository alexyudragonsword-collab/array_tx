"""ex11 — one DPD for every scan angle, or one per angle?

ex09 / ex10: under load modulation a DPD trained at 0 deg loses ~2.8 dB of
ACLR1 at 60 deg (the active impedance moves with the scan, so the PA's
operating point does).  Without load pull the loss is 0.00 dB.  Two ways to
serve many angles with a fixed model:

  joint   one predistorter fitted jointly over 0 / 30 / 60 deg
          (``dpd.train_angles_deg``: the GMP bases of all angles stacked
          into one least-squares problem);
  table   one predistorter per angle on a 30 deg grid, picked at run time:
          ``nearest`` takes the grid angle with the larger |theta| (the more
          compressed side), ``interp`` blends the two neighbours'
          coefficients linearly (GMP is linear in its parameters).

against ``retrained`` (a fit at every angle: the bound) and ``trained@0``.
Evaluated at 0 / 15 / 30 / 45 / 60 deg, so 15 and 45 are angles no strategy
trained on.  4 x 1 full burst, then 8 x 8 at the grid angles.  Load pull on,
element errors on; OTA ACLR1 at the beam.
"""

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.dpd import blend_banks, predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

CFG_ROW, CFG_GRID = "configs/fr2_4el_survey.yaml", "configs/fr2_8x8_survey.yaml"
GRID = [0.0, 30.0, 60.0]
EVAL = [0.0, 30.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0]
SCHEMES = ("per_element",) if smoke() else ("per_element", "array")
N_SYMBOLS_GRID = 2 if smoke() else 4


def sim_for(cfg_path, *, load_pull=True, joint=None, n_symbols=None):
    cfg = load_config(cfg_path)
    cfg.element.pa.load_pull.enabled = load_pull
    if joint:
        cfg.dpd.train_angles_deg = list(joint)
    return ArraySim(cfg, n_symbols=n_symbols)


def apply(sim, bank, theta):
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False)


def table_bank(banks, theta, mode):
    lo = max(g for g in GRID if g <= theta)
    hi = min(g for g in GRID if g >= theta)
    if lo == hi:
        return banks[lo]
    if mode == "nearest":
        return banks[hi]
    return blend_banks(banks[lo], banks[hi], (theta - lo) / (hi - lo))


def study(cfg_path, evals, n_symbols=None):
    sim = sim_for(cfg_path, n_symbols=n_symbols)
    jsim = sim_for(cfg_path, joint=GRID, n_symbols=n_symbols)
    rows = []
    for sch in SCHEMES:
        retrained = {th: sim.run(th, sch, conducted_diagnostics=False) for th in sorted(set(evals) | set(GRID))}
        grid_banks = {g: retrained[g].dpd for g in GRID}
        for th in evals:
            r = {"scheme": SCHEME_LABELS[sch], "beam deg": th, "retrained": retrained[th].beam.aclr1_db,
                 "trained@0": apply(sim, grid_banks[0.0], th).aclr1_db,
                 "joint 0/30/60": jsim.run(th, sch, conducted_diagnostics=False).beam.aclr1_db}
            if th not in GRID:
                r["table nearest"] = apply(sim, table_bank(grid_banks, th, "nearest"), th).aclr1_db
                r["table interp"] = apply(sim, table_bank(grid_banks, th, "interp"), th).aclr1_db
            else:
                r["table nearest"] = r["table interp"] = r["retrained"]
            rows.append(r)
            print(f"  {SCHEME_LABELS[sch]:22} {th:3.0f} deg: retrained {r['retrained']:7.2f}  trained@0 {r['trained@0']:7.2f}  "
                  f"joint {r['joint 0/30/60']:7.2f}  table nearest {r['table nearest']:7.2f}  interp {r['table interp']:7.2f}", flush=True)
    return sim, rows


s0 = sim_for(CFG_ROW)
t0 = banner("ex11  one DPD for every scan angle, or one per angle (load modulation on)", s0)

print("\nPart 1 — 4 x 1, OTA beam ACLR1 dBc by training strategy (15 / 45 deg: no strategy trained there):")
_, rows1 = study(CFG_ROW, EVAL)
print(table(rows1))
for sch in SCHEMES:
    rs = [r for r in rows1 if r["scheme"] == SCHEME_LABELS[sch]]
    worst = {k: max(r[k] - r["retrained"] for r in rs) for k in ("trained@0", "joint 0/30/60", "table nearest", "table interp")}
    print(f"  {SCHEME_LABELS[sch]}: worst loss vs retrained over {', '.join(f'{t:.0f}' for t in EVAL)} deg -> "
          + "  ".join(f"{k} {v:+.2f} dB" for k, v in worst.items()))

print("\nPart 1' — control, load pull OFF (4 x 1, 60 deg): the strategies should agree")
off = sim_for(CFG_ROW, load_pull=False)
joff = sim_for(CFG_ROW, load_pull=False, joint=GRID)
for sch in SCHEMES:
    b0 = off.run(0.0, sch, conducted_diagnostics=False).dpd
    ret, moved = off.run(60.0, sch, conducted_diagnostics=False).beam.aclr1_db, apply(off, b0, 60.0).aclr1_db
    jo = joff.run(60.0, sch, conducted_diagnostics=False).beam.aclr1_db
    print(f"  {SCHEME_LABELS[sch]:22}: retrained {ret:7.2f}  trained@0 {moved:7.2f}  joint {jo:7.2f}")

rows2 = []
if not smoke():
    print(f"\nPart 2 — 8 x 8 ({N_SYMBOLS_GRID} symbols), grid angles only:")
    _, rows2 = study(CFG_GRID, GRID, n_symbols=N_SYMBOLS_GRID)
    print(table([{k: v for k, v in r.items() if not k.startswith("table")} for r in rows2]))

fig, ax = plt.subplots(1, len(SCHEMES), figsize=(5.4 * len(SCHEMES), 3.9), squeeze=False)
styles = {"retrained": ("k", "o-"), "trained@0": ("#d6652a", "s--"), "joint 0/30/60": ("#2a78d6", "^-"),
          "table nearest": ("#8a8a85", "v:"), "table interp": ("#5a9e3c", "d-")}
for a, sch in zip(ax[0], SCHEMES):
    rs = [r for r in rows1 if r["scheme"] == SCHEME_LABELS[sch]]
    for k, (col, st) in styles.items():
        a.plot([r["beam deg"] for r in rs], [r[k] for r in rs], st, color=col, label=k, ms=5)
    for g in GRID:
        a.axvline(g, color="#e2e2dd", lw=0.8, zorder=0)
    a.set(xlabel="beam [deg]  (grey lines: the angles a table / the joint fit trained on)", ylabel="OTA ACLR1 at the beam [dBc]",
          title=f"4 x 1, {SCHEME_LABELS[sch]}" + (" (smoke)" if smoke() else ""))
    a.legend(fontsize=7)
    a.title.set_color(SCHEME_COLORS[sch])
done(t0, fig, "ex11_multi_angle_dpd.png")
