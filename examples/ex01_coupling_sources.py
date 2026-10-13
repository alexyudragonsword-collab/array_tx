"""ex01 — the three coupling sources side by side.

analytic (flat c1/c2), survey (published magnitude, linear phase from the
free-space path delay) and touchstone (an .s4p written from the analytic
matrix, read back) are built from three configs that differ in ONE key and
go through the one apply_coupling.  Part 1 prints |S| and phase at f0 and
the frequency dependence; Part 2 runs the three DPD schemes under each
source at the 30 deg beam and reads OTA EVM / ACLR; the touchstone column
must equal the analytic one bit for bit.
"""
import os

import numpy as np

from _common import OUT, SCHEME_COLORS, SCHEME_LABELS, SOURCE_COLORS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.coupling import build_coupling, write_matrix_touchstone
from arraytx.geometry import LinearArray
from arraytx.report import table

cfgs = {"analytic": load_config("configs/fr2_4el_analytic.yaml"),
        "survey": load_config("configs/fr2_4el_survey.yaml")}
geom = LinearArray(4, 0.5, 28e9)
fs = 4096 * 120e3 * 4
s4p = os.path.join(OUT, "analytic_4el.s4p")
write_matrix_touchstone(s4p, build_coupling(cfgs["analytic"], geom, fs), comments=("ex01: written from the analytic config",))
ct = load_config("configs/fr2_4el_touchstone.yaml")
ct.coupling.touchstone.path = s4p
cfgs["touchstone"] = ct

sims = {k: ArraySim(c) for k, c in cfgs.items()}
t0 = banner("ex01  coupling sources: analytic / survey / touchstone", sims["survey"])

print("\nPart 1 — S at f0 (adjacent S21, next-adjacent S31), dB / deg:")
rows = []
for k, s in sims.items():
    m = s.coupling.at(geom.f0_hz)
    rows.append({"source": k, "|S21| dB": 20 * np.log10(abs(m[1, 0])), "arg S21 deg": np.degrees(np.angle(m[1, 0])),
                 "|S31| dB": 20 * np.log10(abs(m[2, 0])), "arg S31 deg": np.degrees(np.angle(m[2, 0])),
                 "grid pts": s.coupling.freqs_hz.size})
print(table(rows))
same = np.array_equal(sims["analytic"].coupling.s, sims["touchstone"].coupling.s)
print(f"touchstone == analytic (matrix, bit for bit): {same}")

print("\nPart 2 — OTA metrics at the 30 deg beam, three schemes x three sources:")
theta0 = 30.0
schemes = ("none", "per_element", "array")
res = {(k, s): sims[k].run(theta0, s) for k in sims for s in schemes}
rows = []
for s in schemes:
    row = {"scheme": SCHEME_LABELS[s]}
    for k in sims:
        r = res[(k, s)]
        row[f"{k} ACLR1"] = r.beam.aclr1_db
        row[f"{k} EVM dB"] = r.beam.evm_db
    rows.append(row)
print(table(rows))
for s in schemes:
    a, t = res[("analytic", s)], res[("touchstone", s)]
    print(f"  {s:12s}: touchstone far field == analytic far field bit for bit: "
          f"{np.array_equal(a.far['beam'][1], t.far['beam'][1])}")
d = {s: res[('survey', s)].beam.aclr1_db - res[('analytic', s)].beam.aclr1_db for s in schemes}
print("\nsurvey - analytic ACLR1 at the beam [dB]: " + ", ".join(f"{s} {v:+.2f}" for s, v in d.items()))

f_rel = np.linspace(-fs / 2, fs / 2, 401)
fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
c1 = cfgs["survey"].coupling.survey.c1_db
for k, s in sims.items():
    m = s.coupling.at(geom.f0_hz + f_rel)
    s21 = m[:, 1, 0]
    s21_f0 = s.coupling.at(geom.f0_hz)[1, 0]
    ls = "--" if k == "touchstone" else "-"
    ax[0].plot(f_rel / 1e6, 20 * np.log10(np.abs(s21)), ls, color=SOURCE_COLORS[k], label=k)
    # phase relative to its own value at f0: analytic/touchstone are flat, the
    # survey slope is the free-space delay over one element pitch
    ax[1].plot(f_rel / 1e6, np.degrees(np.unwrap(np.angle(s21 / s21_f0))), ls, color=SOURCE_COLORS[k], label=k)
ax[0].set(xlabel="offset from f0 [MHz]", ylabel="|S21| [dB]", title="adjacent coupling magnitude", ylim=(c1 - 3, c1 + 1))
ax[1].set(xlabel="offset from f0 [MHz]", ylabel="arg S21 - arg S21(f0) [deg]", title="adjacent coupling phase (relative to f0)")
ax[0].legend(); ax[1].legend()
x = np.arange(len(sims))
for i, s in enumerate(schemes):
    vals = [res[(k, s)].beam.aclr1_db for k in sims]
    ax[2].plot(x + (i - 1) * 0.18, vals, "o", ms=8, color=SCHEME_COLORS[s], label=SCHEME_LABELS[s])
ax[2].set_xticks(x, list(sims))
ax[2].set_xlim(-0.6, len(sims) - 0.4)
ax[2].set(ylabel="OTA ACLR1 at the beam [dBc]  (lower is better)", title=f"beam {theta0:.0f} deg" + (" (smoke)" if smoke() else ""))
ax[2].legend(fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.02), ncol=1)
done(t0, fig, "ex01_coupling_sources.png")
