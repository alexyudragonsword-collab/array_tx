"""ex13 — does the |Gamma| guard decide any number?

``element.pa.load_pull.gamma_max`` clips |Gamma_k| per sample (proposal:
"a guard, not physics", 0.5).  ``info["load_pull"]["clip_fraction"]`` says
how often it acted.  If it acts, the load-pull results depend on a guard,
so this example re-runs the decisive points at gamma_max = 0.5 / 0.8 / 1.0:

  Part 1  4 x 1 (ex09 / ex10 Part B / ex11 / ex12 live here): clip fraction
          at full size, polar and outphasing (rho 0.1);
  Part 2  8 x 8 (ex10 Part A, 4 symbols): ACLR1 of the three schemes at
          0 and 60 deg, the loaded array efficiency, interior vs edge, the
          DPD trained at 0 deg used at 60 deg, and the fixed-point deltas
          (does the iteration still converge when larger Gamma is allowed?).
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.dpd import predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

GMAX = [0.5, 1.0] if smoke() else [0.5, 0.8, 1.0]
N_SYMBOLS_GRID = 2 if smoke() else 4


def sim_for(path, gmax, *, topology="polar", rho=0.0, n_symbols=None):
    cfg = load_config(path)
    cfg.element.topology = topology
    cfg.element.outphasing.source_impedance_rel = rho
    cfg.element.pa.load_pull.enabled = True
    cfg.element.pa.load_pull.gamma_max = gmax
    return ArraySim(cfg, n_symbols=n_symbols)


def clip(r):
    return 100.0 * float(np.mean(r.info["load_pull"]["clip_fraction"])), 100.0 * float(np.max(r.info["load_pull"]["clip_fraction"]))


s0 = sim_for("configs/fr2_8x8_survey.yaml", 0.5, n_symbols=N_SYMBOLS_GRID)
t0 = banner("ex13  does the |Gamma| guard (gamma_max) decide any load-pull number?", s0)

print("\nPart 1 — 4 x 1 at full size: how often the guard acts at gamma_max 0.5 (no DPD):")
rows1 = []
for name, topo, rho in (("polar", "polar", 0.0), ("outphasing rho 0.1", "outphasing", 0.1)):
    sim = sim_for("configs/fr2_4el_survey.yaml", 0.5, topology=topo, rho=rho)
    for th in (0.0, 30.0, 60.0):
        r = sim.run(th, "none", conducted_diagnostics=False)
        cm, cx = clip(r)
        rows1.append({"array": "4 x 1", "topology": name, "beam deg": th, "clip mean %": cm, "clip max elem %": cx,
                      "|G| max": max(r.info["load_pull"]["abs_gamma_max"])})
print(table(rows1))

print(f"\nPart 2 — 8 x 8 ({N_SYMBOLS_GRID} symbols), polar, load pull on, vs gamma_max:")
g = s0.geom
edge = (g.ix == 0) | (g.ix == g.n_x - 1) | (g.iy == 0) | (g.iy == g.n_y - 1)
rows2, rows3 = [], []
for gm in GMAX:
    sim = sim_for("configs/fr2_8x8_survey.yaml", gm, n_symbols=N_SYMBOLS_GRID)
    banks = {}
    for th in (0.0, 60.0):
        for sch in ("none", "per_element", "array"):
            r = sim.run(th, sch, conducted_diagnostics=False)
            if th == 0.0 and sch != "none":
                banks[sch] = r.dpd
            e, lp = r.info["efficiency"], r.info["load_pull"]
            v = 100 * np.array(e["eta_loaded_per_element"])
            cm, cx = clip(r)
            rows2.append({"gamma_max": gm, "beam deg": th, "scheme": SCHEME_LABELS[sch], "ACLR1": r.beam.aclr1_db, "EVM": r.beam.evm_db,
                          "eta loaded %": 100 * e["eta_array_loaded"], "inner %": v[~edge].mean(), "edge %": v[edge].mean(),
                          "clip mean %": cm, "clip max %": cx, "delta 2": lp["deltas"][-1], "s": r.seconds})
            print(f"  gmax {gm:.1f} {th:3.0f} deg {SCHEME_LABELS[sch]:22}: ACLR1 {r.beam.aclr1_db:7.2f}  eta {100*e['eta_array_loaded']:5.2f} %"
                  f"  clip {cm:5.2f} % (max {cx:5.1f})  deltas {lp['deltas'][0]:.4f}/{lp['deltas'][-1]:.5f}  [{r.seconds:.0f} s]", flush=True)
    for sch, bank in banks.items():
        drives = predistort_drives(bank, sim.x, sim.geom, 60.0, sim.fs, sim.cfg.beam.steering)
        _, _, rs = sim.radiate(drives)
        moved = ota_metrics(sim.far_field(rs, 60.0), sim.wf, 60.0, "beam", offsets=(1,), with_sem=False).aclr1_db
        ret = next(x["ACLR1"] for x in rows2 if x["gamma_max"] == gm and x["beam deg"] == 60.0 and x["scheme"] == SCHEME_LABELS[sch])
        rows3.append({"gamma_max": gm, "scheme": SCHEME_LABELS[sch], "trained@0 used@60": moved, "retrained": ret, "penalty dB": moved - ret})
print(table(rows2))
print(table(rows3))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
for sch in ("none", "per_element", "array"):
    for th, mk in ((0.0, "o-"), (60.0, "s--")):
        pts = [x for x in rows2 if x["scheme"] == SCHEME_LABELS[sch] and x["beam deg"] == th]
        ax[0].plot([p["gamma_max"] for p in pts], [p["ACLR1"] for p in pts], mk, color=SCHEME_COLORS[sch],
                   label=f"{SCHEME_LABELS[sch]}, {th:.0f} deg")
ax[0].set(xlabel="gamma_max (the |Gamma| guard)", ylabel="8 x 8 OTA ACLR1 at the beam [dBc]", title="flat = the guard decides nothing" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7)
for th, mk in ((0.0, "o-"), (60.0, "s--")):
    pts = [x for x in rows2 if x["scheme"] == SCHEME_LABELS["none"] and x["beam deg"] == th]
    ax[1].plot([p["gamma_max"] for p in pts], [p["eta loaded %"] for p in pts], mk, color="#2a78d6", label=f"array eta, {th:.0f} deg")
    ax[1].plot([p["gamma_max"] for p in pts], [p["clip mean %"] for p in pts], mk, color="#d6652a", label=f"clip fraction %, {th:.0f} deg")
ax[1].set(xlabel="gamma_max", ylabel="% ", title="8 x 8, no DPD: loaded efficiency and how often the guard acts")
ax[1].legend(fontsize=7)
done(t0, fig, "ex13_gamma_guard_sensitivity.png")
