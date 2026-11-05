"""ex17 — how much does the scan design table (ex16) depend on its assumptions?

The design table rests on numbers that are source: assumed:

  coupling   the survey's adjacent coupling, -16 dB (abstract-level citation);
  kappa      how much of Gamma reaches the PA's knee and AM-PM (1 = the ideal
             voltage-source reading of cairn/load-pull-proposal.md);
  targets    ACLR1 <= -45 dBc and EVM <= -25 dB (design choices).

Each case redoes the ex16 sweep (4 x 1 full burst, per-element DPD retrained
at each angle, CFR x output backoff) with ONE assumption moved, and compares
the per-angle choice (CFR, backoff) and its efficiency with the baseline.
The targets need no new runs: the baseline sweep is re-picked under each.
The answer this example gives: which assumption is worth measuring first --
the one that changes the backoff schedule, not just the numbers.
8 x 8 is not covered (each case would cost ~30 min there).
"""
import numpy as np

from _common import (ACLR_TARGET_DBC, EVM_TARGET_DB, TABLE_MARGIN_DB, banner, design_sweep, design_table, done, plt,
                     smoke)
from arraytx import ArraySim, load_config
from arraytx.report import table

CFG = "configs/fr2_4el_survey.yaml"
ANGLES = [0.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0]
BACKOFFS = [0.0, 2.0] if smoke() else [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]   # 5 dB: stronger coupling may need more than ex16 swept
CFRS = [8.5] if smoke() else [8.5, 7.5, 6.5]
MARGIN = TABLE_MARGIN_DB["4 x 1"]


def coupling(db):
    def tweak(cfg):
        cfg.coupling.scale_db = db                       # survey shape, adjacent -16 dB + db
    return tweak


def kappa(k):
    def tweak(cfg):
        cfg.element.pa.load_pull.kappa_amam = k
        cfg.element.pa.load_pull.kappa_ampm = k
    return tweak


CASES = {"baseline (c1 -16 dB, kappa 1)": None,
         "coupling -13 dB": coupling(3.0),
         "coupling -20 dB": coupling(-4.0),
         "kappa 0.5": kappa(0.5)}
if smoke():
    CASES = {k: v for k, v in CASES.items() if k.startswith(("baseline", "coupling -13"))}

t0 = banner("ex17  design-table sensitivity: coupling, kappa, targets", ArraySim(load_config(CFG)))
print(f"  baseline targets: ACLR1 <= {ACLR_TARGET_DBC} dBc (+{MARGIN} dB table margin), EVM <= {EVM_TARGET_DB} dB; all assumed")

designs, rows_by = {}, {}
for name, tweak in CASES.items():
    print(f"\n  case: {name}")
    rows = design_sweep(CFG, ANGLES, BACKOFFS, CFRS, label="4 x 1", tweak=tweak)
    rows_by[name] = rows
    designs[name], _ = design_table(rows, ANGLES, "4 x 1", MARGIN)

base_name = next(iter(CASES))
base = {d["beam deg"]: d for d in designs[base_name]}


def summary(name, d):
    by = {x["beam deg"]: x for x in d}
    changed = [th for th in ANGLES if (by[th]["CFR dB"], by[th]["backoff dB"]) != (base[th]["CFR dB"], base[th]["backoff dB"])]
    gains = [x["adaptive gain pts"] for x in d if np.isfinite(x["adaptive gain pts"])]
    return {"case": name, "schedule (backoff dB @ " + "/".join(f"{a:.0f}" for a in ANGLES) + ")": " / ".join(
                "-" if not np.isfinite(by[th]["backoff dB"]) else f"{by[th]['backoff dB']:.0f}" for th in ANGLES),
            "CFR @ max angle": by[max(ANGLES)]["CFR dB"],
            "eta @ 0 %": by[0.0]["eta %"], f"eta @ {max(ANGLES):.0f} %": by[max(ANGLES)]["eta %"],
            "angles changed": len(changed), "max adaptive gain pts": max(gains) if gains else float("nan")}


print("\nPart 1 — one physical assumption moved at a time (4 x 1):")
s1 = [summary(n, d) for n, d in designs.items()]
print(table(s1))

print("\nPart 2 — the targets moved, same baseline sweep (no new runs):")
s2 = []
for label, at, et in (("ACLR -43 dBc", -43.0, EVM_TARGET_DB), ("ACLR -45 dBc (baseline)", ACLR_TARGET_DBC, EVM_TARGET_DB),
                      ("ACLR -47 dBc", -47.0, EVM_TARGET_DB), ("EVM -23 dB", ACLR_TARGET_DBC, -23.0)):
    d, _ = design_table(rows_by[base_name], ANGLES, "4 x 1", MARGIN, aclr_target=at, evm_target=et)
    s2.append(summary(label, d))
print(table(s2))

for name, d in designs.items():
    print(f"  {name:32}: " + "  ".join(f"{x['beam deg']:.0f}deg CFR {x['CFR dB']} BO {x['backoff dB']} -> {x['eta %']:.1f}%" for x in d))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
for (name, d), mk in zip(designs.items(), ("o-", "s--", "^--", "d:")):
    ax[0].step([x["beam deg"] for x in d], [x["backoff dB"] for x in d], where="mid", label=name)
    ax[1].plot([x["beam deg"] for x in d], [x["eta %"] for x in d], mk, ms=5, label=name)
ax[0].set(xlabel="beam [deg]", ylabel="output backoff picked [dB]", title="4 x 1: the backoff schedule per assumption" + (" (smoke)" if smoke() else ""))
ax[1].set(xlabel="beam [deg]", ylabel="array drain efficiency at the pick [%]", title="what each assumption does to efficiency")
ax[0].legend(fontsize=7)
ax[1].legend(fontsize=7)
done(t0, fig, "ex17_design_sensitivity.png")
