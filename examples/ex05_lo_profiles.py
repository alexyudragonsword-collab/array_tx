"""ex05 — what LO does 64-QAM at 28 GHz need?  EVM / ACLR vs the shared LO.

The FR2 chain's EVM is set by the LO (cairn/LOG.md: an ideal PA with noise
on sits at -28 dB, the same as the Rapp PA with DPD).  Here the shared LO is
swapped for pll_simulator's own exported clock profiles (bundled, see
src/arraytx/data/clock_profiles/README.md), each read at 28 GHz as a PLL
behind an ideal multiplier, i.e. L(f) + 20 log10(28 GHz / f0).  Part 1
prints the rms phase error each profile injects (locked-LO approximation:
flat below the 400 kHz loop bandwidth, as the DTC applies it) next to the
OTA EVM / ACLR1 at the 30 deg beam without and with the array DPD.  Part 2
checks the small-angle rule EVM ~ 20 log10(sigma_phi) against the chain.
"""
import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.lo import ClockProfileLO
from arraytx.report import table

SWEEP = ["adpll_100m_10g", "adpll_bb_100m_10g", "spll_100m_8g", "sspll_19p2m_4p8g",
         "cppll_frac_38p4m_6g", "ilcm_250m_12g",
         "bench_markulic16_sspll_40m_10p24g", "bench_dartizio23_adpllbb_500m_9p2515g"]
# eight categorical slots, fixed order (dataviz palette)
COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
EVM_LIMIT_DB = 20 * np.log10(0.08)      # 64-QAM 8 % (TS 38.101-2 Table 6.4.2.1-1)
THETA0 = 30.0


def rms_phase_of(lo_obj, loop_bw, f_hi):
    """rms phase [rad] a polar_tx lo_pn object injects between 100 Hz and
    f_hi, locked-LO flattened below the loop bandwidth."""
    f = np.geomspace(100.0, f_hi, 4000)
    s = lo_obj.leeson("lo").psd(np.maximum(f, loop_bw))
    trap = getattr(np, "trapezoid", None) or np.trapz
    return float(np.sqrt(trap(s, f)))


def floor_dbchz(lo_obj, f_hz):
    """L(f) [dBc/Hz] at one offset (double-sided S_phi / 2)."""
    return float(10 * np.log10(lo_obj.leeson("lo").psd(np.array([f_hz]))[0] / 2.0))


base = load_config("configs/fr2_4el_survey.yaml")
sim_ref = ArraySim(base)
t0 = banner("ex05  the shared LO: EVM / ACLR vs pll_simulator clock profiles (28 GHz)", sim_ref)
loop_bw = base.element.lo.loop_bw_hz
rows, curves = [], []

# reference: polar_tx's own FR2 preset LO (-100 dBc/Hz @ 1 MHz, floor -140)
ref_lo = sim_ref.elements[0].tx.phasemod.cfg.lo_pn
r0, r1 = sim_ref.run(THETA0, "none"), sim_ref.run(THETA0, "array")
bw2 = sim_ref.wf.bw / 2
rows.append({"LO": "polar_tx nr_dtc FR2 preset", "f0 GHz": 28.0, "+dB": 0.0,
             "rms mrad": 1e3 * rms_phase_of(ref_lo, loop_bw, bw2), "L@300M": floor_dbchz(ref_lo, 300e6),
             "EVM none": r0.beam.evm_db, "ACLR1 none": r0.beam.aclr1_db,
             "EVM DPD": r1.beam.evm_db, "ACLR1 DPD": r1.beam.aclr1_db})

for name in SWEEP:
    cfg = load_config("configs/fr2_4el_survey.yaml")
    cfg.element.lo.clock_profile = f"bundled:{name}"
    sim = ArraySim(cfg)
    lo = sim.elements[0].tx.phasemod.cfg.lo_pn
    assert isinstance(lo, ClockProfileLO)
    r0, r1 = sim.run(THETA0, "none"), sim.run(THETA0, "array")
    rows.append({"LO": name, "f0 GHz": lo.f0_hz / 1e9, "+dB": 10 * np.log10(lo.scale),
                 "rms mrad": 1e3 * rms_phase_of(lo, loop_bw, bw2), "L@300M": floor_dbchz(lo, 300e6),
                 "EVM none": r0.beam.evm_db, "ACLR1 none": r0.beam.aclr1_db,
                 "EVM DPD": r1.beam.evm_db, "ACLR1 DPD": r1.beam.aclr1_db})
    f = np.geomspace(1e3, sim.fs / 2, 400)
    curves.append((name, f, 10 * np.log10(lo.psd(f) / 2.0)))     # L(f) at 28 GHz, dBc/Hz

