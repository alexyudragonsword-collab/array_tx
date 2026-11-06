"""ex21 — kappa and the coupling phase together (4 x 1).

Both are source: assumed.  ex17 moved kappa alone (0.5: 60 deg backs off
1 dB less, 30 deg 1 dB more) and ex18 the adjacent coupling phase alone
(0 deg reverses the schedule).  They could compound: kappa scales how much of
Gamma reaches the knee, the phase decides at which angle |1 + Gamma| is
large.  This example crosses them (kappa 1 / 0.5 x phase 180 / 90 / 0 deg),
redoes the design table for each, and asks whether ex19's |1 + Gamma| rule
-- trained at kappa 1, 180 deg only -- still meets the targets when kappa is
not what it was trained at (smaller kappa: the same |1 + Gamma| compresses
less, so the rule should only over-back-off).
4 x 1 full burst, per-element DPD retrained per angle, load pull on; CFR
7.5 / 6.5 dB (every ex16-ex19 pick was 6.5) x backoff 0-5 dB.  Targets as
ex16 (assumed design choices).
"""
import numpy as np

from _common import (TABLE_MARGIN_DB, banner, backoff_rule, design_sweep, design_table, done, element_loads,
                     least_backoff, meets, plt, smoke)
from arraytx import ArraySim, load_config
from arraytx.report import table

