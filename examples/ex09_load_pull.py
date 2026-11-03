"""ex09 — load modulation: when the coupled wave moves the PA's operating
point (ROADMAP A2; model and predictions in cairn/load-pull-proposal.md).

With milestone 1's linear leakage the two DPD schemes could not be told
apart at the beam.  Here each element's DPA compresses on its total port
swing |1 + Gamma_k|, Gamma_k being the active reflection coefficient the
coupling leakage produces (two fixed-point rounds).  The proposal predicts:

  1. single beam, identical elements -> Gamma_k is a constant per element
     (the active impedance), so per-element DPD still compensates at its
     training angle;
  2. what separates the schemes is (a) a DPD trained at one scan angle and
     used at another, (b) the time-varying part of Gamma_k that element
     deviations add, (c) the twelve-neighbour interior of a grid.

Part 1: |1 + Gamma_k| per element (mean and spread over time), 4 x 1 and
8 x 8, 0 / 30 / 60 deg, errors on and off.  Part 2: the three schemes at
their training angle, load pull off vs on.  Part 3: DPDs trained at 0 deg
applied at 30 and 60 deg, against retraining.  Part 4: the deviation-
driven residual (errors on vs off).
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.dpd import predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

CFG = "configs/fr2_4el_survey.yaml"
ANGLES = [0.0, 30.0, 60.0]


def sim_for(n_x=4, n_y=1, *, load_pull=True, errors=True):
    cfg = load_config(CFG)
    cfg.array.n_elements, cfg.array.n_rows = n_x, n_y
    cfg.element.pa.load_pull.enabled = load_pull
    cfg.element.errors.enabled = errors
    return ArraySim(cfg)


def beam_metrics_at(sim, bank, theta):
    """Apply an already trained bank at ``theta`` (no retraining)."""
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False)


s_on = sim_for()
t0 = banner("ex09  load modulation: the coupled wave moves the PA's operating point", s_on)

print("\nPart 1 — |1 + Gamma_k| per element (mean / std over time), no DPD:")
rows = []
layouts = [("4 x 1", 4, 1)] if smoke() else [("4 x 1", 4, 1), ("8 x 8", 8, 8)]
for name, nx, ny in layouts:
    for errors in (False, True):
        sim = sim_for(nx, ny, errors=errors)
        for th in ANGLES:
            r = sim.run(th, "none", conducted_diagnostics=False)
            lp = r.info["load_pull"]
            m, sd = np.array(lp["abs_1pg_mean"]), np.array(lp["abs_1pg_std"])
            edge = [k for k in range(sim.geom.n) if sim.geom.ix[k] in (0, nx - 1) or sim.geom.iy[k] in (0, ny - 1)]
            inner = [k for k in range(sim.geom.n) if k not in edge]
            rows.append({"array": name, "errors": errors, "beam deg": th, "mean edge": m[edge].mean(),
                         "mean inner": m[inner].mean() if inner else float("nan"), "max std": sd.max(),
                         "max |Gamma|": max(lp["abs_gamma_max"]), "delta 1": lp["deltas"][0], "delta 2": lp["deltas"][1],
                         "EVM": r.beam.evm_db, "ACLR1": r.beam.aclr1_db, "s": r.seconds})
            print(f"  {name} errors={errors!s:5} {th:3.0f} deg: |1+G| edge {m[edge].mean():.3f}"
                  + (f" inner {m[inner].mean():.3f}" if inner else "") + f"  std max {sd.max():.4f}  deltas {lp['deltas'][0]:.4f}/{lp['deltas'][1]:.5f}  [{r.seconds:.1f} s]", flush=True)
print(table(rows))

print("\nPart 2 — three schemes at their training angle, load pull off vs on (4 x 1, errors on; OTA beam ACLR1 dBc / EVM dB):")
s_off = sim_for(load_pull=False)
rows2 = []
for th in ANGLES:
    for sch in ("none", "per_element", "array"):
        a, b = s_off.run(th, sch, conducted_diagnostics=False), s_on.run(th, sch, conducted_diagnostics=False)
        rows2.append({"beam deg": th, "scheme": SCHEME_LABELS[sch], "ACLR1 off": a.beam.aclr1_db, "ACLR1 on": b.beam.aclr1_db,
                      "EVM off": a.beam.evm_db, "EVM on": b.beam.evm_db})
print(table(rows2))
for th in ANGLES:
    pe = next(x for x in rows2 if x["beam deg"] == th and x["scheme"] == SCHEME_LABELS["per_element"])
    ar = next(x for x in rows2 if x["beam deg"] == th and x["scheme"] == SCHEME_LABELS["array"])
    print(f"  {th:.0f} deg: array - per-element ACLR1 = {ar['ACLR1 on'] - pe['ACLR1 on']:+.2f} dB with load pull ({ar['ACLR1 off'] - pe['ACLR1 off']:+.2f} without)")

print("\nPart 3 — DPD trained at 0 deg, applied at 30 / 60 deg without retraining (load pull on), vs retrained:")
rows3 = []
banks = {sch: s_on.run(0.0, sch, conducted_diagnostics=False).dpd for sch in ("per_element", "array")}
for sch in ("per_element", "array"):
    for th in (30.0, 60.0):
        moved = beam_metrics_at(s_on, banks[sch], th)
        retrained = s_on.run(th, sch, conducted_diagnostics=False).beam
        rows3.append({"scheme": SCHEME_LABELS[sch], "beam deg": th, "ACLR1 trained@0": moved.aclr1_db, "ACLR1 retrained": retrained.aclr1_db,
                      "penalty": moved.aclr1_db - retrained.aclr1_db, "EVM trained@0": moved.evm_db, "EVM retrained": retrained.evm_db})
print(table(rows3))
if not smoke():
    s_off2 = sim_for(load_pull=False)
    banks0 = {sch: s_off2.run(0.0, sch, conducted_diagnostics=False).dpd for sch in ("per_element", "array")}
    for sch in ("per_element", "array"):
        m60 = beam_metrics_at(s_off2, banks0[sch], 60.0); r60 = s_off2.run(60.0, sch, conducted_diagnostics=False).beam
        print(f"  control, load pull OFF: {SCHEME_LABELS[sch]} trained@0 used@60: {m60.aclr1_db - r60.aclr1_db:+.2f} dB vs retrained")

print("\nPart 4 — the deviation-driven residual: errors on vs off, 60 deg, load pull on:")
for errors in (False, True):
    sim = sim_for(errors=errors)
    pe, ar = (sim.run(60.0, s, conducted_diagnostics=False) for s in ("per_element", "array"))
    print(f"  errors={errors!s:5}: per-element {pe.beam.aclr1_db:6.2f}  array {ar.beam.aclr1_db:6.2f}  diff {ar.beam.aclr1_db - pe.beam.aclr1_db:+.2f} dBc"
          f"  (|1+G| std max {max(pe.info['load_pull']['abs_1pg_std']):.4f})")

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
x = np.arange(len(ANGLES))
for i, sch in enumerate(("none", "per_element", "array")):
    off = [next(r["ACLR1 off"] for r in rows2 if r["beam deg"] == th and r["scheme"] == SCHEME_LABELS[sch]) for th in ANGLES]
    on = [next(r["ACLR1 on"] for r in rows2 if r["beam deg"] == th and r["scheme"] == SCHEME_LABELS[sch]) for th in ANGLES]
    ax[0].plot(x + (i - 1) * 0.18, off, "s", mfc="none", ms=7, color=SCHEME_COLORS[sch])
    ax[0].plot(x + (i - 1) * 0.18, on, "o", ms=7, color=SCHEME_COLORS[sch], label=SCHEME_LABELS[sch])
ax[0].set_xticks(x, [f"{t:.0f} deg" for t in ANGLES]); ax[0].set_xlim(-0.6, len(ANGLES) - 0.4)
ax[0].set(ylabel="OTA ACLR1 at the beam [dBc]  (lower is better)", title="open = linear leakage, filled = load pull" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=8)
for sch in ("per_element", "array"):
    ths = [r["beam deg"] for r in rows3 if r["scheme"] == SCHEME_LABELS[sch]]
    ax[1].plot(ths, [r["penalty"] for r in rows3 if r["scheme"] == SCHEME_LABELS[sch]], "o-", color=SCHEME_COLORS[sch], label=SCHEME_LABELS[sch])
ax[1].axhline(0, color="#8a8a85", lw=0.8)
ax[1].set(xlabel="beam used at [deg]", ylabel="ACLR1 penalty of the DPD trained at 0 deg [dB]", title="scan-angle mismatch under load pull")
ax[1].legend(fontsize=8)
done(t0, fig, "ex09_load_pull.png")
