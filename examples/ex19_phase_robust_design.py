"""ex19 — a scan design table that survives not knowing the coupling phase.

ex18: the adjacent coupling phase (config: 180 deg, a sign convention, source
assumed) decides WHICH scan angle needs the backoff; at 0 deg the schedule is
reversed.  The backoff tracks one thing the array can measure per angle --
the mean |1 + Gamma| the steered drives put on the PAs (a coupler / the
calibration knows it) -- so a table can store backoff against |1 + Gamma|
instead of against the angle.

  Part 1  train: the nominal case (180 deg).  At every training angle, the
          least backoff that meets the targets (CFR 6.5 dB, the depth every
          ex16-ex18 pick used), and the |1 + Gamma| there.  The rule:
          backoff(m) = the training backoff of the nearest point at or above
          m (monotone, conservative); above the trained range, extrapolated
          by the fitted dB per unit m and rounded up.
  Part 2  test: the other phases, never trained on.  Four strategies per
          angle, each read from that phase's own sweep:
            angle table   the 180 deg schedule by angle (what ex16 stores);
            |1+G| rule    Part 1's rule applied to the measured m;
            worst case    the most backoff any phase needs at that angle;
            oracle        the least backoff that meets the targets there.
          Reported: whether each meets the targets, and its efficiency.
Targets as ex16 (assumed design choices).  4 x 1 full burst; 8 x 8 4 symbols.
"""
import math

import numpy as np

from _common import (TABLE_MARGIN_DB, banner, design_sweep, done, element_loads, meets, plt, smoke)
from arraytx import ArraySim, load_config
from arraytx.report import table

