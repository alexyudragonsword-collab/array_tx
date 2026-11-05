"""ex18 — which part of the coupling matrix does the design table actually depend on?

ex17 moved the adjacent coupling MAGNITUDE and found it the most sensitive
assumption; on 8 x 8 it also found a ceiling (-13 dB is refused as not
passive).  The rest of the survey matrix is assumed too (config ``ref``):

  c1 phase    the adjacent coupling's phase at f0, 180 deg ("sign convention");
  c1y_rel     coupling to the next ROW relative to along the row, 0 dB (E- and
              H-plane equal -- patches usually differ by several dB);
  c_diag_rel  the diagonal neighbour, -6 dB;
  phase_from_distance  farther classes carry their extra electrical length.

Part 1  the passive ceiling on 8 x 8: the adjacent coupling at which the
        leakage alone reaches gain 1, against each shape parameter (no runs;
        a global phase cannot change it -- singular values ignore it).
Part 2  what the PAs see: the mean |1 + Gamma| (undistorted steered drives,
        one radiate each) against scan angle for c1 phase 0 / 90 / 180 / 270.
Part 3  4 x 1 design table (ex16 grid) for the four c1 phases.
Part 4  8 x 8 design table (0 / 30 / 60 deg) for c1 phase 0 / 90 deg, the
        E/H difference c1y_rel -3 dB, and -3 dB with c1 -13 dB (passive then).
Targets as ex16 (assumed design choices).
"""
import numpy as np

from _common import TABLE_MARGIN_DB, banner, design_sweep, design_table, done, element_loads, plt, same_setting, smoke
from arraytx import ArraySim, load_config
from arraytx.coupling import build_coupling
from arraytx.report import table

