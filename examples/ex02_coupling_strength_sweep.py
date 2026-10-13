"""ex02 — OTA metrics vs coupling strength.

The survey coupling shape, scaled from no coupling (-inf) up to +6 dB
(adjacent coupling -10 dB), for the three DPD schemes at the 30 deg beam.
Acceptance 2: with the coupling at zero the three... two DPD schemes land on
the same OTA ACLR within 0.5 dB.  The curve shows how much the whole-array
DPD and the per-element DPD each care about the leakage.
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.report import table

base = load_config("configs/fr2_4el_survey.yaml")
scales = [-np.inf, -24.0, -18.0, -12.0, -6.0, 0.0, 6.0]
if smoke():
    scales = [-np.inf, -12.0, 0.0, 6.0]
schemes = ("none", "per_element", "array")
theta0 = 30.0

sim0 = ArraySim(base)
t0 = banner("ex02  coupling strength sweep (survey shape, scaled)", sim0)
c1 = base.coupling.survey.c1_db

rows, curves = [], {s: [] for s in schemes}
for sc in scales:
    cfg = load_config("configs/fr2_4el_survey.yaml")
    cfg.coupling.scale_db = float(sc)
    sim = ArraySim(cfg)
    row = {"scale dB": sc, "|S21| dB": sim.coupling.max_offdiag_db()}
    for s in schemes:
        r = sim.run(theta0, s)
        row[f"{s} ACLR1"] = r.beam.aclr1_db
        row[f"{s} EVM"] = r.beam.evm_db
        curves[s].append((r.beam.aclr1_db, r.beam.evm_db))
    rows.append(row)
print("\nOTA at the 30 deg beam vs coupling (ACLR1 dBc, EVM dB):")
print(table(rows))

z = rows[0]
spread = max(z[f"{s} ACLR1"] for s in schemes[1:]) - min(z[f"{s} ACLR1"] for s in schemes[1:])
print(f"\nS = 0: per-element vs array DPD ACLR1 spread {spread:.2f} dB (acceptance: < 0.5)")
last = rows[-1]
print(f"strongest coupling ({last['|S21| dB']:.0f} dB): none {last['none ACLR1']:.1f}, "
      f"per-element {last['per_element ACLR1']:.1f}, array {last['array ACLR1']:.1f} dBc")

xs = [c1 + sc for sc in scales]
xs[0] = c1 - 36.0 if scales[0] == -np.inf else xs[0]
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
for s in schemes:
    a = np.array(curves[s])
    ax[0].plot(xs, a[:, 0], "o-", ms=4, color=SCHEME_COLORS[s], label=SCHEME_LABELS[s])
    ax[1].plot(xs, a[:, 1], "o-", ms=4, color=SCHEME_COLORS[s], label=SCHEME_LABELS[s])
for a in ax:
    a.set_xlabel("adjacent coupling |S21| [dB]  (leftmost point = no coupling)")
    a.axvline(c1, color="#8a8a85", lw=0.8, ls=":")
ax[0].set(ylabel="OTA ACLR1 at the beam [dBc]", title="ACLR vs coupling (lower is better)")
ax[1].set(ylabel="OTA EVM at the beam [dB]", title="EVM vs coupling")
ax[0].legend(fontsize=8)
done(t0, fig, "ex02_coupling_sweep.png")
