"""ex16 — the scan design table: per scan angle, which output backoff, CFR
depth and DPD table, and what it costs in drain efficiency.

No new physics: this puts ex10 (backoff / CFR vs ACLR and efficiency), ex13
(the |Gamma| guard at 1.0), the loaded efficiency (Gamma in) and ex14 (the
DPD table and its interpolation loss) into one design answer.

Design targets (source: assumed -- design choices, not specification
limits): ACLR1 <= -45 dBc at the beam (about what the array reaches without
load modulation), EVM <= -25 dB (3 dB inside the 64-QAM 8 % limit, -21.9 dB,
TS 38.101-2).  The per-element DPD is retrained at each angle (the table
entry); the table's interpolation loss between entries is carried as an ACLR
margin per array (ex14: +0.30 dB on 4 x 1 with nine banks; ex15: +0.35 dB on
8 x 8 with ten).  The 60 deg setting used as the fixed baseline is checked
against the targets at every angle; where it fails, no gain is claimed.

For each angle: the Pareto front of ACLR1 vs array efficiency over
backoff x CFR, the most efficient point that meets both targets, and the
efficiency a FIXED setting (the one 60 deg needs) would cost at that angle.
"""
import numpy as np

from _common import (ACLR_TARGET_DBC, EVM_TARGET_DB, TABLE_MARGIN_DB, banner, design_sweep,
                     design_table, done, plt, smoke)
from arraytx import ArraySim, load_config
from arraytx.report import table

ANGLES = [0.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0]
BACKOFFS = [0.0, 2.0] if smoke() else [0.0, 1.0, 2.0, 3.0]
CFRS = [8.5] if smoke() else [8.5, 7.5, 6.5]


def pareto(pts):
    """Points not beaten on both lower ACLR1 and higher efficiency."""
    return sorted((p for p in pts if not any(q["ACLR1"] <= p["ACLR1"] and q["eta %"] >= p["eta %"] and q is not p
                                             and (q["ACLR1"] < p["ACLR1"] or q["eta %"] > p["eta %"]) for q in pts)),
                  key=lambda p: p["eta %"])


s0 = ArraySim(load_config("configs/fr2_4el_survey.yaml"))
t0 = banner("ex16  scan design table: backoff / CFR / DPD table per scan angle, priced in drain efficiency", s0)
print(f"  targets (assumed design choices): ACLR1 <= {ACLR_TARGET_DBC} dBc with the DPD table margin "
      f"({', '.join(f'{k} {v} dB' for k, v in TABLE_MARGIN_DB.items())}: ex14 / ex15), EVM <= {EVM_TARGET_DB} dB")

print("\nPart 1 — 4 x 1 full burst, per-element DPD retrained per angle, load pull on (ACLR1 dBc / array efficiency, Gamma in):")
rows1 = design_sweep("configs/fr2_4el_survey.yaml", ANGLES, BACKOFFS, CFRS, label="4 x 1")
d1, pick1 = design_table(rows1, ANGLES, "4 x 1", TABLE_MARGIN_DB["4 x 1"])
print(table(d1))

rows2, d2 = [], []
if not smoke():
    a8, b8, c8 = [0.0, 30.0, 60.0], [0.0, 2.0, 3.0], [8.5, 6.5]
    print("\nPart 2 — 8 x 8 (4 symbols), the same question on a coarser grid:")
    rows2 = design_sweep("configs/fr2_8x8_survey.yaml", a8, b8, c8, n_symbols=4, label="8 x 8")
    d2, _ = design_table(rows2, a8, "8 x 8", TABLE_MARGIN_DB["8 x 8"])
    print(table(d2))

for d in (d1, d2):
    if d and all(np.isfinite(x["eta %"]) for x in d):
        lab = d[0]["array"]
        print(f"  {lab}: adapting backoff / CFR to the scan angle instead of the 60 deg setting everywhere gains "
              + ", ".join(f"{x['beam deg']:.0f} deg {x['adaptive gain pts']:+.1f}" for x in d) + " efficiency points")

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
cols = plt.cm.viridis(np.linspace(0, 0.9, len(ANGLES)))
for th, col in zip(ANGLES, cols):
    pts = [x for x in rows1 if x["beam deg"] == th]
    ax[0].plot([p["eta %"] for p in pts], [p["ACLR1"] for p in pts], ".", color=col, alpha=0.35)
    fr = pareto(pts)
    ax[0].plot([p["eta %"] for p in fr], [p["ACLR1"] for p in fr], "o-", color=col, ms=4, label=f"{th:.0f} deg")
    if pick1.get(th):
        ax[0].plot(pick1[th]["eta %"], pick1[th]["ACLR1"], "*", color=col, ms=13, mec="k", mew=0.6)
ax[0].axhline(ACLR_TARGET_DBC - TABLE_MARGIN_DB["4 x 1"], color="#8a8a85", lw=0.8, ls="--")
ax[0].set(xlabel="array drain efficiency [%]  (Gamma in)", ylabel="OTA ACLR1 at the beam [dBc]",
          title="4 x 1: Pareto front per scan angle (star = design pick)" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7)
x = np.arange(len(d1))
ax[1].bar(x - 0.18, [r["eta %"] for r in d1], 0.36, color="#2a78d6", label="adapted per angle")
ax[1].bar(x + 0.18, [r["eta fixed %"] for r in d1], 0.36, color="#d6652a", label="60 deg setting everywhere")
for i, r in enumerate(d1):
    if np.isfinite(r["backoff dB"]):
        ax[1].annotate(f"CFR {r['CFR dB']:.1f}\nBO {r['backoff dB']:.0f}", (i - 0.18, r["eta %"]), textcoords="offset points",
                       xytext=(0, 3), ha="center", fontsize=6)
ax[1].set_xticks(x, [f"{r['beam deg']:.0f} deg" for r in d1])
ax[1].set(ylabel="array drain efficiency [%]", title="4 x 1: what the design table buys")
ax[1].legend(fontsize=7, loc="lower left")
done(t0, fig, "ex16_scan_design.png")
