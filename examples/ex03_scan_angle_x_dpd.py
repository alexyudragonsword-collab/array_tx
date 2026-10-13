"""ex03 — scan angle x DPD scheme: the milestone-1 table.

Part 1: OTA EVM / ACLR1 / ACLR2 in the beam direction and in the highest
sidelobe direction for 0 / 30 / 60 deg x {no DPD, per-element, array}, under
the default (survey) coupling with phase-shifter steering, plus the 60 deg
row with true time delay.  Part 2: the band-edge squint at each angle,
measured on the array factor against the closed form.  Part 3: the
conducted-port numbers, printed as diagnostics only.
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, diagnostic_table, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.beam import peak_direction_cw, squint_analytic_deg
from arraytx.report import table

cfg = load_config("configs/fr2_4el_survey.yaml")
sim = ArraySim(cfg)
t0 = banner("ex03  scan angle x DPD scheme (OTA, survey coupling)", sim)
schemes = ("none", "per_element", "array")
scan = list(cfg.beam.scan_deg)

res = sim.run_matrix(scan, schemes)
rows = []
for th in scan:
    for s in schemes:
        r = res[(th, s)]
        rows.append({"beam deg": th, "scheme": SCHEME_LABELS[s],
                     "EVM dB": r.beam.evm_db, "ACLR1": r.beam.aclr1_db, "ACLR2": r.beam.aclr2_db,
                     "sidelobe deg": r.sidelobe_deg if r.sidelobe_deg is not None else float("nan"),
                     "SL EVM": r.sidelobe.evm_db if r.sidelobe else float("nan"),
                     "SL ACLR1": r.sidelobe.aclr1_db if r.sidelobe else float("nan"),
                     "s": r.seconds})
print("\nPart 1 — OTA metrics, phase-shifter steering (ACLR in dBc, EVM in dB):")
print(table(rows))
cfg_t = load_config("configs/fr2_4el_survey.yaml")
cfg_t.beam.steering = "ttd"
sim_t = ArraySim(cfg_t)
trow = []
for s in schemes:
    r = sim_t.run(60.0, s)
    trow.append({"beam deg": 60.0, "steering": "ttd", "scheme": SCHEME_LABELS[s], "EVM dB": r.beam.evm_db,
                 "ACLR1": r.beam.aclr1_db, "SL ACLR1": r.sidelobe.aclr1_db if r.sidelobe else float("nan")})
print("\n60 deg with true time delay:")
print(table(trow))

print("\nheadline (beam direction, ACLR1):")
for th in scan:
    n, pe, ar = (res[(th, s)].beam.aclr1_db for s in schemes)
    print(f"  {th:4.0f} deg: no DPD {n:6.1f} | per-element {pe:6.1f} ({pe - n:+.1f}) | array {ar:6.1f} ({ar - n:+.1f}) "
          f"| array - per-element {ar - pe:+.2f} dB")

print("\nPart 2 — band-edge squint (phase-shifter steering), measured on the array factor vs closed form:")
srows = []
for th in scan:
    for df in (-200e6, 200e6):
        meas = peak_direction_cw(sim.geom, th, df, "phase") - th
        ana = squint_analytic_deg(th, sim.f0, df)
        srows.append({"beam deg": th, "df MHz": df / 1e6, "measured deg": meas, "analytic deg": ana,
                      "error %": (abs(meas - ana) / abs(ana) * 100) if ana else 0.0})
print(table(srows))

print("\nPart 3 — " + diagnostic_table(res[(30.0, "none")]))

fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
x = np.arange(len(scan))
for i, s in enumerate(schemes):
    ax[0].plot(x + (i - 1) * 0.18, [res[(th, s)].beam.aclr1_db for th in scan], "o", ms=8, color=SCHEME_COLORS[s], label=SCHEME_LABELS[s])
    ax[0].plot(x + (i - 1) * 0.18, [res[(th, s)].sidelobe.aclr1_db for th in scan], "^", ms=7, mfc="none", color=SCHEME_COLORS[s])
    ax[1].plot(x + (i - 1) * 0.18, [res[(th, s)].beam.evm_db for th in scan], "o", ms=8, color=SCHEME_COLORS[s], label=SCHEME_LABELS[s])
for a, yl, tt in ((ax[0], "OTA ACLR1 [dBc]  (lower is better)", "ACLR1 vs scan angle: beam (dots), highest sidelobe (open triangles)"),
                  (ax[1], "OTA EVM at the beam [dB]  (lower is better)", "EVM vs scan angle")):
    a.set_xticks(x, [f"{th:.0f} deg" for th in scan]); a.set_xlim(-0.6, len(scan) - 0.4)
    a.set(ylabel=yl, title=tt + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=8, loc="lower left", bbox_to_anchor=(0, 1.08), ncol=3)
done(t0, fig, "ex03_scan_x_dpd.png")
