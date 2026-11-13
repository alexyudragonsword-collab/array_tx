"""ex22 — are the dtc_openloop spur / IM numbers converged in the sampling grid?

ROADMAP B2 used to say the event engine cannot run at FR2, so the FR2 numbers
come from a "linearised" engine and no spur / IM conclusion may be drawn from
them.  The FR2 chain has no ADPLL at all: polar_tx nr_dtc(bw > 100 MHz) is
wifi_dtc, an open-loop DTC (dtc_openloop) that applies its deterministic
non-idealities sample by sample.  What it cannot see is anything above
fs / 2: a nonlinear product there folds back.  So the question is whether the
numbers move when the grid gets finer.

Grid: sim.oversampling 4 (today, fs = 1.966 GS/s), 8 and 16 (7.864 GS/s).
Literal x1 / x2 cannot be run: ACLR1 needs fs >= 3 BW and os 1 / 2 give
1.23 / 2.46 BW.  The DTC and the DPA update on the simulation grid, so os ->
infinity is the continuous-time limit of the same model; the difference
os 4 vs os 16 is what the os-4 grid folds.

Pre-registered tolerance (written before the full run): a number is
converged at os 4 if it is within 0.3 dB of its os-16 value (ACLR) or
0.1 dB (EVM).

  Part A  ex04's case: beam 30 deg, survey and analytic coupling, no DPD /
          per-element / array DPD, noise OFF (the spur / IM question is a
          deterministic one): beam ACLR1, ACLR2, EVM, sidelobe ACLR1, worst
          lit direction (pattern >= -15 dB) ACLR1.
          Also at os 16: the DTC and DPA clocks held at 1.966 GHz (ZOH) --
          different physics (a real update clock's images and droop), shown
          for scale, not part of the convergence test (its EVM reads the ZOH's
          half-update delay as error, so read its ACLR columns only).
  Part B  ex07's case: the three loudest clock-profile spur tables, spurs off
          and on (noise on -- the spurs are gated with it), no DPD and array
          DPD: the change in EVM and ACLR1 the spurs make.
  Part C  noise ON at the beam, no DPD: the random floor.  The DTC jitter is
          drawn per simulation sample, so its in-band density falls as the
          grid gets finer -- a property of the noise model, shown separately.
  Part D  the DPD cases at os 4 / 8 / 16 / 32 (survey; beam and sidelobe):
          whether the DPD numbers settle at all.
"""
from dataclasses import replace

import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.lo import ClockProfileLO, list_bundled
from arraytx.metrics import aclr1_vs_direction, power_vs_direction_db
from arraytx.report import table

THETA0 = 30.0
OS = [4, 8] if smoke() else [4, 8, 16]
REF = OS[-1]
N_SYMBOLS = 2 if smoke() else 8
SCHEMES = ("none", "per_element") if smoke() else ("none", "per_element", "array")
COUPLINGS = ("survey",) if smoke() else ("survey", "analytic")
THETAS = np.arange(-90.0, 90.0 + 0.5, 6.0 if smoke() else 3.0)
F_CLOCK = 1966.08e6                 # today's grid = the DTC / DPA update clock of variant (ii)
TOL_ACLR, TOL_EVM = 0.3, 0.1


def sim_for(cfg_path, os_, *, noise, held=False, profile=None, spurs=False):
    cfg = load_config(cfg_path)
    cfg.sim.oversampling = os_
    cfg.sim.noise = noise
    if profile is not None:
        cfg.element.lo.clock_profile = f"bundled:{profile}"
        cfg.element.lo.spurs = spurs
    sim = ArraySim(cfg, n_symbols=N_SYMBOLS)
    if held and sim.fs != F_CLOCK:
        # variant (ii): the DTC and the DPA update at today's clock, ZOH between updates
        for el in sim.elements:
            el.tx.cfg = replace(el.tx.cfg, f_dpa=F_CLOCK)
            el.tx.phasemod.cfg = replace(el.tx.phasemod.cfg, f_update=F_CLOCK)
    return sim


def beam_numbers(sim, scheme):
    r = sim.run(THETA0, scheme, conducted_diagnostics=False)
    e = sim.far_field_many(r.rs, THETAS)
    a = aclr1_vs_direction(e, sim.wf, THETAS)
    p = power_vs_direction_db(e)
    lit = (p - p.max()) >= -15.0
    del e
    return {"ACLR1": r.beam.aclr1_db, "ACLR2": r.beam.aclr2_db, "EVM": r.beam.evm_db,
            "SL ACLR1": r.sidelobe.aclr1_db, "worst lit ACLR1": float(np.max(a[lit]))}