rows.sort(key=lambda r: r["rms mrad"])
print("\nPart 1 — OTA at the 30 deg beam vs LO (profiles scaled to 28 GHz; rms phase IN BAND, 100 Hz..BW/2, flat below the loop BW;")
print("         L@300M = L(f) in dBc/Hz one adjacent channel out, the ACLR-relevant number):")
print(table(rows))
print(f"\n64-QAM EVM limit 8 % = {EVM_LIMIT_DB:.1f} dB.  Meets it with >= 3 dB margin (no DPD): "
      + ", ".join(r["LO"] for r in rows if r["EVM none"] <= EVM_LIMIT_DB - 3) )
print("fails it (no DPD): " + (", ".join(r["LO"] for r in rows if r["EVM none"] > EVM_LIMIT_DB) or "none"))

print("\nPart 2 — small-angle rule: EVM_dB ~ 20 log10(sigma_phi) + c")
pred = np.array([20 * np.log10(r["rms mrad"] * 1e-3) for r in rows])
fits = {}
for col in ("EVM none", "EVM DPD"):
    meas = np.array([r[col] for r in rows])
    s, c = np.polyfit(pred, meas, 1)
    fits[col] = (s, c)
    print(f"  {col:8s}: EVM = {s:.2f} x 20log10(sigma) {c:+.2f} dB over {len(rows)} LOs; residual rms "
          f"{np.std(meas - (s * pred + c)):.2f} dB")
print("  (a slope of 1 is a purely LO-limited EVM; below 1 the PA / datapath floor at the clean end takes over --")
print("   the DPD column, with most of the PA share removed, is the one that tracks the LO)")
slope, icpt = fits["EVM DPD"]

fig, ax = plt.subplots(1, 2, figsize=(11.5, 4))
for (name, f, l_db), c in zip(curves, COLORS):
    ax[0].semilogx(f, l_db, color=c, label=name, lw=1.3)
f = np.geomspace(1e3, sim_ref.fs / 2, 400)
ax[0].semilogx(f, 10 * np.log10(ref_lo.leeson("lo").psd(f) / 2.0), color="#8a8a85", ls="--", label="polar_tx FR2 preset")
ax[0].axvline(loop_bw, color="#8a8a85", lw=0.8, ls=":")
ax[0].set(xlabel="offset from 28 GHz carrier [Hz]", ylabel="L(f) [dBc/Hz]", title="clock profiles read at 28 GHz")
ax[0].legend(fontsize=7, ncol=2)
for i, r in enumerate(rows):
    c = "#8a8a85" if r["LO"].startswith("polar_tx") else COLORS[SWEEP.index(r["LO"])]
    ax[1].plot(r["rms mrad"], r["EVM none"], "o", ms=8, color=c)
    ax[1].plot(r["rms mrad"], r["EVM DPD"], "o", ms=8, mfc="none", color=c)
    ax[1].annotate(r["LO"].replace("bench_", "").split("_")[0], (r["rms mrad"], r["EVM none"]),
                   textcoords="offset points", xytext=(5, 4), fontsize=7, color="#555")
xs = np.geomspace(min(r["rms mrad"] for r in rows) * 0.8, max(r["rms mrad"] for r in rows) * 1.3, 50)
ax[1].plot(xs, slope * 20 * np.log10(xs * 1e-3) + icpt, color="#8a8a85", lw=0.8, ls="--", label=f"fit to DPD column, slope {slope:.2f}")
ax[1].axhline(EVM_LIMIT_DB, color="#e34948", lw=1.0, ls=":", label="64-QAM 8 % limit")
ax[1].set_xscale("log")
ax[1].set(xlabel="in-band rms LO phase error at 28 GHz, 100 Hz..BW/2 [mrad]", ylabel="OTA EVM at the beam [dB]  (lower is better)",
          title="EVM vs LO: filled = no DPD, open = array DPD" + (" (smoke)" if smoke() else ""))
ax[1].legend(fontsize=8)
done(t0, fig, "ex05_lo_profiles.png")