CFG = "configs/fr2_4el_survey.yaml"
ANGLES = [0.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0]
BACKOFFS = [0.0, 2.0] if smoke() else [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
CFRS = [6.5] if smoke() else [7.5, 6.5]
KAPPAS = [1.0, 0.5]
PHASES = [180.0, 0.0] if smoke() else [180.0, 90.0, 0.0]
MARGIN = TABLE_MARGIN_DB["4 x 1"]


def case(kappa, ph):
    def tweak(cfg):
        cfg.element.pa.load_pull.kappa_amam = kappa
        cfg.element.pa.load_pull.kappa_ampm = kappa
        cfg.coupling.survey.c1_deg_at_f0 = ph
    return tweak


def mean_load(kappa, ph, theta):
    cfg = load_config(CFG)
    cfg.element.pa.load_pull.enabled = True
    case(kappa, ph)(cfg)
    return float(element_loads(ArraySim(cfg), theta).mean())


t0 = banner("ex21  kappa x coupling phase (4 x 1): does the design table, and the |1 + Gamma| rule, survive both?", ArraySim(load_config(CFG)))

designs, sweeps = {}, {}
for k in KAPPAS:
    for ph in PHASES:
        name = f"kappa {k:g}, phase {ph:.0f} deg"
        print(f"\n  case: {name}")
        rows = design_sweep(CFG, ANGLES, BACKOFFS, CFRS, label="4 x 1", tweak=case(k, ph))
        sweeps[(k, ph)] = rows
        designs[(k, ph)], _ = design_table(rows, ANGLES, "4 x 1", MARGIN)

print("\nPart 1 — the design table per case (most efficient setting meeting the targets):")
s1 = []
for (k, ph), d in designs.items():
    by = {x["beam deg"]: x for x in d}
    s1.append({"kappa": k, "phase deg": ph,
               "backoff dB @ " + "/".join(f"{a:.0f}" for a in ANGLES): " / ".join(
                   "-" if not np.isfinite(by[a]["backoff dB"]) else f"{by[a]['backoff dB']:.0f}" for a in ANGLES),
               "CFR dB": " / ".join(f"{by[a]['CFR dB']:.1f}" for a in ANGLES),
               "eta min %": float(np.nanmin([x["eta %"] for x in d])), "eta mean %": float(np.nanmean([x["eta %"] for x in d]))})
print(table(s1))

print("\nPart 2 — ex19's |1 + Gamma| rule trained at kappa 1, 180 deg (these five angles, CFR 6.5 dB), applied to every case:")
train = [(mean_load(1.0, 180.0, a), least_backoff([x for x in sweeps[(1.0, 180.0)] if x["CFR dB"] == 6.5], a, MARGIN)) for a in ANGLES]
keep = [(m, b) for m, b in train if np.isfinite(b)]
TOLS = (0.0, 0.005)        # 0 = ex19's rule; 0.005 = 2.5 x the |1+G| repeatability across operating points (<= 0.002, b068902)
rules = {tol: backoff_rule([m for m, _ in keep], [b for _, b in keep], tol=tol) for tol in TOLS}
rule, m_sorted, b_mono, slope = rules[0.0]
print("  steps " + ", ".join(f"{m:.3f}->{b:.0f} dB" for m, b in zip(m_sorted, b_mono)) + f"; above: {slope:.2f} dB per unit, rounded up")
rows2, loads = [], {}
for (k, ph), rows in sweeps.items():
    r65 = [x for x in rows if x["CFR dB"] == 6.5]
    for a in ANGLES:
        m = mean_load(k, ph, a)
        loads[(k, ph, a)] = m
        need = least_backoff(r65, a, MARGIN)
        rec = {"kappa": k, "phase deg": ph, "beam deg": a, "|1+G|": m, "least BO": need}
        for tol in TOLS:
            b, ext = rules[tol][0](m)
            x = next((x for x in r65 if x["beam deg"] == a and x["backoff dB"] == min(b, BACKOFFS[-1])), None)
            rec[f"BO tol {tol:g}"] = b
            rec[f"ext tol {tol:g}"] = ext
            rec[f"meets tol {tol:g}"] = bool(x is not None and b <= BACKOFFS[-1] and meets(x, MARGIN))
            rec[f"eta % tol {tol:g}"] = x["eta %"] if x else float("nan")
        rows2.append(rec)
print(table(rows2))
for k in KAPPAS:
    rr = [r for r in rows2 if r["kappa"] == k]
    for tol in TOLS:
        over = [r[f"BO tol {tol:g}"] - r["least BO"] for r in rr if np.isfinite(r["least BO"])]
        etas = [r[f"eta % tol {tol:g}"] for r in rr if r[f"meets tol {tol:g}"]]
        print(f"  kappa {k:g}, tol {tol:g}: rule meets {sum(r[f'meets tol {tol:g}'] for r in rr)}/{len(rr)}; "
              f"more backoff than needed at {sum(o > 0 for o in over)}, less at {sum(o < 0 for o in over)} points"
              + (f"; mean efficiency where met {np.mean(etas):.2f} %" if etas else ""))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
cols = dict(zip([180.0, 90.0, 0.0], ("#2a78d6", "#5a9e3c", "#d6652a")))
for (k, ph), d in designs.items():
    ax[0].step([x["beam deg"] for x in d], [x["backoff dB"] + (0.04 if k == 0.5 else 0.0) for x in d], where="mid",
               color=cols[ph], ls="-" if k == 1.0 else "--", label=f"kappa {k:g}, {ph:.0f} deg")
ax[0].set(xlabel="beam [deg]", ylabel="backoff picked [dB] (kappa 0.5 drawn +0.04)",
          title="4 x 1 design table: kappa x coupling phase" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7)
for r in rows2:
    ax[1].plot(r["|1+G|"], r["least BO"], "o" if r["kappa"] == 1.0 else "s", mfc="none" if r["kappa"] == 0.5 else cols[r["phase deg"]],
               color=cols[r["phase deg"]], ms=6)
ax[1].step(m_sorted, b_mono, where="post", color="#8a8a85", lw=1.0, label="rule (kappa 1, 180 deg)")
ax[1].plot([], [], "o", color="#8a8a85", label="kappa 1: least backoff")
ax[1].plot([], [], "s", mfc="none", color="#8a8a85", label="kappa 0.5: least backoff")
ax[1].set(xlabel="mean |1 + Gamma|", ylabel="least backoff meeting the targets [dB]", title="the rule against both kappas")
ax[1].legend(fontsize=7)
done(t0, fig, "ex21_kappa_x_phase.png")