s0 = sim_for("configs/fr2_4el_survey.yaml", 4, noise=False)
t0 = banner("ex22  dtc_openloop: are the spur / IM numbers converged in the sampling grid? (ROADMAP B2)", s0)
print(f"  oversampling {OS} -> fs {', '.join(f'{4096 * 120e3 * k / 1e9:.3f}' for k in OS)} GS/s; "
      f"{N_SYMBOLS} symbols; tolerance |os - os{REF}| <= {TOL_ACLR} dB (ACLR), {TOL_EVM} dB (EVM)")

# ------------------------------------------------------------------ Part A
print(f"\nPart A — ex04's case, beam {THETA0:.0f} deg, noise off (deterministic): metric per oversampling")
rowsA, worstA = [], {}
for cpl in COUPLINGS:
    path = f"configs/fr2_4el_{cpl}.yaml"
    for sch in SCHEMES:
        got = {k: beam_numbers(sim_for(path, k, noise=False), sch) for k in OS}
        if not smoke():
            got["16 held"] = beam_numbers(sim_for(path, 16, noise=False, held=True), sch)
        for m in got[REF]:
            row = {"coupling": cpl, "scheme": sch, "metric": m}
            row.update({f"os {k}": got[k][m] for k in got})
            for k in OS[:-1]:
                row[f"os{k}-os{REF}"] = got[k][m] - got[REF][m]
            tol = TOL_EVM if m == "EVM" else TOL_ACLR
            row["converged at os 4"] = abs(row[f"os4-os{REF}"]) <= tol
            rowsA.append(row)
        print(f"  {cpl:8s} {sch:12s}: " + "  ".join(
            f"{m} {got[4][m]:.2f}->{got[REF][m]:.2f}" for m in got[REF]), flush=True)
print(table(rowsA))
for m in ("ACLR1", "ACLR2", "EVM", "SL ACLR1", "worst lit ACLR1"):
    d = [r[f"os4-os{REF}"] for r in rowsA if r["metric"] == m]
    d8 = [r.get(f"os8-os{REF}", np.nan) for r in rowsA if r["metric"] == m]
    worstA[m] = (max(d, key=abs), max(d8, key=abs) if len(OS) > 2 else float("nan"))
    print(f"  {m:16s}: os4 - os{REF} {min(d):+.2f} .. {max(d):+.2f} dB"
          + (f"; os8 - os{REF} {min(d8):+.2f} .. {max(d8):+.2f} dB" if len(OS) > 2 else ""))

# ------------------------------------------------------------------ Part B
print(f"\nPart B — ex07's case: the loudest spur tables, change spurs-on minus spurs-off (noise on), beam {THETA0:.0f} deg")
names = [n for n in list_bundled() if ClockProfileLO(f"bundled:{n}").spurs]
names.sort(key=lambda n: -ClockProfileLO(f"bundled:{n}", fout_hz=28e9).spur_rms_rad())
names = names[:1] if smoke() else names[:3]
schB = ("none",) if smoke() else ("none", "array")
rowsB = []
for name in names:
    for sch in schB:
        rec = {"profile": name, "scheme": sch}
        for k in OS:
            off = sim_for("configs/fr2_4el_survey.yaml", k, noise=True, profile=name, spurs=False).run(
                THETA0, sch, conducted_diagnostics=False)
            on = sim_for("configs/fr2_4el_survey.yaml", k, noise=True, profile=name, spurs=True).run(
                THETA0, sch, conducted_diagnostics=False)
            rec[f"dEVM os{k}"] = on.beam.evm_db - off.beam.evm_db
            rec[f"dACLR1 os{k}"] = on.beam.aclr1_db - off.beam.aclr1_db
        rec["dEVM os4-os%d" % REF] = rec["dEVM os4"] - rec[f"dEVM os{REF}"]
        rec["dACLR1 os4-os%d" % REF] = rec["dACLR1 os4"] - rec[f"dACLR1 os{REF}"]
        rowsB.append(rec)
        devm = ", ".join("%+.2f" % rec["dEVM os%d" % k] for k in OS)
        daclr = ", ".join("%+.2f" % rec["dACLR1 os%d" % k] for k in OS)
        print(f"  {name:40s} {sch:5s}: dEVM {devm} dB, dACLR1 {daclr} dB", flush=True)
