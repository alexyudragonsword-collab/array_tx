"""ex07 — the clock profile's discrete spurs: what reference and fractional
spurs do to the beam, at 28 GHz.

ex05 read the clock profiles' L(f) curves only.  Nine of the 18 bundled
profiles also carry a spurs: table (reference spurs at f_ref and its
harmonics, fractional spurs at the fractional offset); from this version
the element applies them as sinusoidal LO phase modulation at the carrier
(lo.ClockProfileLO.spurs_at_carrier: a = 2 * 10^(dbc/20) * fout/f0, start
phase from the lo_spurs seed stream).  Part 1: for each of the nine, the
spur table scaled to 28 GHz, the rms phase it adds, and the OTA EVM / ACLR1
at the 30 deg beam with the spurs off and on, without and with the array
DPD.  Part 2: the small-angle estimate EVM_on = EVM_off (+) 20 log10(rms
spur phase) against the measured change -- a spur inside the subcarrier
spacing (a slow phase wobble) and one far outside it (ICI) both land there,
because neither equaliser tracks a phase that moves within a symbol.
"""
import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.lo import ClockProfileLO, list_bundled
from arraytx.report import table

THETA0 = 30.0
CFG = "configs/fr2_4el_survey.yaml"
SCHEMES = ("none",) if smoke() else ("none", "array")
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#8a8a85"]


def sim_for(name, spurs_on):
    cfg = load_config(CFG)
    cfg.element.lo.clock_profile = f"bundled:{name}"
    cfg.element.lo.spurs = bool(spurs_on)
    return ArraySim(cfg)


def power_add_db(a_db, b_db):
    return 10 * np.log10(10 ** (a_db / 10) + 10 ** (b_db / 10))


names = [n for n in list_bundled() if ClockProfileLO(f"bundled:{n}").spurs]
names.sort(key=lambda n: -ClockProfileLO(f"bundled:{n}", fout_hz=28e9).spur_rms_rad())    # loudest first
if smoke():
    names = names[:3]
t0 = banner("ex07  clock-profile spurs at 28 GHz: EVM / ACLR with the spur table off and on", sim_for(names[0], True))
rows, spur_rows, store = [], [], {}
for name in names:
    s_off, s_on = sim_for(name, False), sim_for(name, True)
    lo = s_on.elements[0].tx.phasemod.cfg.lo_pn
    tab = lo.spurs_at_carrier()
    worst = max(tab, key=lambda fa: fa[1])
    rms = lo.spur_rms_rad()
    rec = {"LO": name.replace("bench_", ""), "f0 GHz": lo.f0_hz / 1e9, "+dB": 10 * np.log10(lo.scale),
           "spurs": len(tab), "worst kHz": worst[0] / 1e3, "worst dBc@28G": 20 * np.log10(worst[1] / 2),
           "rms mrad": 1e3 * rms, "pred dB": 20 * np.log10(rms) if rms > 0 else -np.inf}
    for sch in SCHEMES:
        r_off, r_on = s_off.run(THETA0, sch), s_on.run(THETA0, sch)
        rec[f"EVM off {sch}"] = r_off.beam.evm_db
        rec[f"EVM on {sch}"] = r_on.beam.evm_db
        rec[f"ACLR1 off {sch}"] = r_off.beam.aclr1_db
        rec[f"ACLR1 on {sch}"] = r_on.beam.aclr1_db
        store[(name, sch)] = (r_off.beam.evm_db, r_on.beam.evm_db, power_add_db(r_off.beam.evm_db, rec["pred dB"]))
    rows.append(rec)
    for f, a in tab:
        spur_rows.append({"LO": name.replace("bench_", ""), "offset kHz": f / 1e3, "dBc@f0": 20 * np.log10(a / 2) - 10 * np.log10(lo.scale),
                          "dBc@28G": 20 * np.log10(a / 2), "peak mrad": 1e3 * a})
    print(f"  {name:42s} {len(tab)} spurs, rms {1e3 * rms:6.2f} mrad: EVM none {rec['EVM off none']:7.2f} -> {rec['EVM on none']:7.2f}"
          + (f", DPD {rec['EVM off array']:7.2f} -> {rec['EVM on array']:7.2f}" if "array" in SCHEMES else ""), flush=True)

print("\nPart 1 — spur tables scaled to 28 GHz (dBc = single-sideband level; peak = phase deviation):")
print(table(spur_rows))
print(f"\nOTA at the {THETA0:.0f} deg beam, survey coupling, 4 elements; 'pred' = 20 log10(rms spur phase):")
print(table(rows))

print("\nPart 2 — small-angle estimate EVM_on = EVM_off (+) pred vs measured, in dB of change:")
for sch in SCHEMES:
    errs = []
    for name in names:
        off, on, pred = store[(name, sch)]
        errs.append((on - off) - (pred - off))
        print(f"  {sch:5s} {name:42s} measured {on - off:+5.2f}  predicted {pred - off:+5.2f}  (error {errs[-1]:+5.2f})")
    print(f"  {sch}: rms error of the estimate over {len(names)} profiles {np.sqrt(np.mean(np.square(errs))):.2f} dB")
print("\nACLR1: the spurs sit at offsets far inside the 400 MHz channel, so what reaches the adjacent channel is the")
print("       band-edge sliver shifted by the spur offset, at the spur level -- see the ACLR1 off/on columns.")

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for i, name in enumerate(names):
    lo = ClockProfileLO(f"bundled:{name}", fout_hz=28e9)
    tab = lo.spurs_at_carrier()
    ax[0].plot([f / 1e3 for f, _ in tab], [20 * np.log10(a / 2) for _, a in tab], "o", color=COLORS[i % len(COLORS)],
               label=name.replace("bench_", ""), ms=6)
ax[0].set_xscale("log")
ax[0].set(xlabel="offset from the 28 GHz carrier [kHz]", ylabel="spur level at 28 GHz [dBc]", title="spur tables of the bundled profiles, scaled")
ax[0].axvline(120.0, color="#8a8a85", lw=0.8, ls=":")
ax[0].annotate("subcarrier spacing", (120.0, ax[0].get_ylim()[0] + 2), fontsize=7, color="#555", rotation=90)
ax[0].legend(fontsize=6)
x = np.arange(len(names))
for j, sch in enumerate(SCHEMES):
    off = [store[(n, sch)][0] for n in names]
    on = [store[(n, sch)][1] for n in names]
    pred = [store[(n, sch)][2] for n in names]
    ax[1].plot(x + 0.15 * j, off, "s", mfc="none", color=COLORS[j], label=f"{sch}: spurs off")
    ax[1].plot(x + 0.15 * j, on, "o", color=COLORS[j], label=f"{sch}: spurs on")
    ax[1].plot(x + 0.15 * j, pred, "_", ms=12, mew=1.5, color="#8a8a85", label="small-angle estimate" if j == 0 else None)
ax[1].set_xticks(x, [n.replace("bench_", "")[:14] for n in names], rotation=45, ha="right", fontsize=7)
ax[1].set(ylabel="OTA EVM at the beam [dB]  (lower is better)", title="EVM with the spur table off / on" + (" (smoke)" if smoke() else ""))
ax[1].legend(fontsize=7)
done(t0, fig, "ex07_lo_spurs.png")