CFR = 6.5
BACKOFFS = [0.0, 1.0, 2.0, 3.0] if smoke() else [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
SETUPS = {
    "4 x 1": {"cfg": "configs/fr2_4el_survey.yaml", "n_symbols": None,
              "train": [0.0, 60.0] if smoke() else [float(a) for a in np.arange(0.0, 60.0 + 1e-9, 7.5)],
              "test": [0.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0],
              "phases": [0.0] if smoke() else [0.0, 90.0, 270.0]},
    "8 x 8": {"cfg": "configs/fr2_8x8_survey.yaml", "n_symbols": 4,
              "train": [0.0, 15.0, 30.0, 45.0, 60.0], "test": [0.0, 30.0, 60.0], "phases": [0.0, 90.0]},
}
if smoke():
    SETUPS = {"4 x 1": SETUPS["4 x 1"]}                       # CI time: the 8 x 8 answer comes from the full run
NOMINAL = 180.0


def phase(ph):
    def tweak(cfg):
        cfg.coupling.survey.c1_deg_at_f0 = ph
    return tweak


def mean_load(path, ph, theta, n_symbols):
    cfg = load_config(path)
    cfg.element.pa.load_pull.enabled = True
    phase(ph)(cfg)
    return float(element_loads(ArraySim(cfg, n_symbols=n_symbols), theta).mean())


def least_backoff(rows, theta, margin):
    """The least backoff at ``theta`` that meets the targets (NaN if none in the sweep)."""
    ok = sorted(x["backoff dB"] for x in rows if x["beam deg"] == theta and meets(x, margin))
    return ok[0] if ok else float("nan")


def make_rule(ms, bs):
    """backoff(m) from training pairs: monotone (cumulative max in m), the
    nearest trained point at or above m; above the range, the fitted dB per
    unit m, rounded up."""
    order = np.argsort(ms)
    m_sorted = np.asarray(ms)[order]
    b_mono = np.maximum.accumulate(np.asarray(bs)[order])
    slope = float(np.polyfit(m_sorted, b_mono, 1)[0]) if np.ptp(m_sorted) > 0 else 0.0

    def rule(m):
        i = int(np.searchsorted(m_sorted, m - 1e-9))
        if i < len(m_sorted):
            return float(b_mono[i]), False
        return float(b_mono[-1] + math.ceil(max(slope, 0.0) * (m - m_sorted[-1]) - 1e-9)), True
    return rule, m_sorted, b_mono, slope


def row_at(rows, theta, bo):
    return next((x for x in rows if x["beam deg"] == theta and x["backoff dB"] == bo), None)


s0 = ArraySim(load_config(SETUPS["4 x 1"]["cfg"]))
t0 = banner("ex19  a scan design table that survives an unknown coupling phase: backoff stored against |1 + Gamma|", s0)
print(f"  CFR {CFR} dB throughout; backoff swept {BACKOFFS[0]:.0f}-{BACKOFFS[-1]:.0f} dB; targets and table margins as ex16 (assumed)")

results, training = {}, {}
for lab, st in SETUPS.items():
    margin = TABLE_MARGIN_DB[lab]
    print(f"\n{lab} — Part 1: train on the nominal phase ({NOMINAL:.0f} deg):")
    rows = design_sweep(st["cfg"], st["train"], BACKOFFS, [CFR], n_symbols=st["n_symbols"], label=lab, tweak=phase(NOMINAL))
    ms = [mean_load(st["cfg"], NOMINAL, th, st["n_symbols"]) for th in st["train"]]
    bs = [least_backoff(rows, th, margin) for th in st["train"]]
    keep = [i for i, b in enumerate(bs) if np.isfinite(b)]
    rule, m_sorted, b_mono, slope = make_rule([ms[i] for i in keep], [bs[i] for i in keep])
    training[lab] = (ms, bs, m_sorted, b_mono)
    print(table([{"beam deg": th, "|1+G| mean": m, "least backoff dB": b} for th, m, b in zip(st["train"], ms, bs)]))
    print("  rule: monotone steps at |1+G| " + ", ".join(f"{m:.3f}->{b:.0f} dB" for m, b in zip(m_sorted, b_mono))
          + f"; above {m_sorted[-1]:.3f}: {slope:.2f} dB per unit, rounded up")
    nominal_table = {th: least_backoff(rows, th, margin) for th in st["test"]}

    print(f"\n{lab} — Part 2: test phases {', '.join(f'{p:.0f}' for p in st['phases'])} deg (never trained on):")
    sweeps = {NOMINAL: rows}
    for ph in st["phases"]:
        print(f"\n  phase {ph:.0f} deg:")
        sweeps[ph] = design_sweep(st["cfg"], st["test"], BACKOFFS, [CFR], n_symbols=st["n_symbols"], label=lab, tweak=phase(ph))
    def worst_of(th):
        need = [least_backoff(sweeps[p], th, margin) for p in [NOMINAL, *st["phases"]]]
        return float("nan") if any(not np.isfinite(b) for b in need) else max(need)
    worst = {th: worst_of(th) for th in st["test"]}
    out = []
    for ph in st["phases"]:
        for th in st["test"]:
            m = mean_load(st["cfg"], ph, th, st["n_symbols"])
            b_rule, extrap = rule(m)
            picks = {"angle table": nominal_table[th], "|1+G| rule": b_rule, "worst case": worst[th],
                     "oracle": least_backoff(sweeps[ph], th, margin)}
            rec = {"array": lab, "phase deg": ph, "beam deg": th, "|1+G|": m, "extrapolated": extrap}
            for name, b in picks.items():
                x = row_at(sweeps[ph], th, min(b, BACKOFFS[-1])) if np.isfinite(b) else None
                rec[f"{name} BO"] = b
                rec[f"{name} ok"] = bool(x is not None and b <= BACKOFFS[-1] and meets(x, margin))
                rec[f"{name} eta %"] = x["eta %"] if x is not None else float("nan")
            out.append(rec)
    results[lab] = out
    print(table([{k: v for k, v in r.items() if k != "array"} for r in out]))
    for name in ("angle table", "|1+G| rule", "worst case", "oracle"):
        okn = sum(r[f"{name} ok"] for r in out)
        etas = [r[f"{name} eta %"] for r in out if r[f"{name} ok"]]
        print(f"  {lab} {name:12}: meets the targets at {okn}/{len(out)} (phase, angle) points; "
              f"efficiency where it meets: worst {min(etas):.2f} %, mean {np.mean(etas):.2f} %" if etas else f"  {lab} {name:12}: meets nowhere")

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
for lab, mk in zip(training, ("o", "s")):
    ms, bs, m_sorted, b_mono = training[lab]
    ax[0].plot(ms, bs, mk, color="#2a78d6", ms=6, label=f"{lab} training ({NOMINAL:.0f} deg)")
    ax[0].step(m_sorted, b_mono, where="post", color="#2a78d6", lw=0.8)
    for r in results[lab]:
        ax[0].plot(r["|1+G|"], r["oracle BO"], mk, mfc="none", color="#d6652a", ms=7)
ax[0].plot([], [], "o", mfc="none", color="#d6652a", label="test phases: least backoff needed")
ax[0].set(xlabel="mean |1 + Gamma| at the angle", ylabel="least backoff meeting the targets [dB]",
          title="backoff follows |1 + Gamma|, whatever the phase" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7)
names = ("angle table", "|1+G| rule", "worst case", "oracle")
cols = ("#d6652a", "#2a78d6", "#8a8a85", "#5a9e3c")
allr = [r for lab in results for r in results[lab]]
x = np.arange(len(allr))
for i, (name, col) in enumerate(zip(names, cols)):
    ax[1].bar(x + (i - 1.5) * 0.2, [r[f"{name} eta %"] if r[f"{name} ok"] else 0.0 for r in allr], 0.2, color=col, label=name)
ax[1].set_xticks(x, [f"{r['array'][0]}:{r['phase deg']:.0f}/{r['beam deg']:.0f}" for r in allr], rotation=90, fontsize=6)
ax[1].set(ylabel="efficiency where the targets are met [%] (0 = missed)", title="test phases (array:phase/angle)")
ax[1].legend(fontsize=7, loc="lower right")
done(t0, fig, "ex19_phase_robust_design.png")