CFG4, CFG8 = "configs/fr2_4el_survey.yaml", "configs/fr2_8x8_survey.yaml"
PHASES = [180.0, 0.0] if smoke() else [180.0, 90.0, 0.0, 270.0]
LOAD_ANGLES = [0.0, 60.0] if smoke() else [float(a) for a in np.arange(0.0, 60.0 + 1e-9, 7.5)]
A4 = [0.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0]
B4 = [0.0, 2.0] if smoke() else [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
C4 = [8.5] if smoke() else [8.5, 7.5, 6.5]
A8, B8, C8 = [0.0, 30.0, 60.0], [0.0, 1.0, 2.0, 3.0, 4.0, 5.0], [8.5, 6.5]


def shape(**survey):
    """A tweak that sets fields of ``coupling.survey`` (and ``scale_db`` if given)."""
    scale = survey.pop("scale_db", None)

    def tweak(cfg):
        for k, v in survey.items():
            setattr(cfg.coupling.survey, k, v)
        if scale is not None:
            cfg.coupling.scale_db = scale
    return tweak


def sim_for(path, tweak=None, n_symbols=None):
    cfg = load_config(path)
    cfg.element.pa.load_pull.enabled = True
    if tweak is not None:
        tweak(cfg)
    if smoke() and cfg.array.n_rows > 1:
        cfg.array.n_elements, cfg.array.n_rows = 4, 4          # CI time: the 8 x 8 numbers come from the full run
    return ArraySim(cfg, n_symbols=n_symbols)


s4 = sim_for(CFG4)
t0 = banner("ex18  which part of the coupling matrix the design table depends on: phase, E/H, diagonal, ceiling", s4)

# ------------------------------------------------------------------ Part 1: passive ceiling
s8 = sim_for(CFG8, n_symbols=2)
print(f"\nPart 1 — the passive ceiling: adjacent coupling at which the leakage alone reaches gain 1 "
      f"({s8.geom.n_x} x {s8.geom.n_y}, survey shape):")
base_c1 = load_config(CFG8).coupling.survey.c1_db


def ceiling(**kw):
    cfg = load_config(CFG8)
    shape(**kw)(cfg)
    cfg.coupling.scale_db = -20.0                                 # far from the ceiling; the gain scales linearly
    g = build_coupling(cfg, s8.geom, s8.fs).max_gain() * 10.0
    return g, base_c1 - 20.0 * np.log10(g)


rows1 = []
for label, kw in [("baseline (c1 180 deg, c1y 0 dB, diag -6 dB)", {}),
                  *[(f"c1 phase {p:.0f} deg", {"c1_deg_at_f0": p}) for p in PHASES[1:]],
                  *[(f"c1y_rel {cy:.0f} dB, diag {cd:.0f} dB", {"c1y_rel_db": cy, "c_diag_rel_db": cd})
                    for cy in (0.0, -3.0, -6.0, -10.0) for cd in (-6.0, -10.0) if (cy, cd) != (0.0, -6.0)],
                  ("phase_from_distance off", {"phase_from_distance": False})]:
    g, lim = ceiling(**kw)
    rows1.append({"shape": label, f"leakage gain @ {base_c1:.0f} dB": g, "ceiling c1 dB": lim})
print(table(rows1))

# ------------------------------------------------------------------ Part 2: |1 + Gamma| vs angle
print("\nPart 2 — mean |1 + Gamma| the undistorted steered drives put on the PAs, vs the adjacent coupling phase:")
loads = {}
for lab, path in (("4 x 1", CFG4), (f"{s8.geom.n_x} x {s8.geom.n_y}", CFG8)):
    for ph in PHASES:
        sim = sim_for(path, shape(c1_deg_at_f0=ph), n_symbols=None if lab == "4 x 1" else 2)
        loads[(lab, ph)] = [float(element_loads(sim, th).mean()) for th in LOAD_ANGLES]
        print(f"  {lab} c1 phase {ph:5.0f} deg: " + "  ".join(f"{th:.1f}:{m:.3f}" for th, m in zip(LOAD_ANGLES, loads[(lab, ph)])),
              flush=True)


def schedule(d, angles):
    by = {x["beam deg"]: x for x in d}
    return " / ".join("-" if not np.isfinite(by[t]["backoff dB"]) else f"{by[t]['backoff dB']:.0f}" for t in angles)


def summary(designs, angles, label):
    base = {x["beam deg"]: x for x in next(iter(designs.values()))}
    out = []
    for name, d in designs.items():
        by = {x["beam deg"]: x for x in d}
        out.append({"case": name, f"backoff dB @ {'/'.join(f'{a:.0f}' for a in angles)}": schedule(d, angles),
                    "CFR dB @ " + "/".join(f"{a:.0f}" for a in angles): " / ".join(f"{by[t]['CFR dB']:.1f}" for t in angles),
                    "eta @ 0 %": by[0.0]["eta %"], f"eta @ {max(angles):.0f} %": by[max(angles)]["eta %"],
                    "eta min %": float(np.nanmin([x["eta %"] for x in d])) if any(np.isfinite(x["eta %"]) for x in d) else float("nan"),
                    "angles changed": sum(not same_setting(by[t], base[t]) for t in angles)})
    print(f"\n  {label}:")
    print(table(out))
    return out


# ------------------------------------------------------------------ Part 3: 4 x 1 design per phase
print("\nPart 3 — 4 x 1 design table (per-element DPD retrained per angle, load pull on) vs the adjacent coupling phase:")
designs4 = {}
for ph in PHASES:
    print(f"\n  case: c1 phase {ph:.0f} deg")
    rows = design_sweep(CFG4, A4, B4, C4, label="4 x 1", tweak=shape(c1_deg_at_f0=ph))
    designs4[f"c1 phase {ph:.0f} deg"], _ = design_table(rows, A4, "4 x 1", TABLE_MARGIN_DB["4 x 1"])
s3 = summary(designs4, A4, "4 x 1 summary")

# ------------------------------------------------------------------ Part 4: 8 x 8 design per shape
designs8 = {}
if not smoke():
    print(f"\nPart 4 — 8 x 8 (4 symbols) design table, 0 / 30 / 60 deg, table margin {TABLE_MARGIN_DB['8 x 8']} dB:")
    cases8 = {"baseline (c1 -16 dB, 180 deg, c1y 0 dB)": None,
              "c1 phase 0 deg": shape(c1_deg_at_f0=0.0),
              "c1 phase 90 deg": shape(c1_deg_at_f0=90.0),
              "c1y_rel -3 dB": shape(c1y_rel_db=-3.0),
              "c1y_rel -3 dB, c1 -13 dB": shape(c1y_rel_db=-3.0, scale_db=3.0)}
    for name, tweak in cases8.items():
        print(f"\n  case: {name}")
        rows = design_sweep(CFG8, A8, B8, C8, n_symbols=4, label="8 x 8", tweak=tweak)
        designs8[name], _ = design_table(rows, A8, "8 x 8", TABLE_MARGIN_DB["8 x 8"])
    summary(designs8, A8, "8 x 8 summary")

fig, ax = plt.subplots(1, 3, figsize=(15.5, 3.8))
cols = dict(zip([180.0, 90.0, 0.0, 270.0], ("#2a78d6", "#5a9e3c", "#d6652a", "#8a5ac8")))
for (lab, ph), m in loads.items():
    ax[0].plot(LOAD_ANGLES, m, "o-" if lab == "4 x 1" else "s--", ms=3, color=cols[ph], label=f"{lab}, c1 {ph:.0f} deg")
ax[0].axhline(1.0, color="#8a8a85", lw=0.8, ls=":")
ax[0].set(xlabel="beam [deg]", ylabel="mean |1 + Gamma| (undistorted drives)",
          title="what the PAs see vs the adjacent coupling phase" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=6, ncol=2)
for (name, d), ph in zip(designs4.items(), PHASES):
    ax[1].step([x["beam deg"] for x in d], [x["backoff dB"] for x in d], where="mid", color=cols[ph], label=name)
ax[1].set(xlabel="beam [deg]", ylabel="output backoff picked [dB]", title="4 x 1: backoff schedule vs c1 phase")
ax[1].legend(fontsize=7)
if designs8:
    for (name, d), mk in zip(designs8.items(), ("o-", "s--", "^--", "d:", "v-.")):
        ax[2].plot([x["beam deg"] for x in d], [x["eta %"] for x in d], mk, ms=5, label=name)
        for x in d:
            if np.isfinite(x["backoff dB"]):
                ax[2].annotate(f"{x['backoff dB']:.0f}", (x["beam deg"], x["eta %"]), textcoords="offset points", xytext=(4, 2), fontsize=6)
    ax[2].set(xlabel="beam [deg]", ylabel="array drain efficiency at the pick [%]", title="8 x 8: efficiency at the pick (label = backoff dB)")
    ax[2].legend(fontsize=6)
else:
    lims = [r["ceiling c1 dB"] for r in rows1]
    ax[2].barh(range(len(rows1)), lims, color="#2a78d6")
    ax[2].set_yticks(range(len(rows1)), [r["shape"] for r in rows1], fontsize=6)
    ax[2].set(xlabel="passive ceiling for the adjacent coupling [dB]", title="8 x 8: how strong c1 may be")
done(t0, fig, "ex18_coupling_shape.png")