print(table(rowsB))

# ------------------------------------------------------------------ Part C
print(f"\nPart C — noise on, no DPD, survey, beam {THETA0:.0f} deg: the random floor against the grid")
rowsC = []
for k in OS:
    r = sim_for("configs/fr2_4el_survey.yaml", k, noise=True).run(THETA0, "none", conducted_diagnostics=False)
    q = sim_for("configs/fr2_4el_survey.yaml", k, noise=False).run(THETA0, "none", conducted_diagnostics=False)
    rowsC.append({"os": k, "fs GS/s": 4096 * 120e3 * k / 1e9, "EVM noise on": r.beam.evm_db, "EVM noise off": q.beam.evm_db,
                  "ACLR1 noise on": r.beam.aclr1_db, "ACLR1 noise off": q.beam.aclr1_db,
                  "ACLR2 noise on": r.beam.aclr2_db, "ACLR2 noise off": q.beam.aclr2_db})
print(table(rowsC))

# ------------------------------------------------------------------ Part D
rowsD = []
if not smoke():
    # Part A's DPD rows did not settle by os 16 (os 8 sat further from os 16 than os 4 did):
    # one more octave for them, beam and sidelobe only (no direction scan at 15.7 GS/s)
    print(f"\nPart D — the DPD cases one octave further (os 32, survey, beam {THETA0:.0f} deg, noise off)")
    for sch in ("per_element", "array"):
        rec = {"scheme": sch}
        for k in (4, 8, 16, 32):
            r = sim_for("configs/fr2_4el_survey.yaml", k, noise=False).run(THETA0, sch, conducted_diagnostics=False)
            rec.update({f"ACLR1 os{k}": r.beam.aclr1_db, f"ACLR2 os{k}": r.beam.aclr2_db, f"SL ACLR1 os{k}": r.sidelobe.aclr1_db})
        rowsD.append(rec)
        print("  " + sch + ": " + "  ".join(f"{m} " + " / ".join("%.2f" % rec[f"{m} os{k}"] for k in (4, 8, 16, 32))
                                         for m in ("ACLR1", "ACLR2", "SL ACLR1")), flush=True)
    print(table(rowsD))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
for m, mk in (("ACLR1", "o-"), ("ACLR2", "s--"), ("SL ACLR1", "^:"), ("worst lit ACLR1", "v-.")):
    for cpl in COUPLINGS:
        for sch, col in zip(SCHEMES, ("#8a8a85", "#2a78d6", "#d6652a")):
            r = next(x for x in rowsA if x["coupling"] == cpl and x["scheme"] == sch and x["metric"] == m)
            ax[0].plot(OS, [r[f"os {k}"] - r[f"os {REF}"] for k in OS], mk, color=col, alpha=0.75,
                       label=f"{m}, {sch}" if cpl == COUPLINGS[0] else None)
ax[0].axhspan(-TOL_ACLR, TOL_ACLR, color="#eef4fb", zorder=0)
ax[0].set_xscale("log", base=2)
ax[0].set_xticks(OS, [str(k) for k in OS])
ax[0].set(xlabel="oversampling (fs = 491.52 MS/s x os)", ylabel=f"metric - its os-{REF} value [dB]",
          title="Part A: noise off, beam 30 deg (band = tolerance)" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=6, ncol=2)
ax[1].plot([r["os"] for r in rowsC], [r["ACLR1 noise on"] for r in rowsC], "o-", color="#2a78d6", label="ACLR1 noise on")
ax[1].plot([r["os"] for r in rowsC], [r["ACLR1 noise off"] for r in rowsC], "o--", color="#2a78d6", label="ACLR1 noise off")
ax[1].plot([r["os"] for r in rowsC], [r["ACLR2 noise on"] for r in rowsC], "s-", color="#d6652a", label="ACLR2 noise on")
ax[1].plot([r["os"] for r in rowsC], [r["ACLR2 noise off"] for r in rowsC], "s--", color="#d6652a", label="ACLR2 noise off")
ax[1].set_xscale("log", base=2)
ax[1].set_xticks(OS, [str(k) for k in OS])
ax[1].set(xlabel="oversampling", ylabel="beam ACLR [dBc]", title="Part C: no DPD, survey, noise on vs off")
ax[1].legend(fontsize=7)
done(t0, fig, "ex22_oversampling_convergence.png")
