"""ex22 — the grid around the element's 4x clock: are the FR2 numbers converged?

The first ex22 (2026-11-13, cairn/dtc-openloop-grid.md) refined the grid
with the DTC / DPA update clock tied to it: os 16 was a chip clocked 4x
faster, not the same chip read on a finer grid (reading T).  polar_tx#22
answered with polar_tx 0e7b7ac: the clock is the hardware's, 4 x the FFT
rate (1966.08 MHz at FR2), and a grid finer than it holds each update.
arraytx follows (arraytx.clock): the waveform (burst_on_grid), CFR and DPD
run at the clock; steering, true-time delay, the held chain output,
coupling, the far field and the metrics run on the grid.  This is reading P:
only the grid changes, os 4 / 8 / 16 / 32 = 1 / 2 / 4 / 8 grid samples per
update, fs 1.966 / 3.932 / 7.864 / 15.73 GS/s.

Pre-registered (written into this file before the full run): a reading
converges at os 4 if it is within TOL of the same reading at os 16, and
os 16 is itself converged if os 32 is within TOL of it.  ACLR and mask
margins 0.3 dB, EVM 0.1 dB.  Against the first ex22 three readings are
added, as polar_tx's ex22 has them: per-tone EVM (the hold's droop is a
linear in-band response, which per-tone equalisation removes and scalar
does not), and the stylized mask's out-of-band margin over the band the
clock's Nyquist holds ("mask", the span os 4 sees) and over the whole grid
("mask full", where the hold's images at multiples of the clock show --
unfiltered: no output filter is modelled, so this reading is not a TX's).

  Part A  ex04's case: beam 30 deg, survey and analytic coupling, no DPD /
          per-element / array DPD, noise off: beam ACLR1 / ACLR2 / EVM
          (scalar, per-tone) / mask (visible, full), sidelobe ACLR1, worst
          lit direction (pattern >= -15 dB) ACLR1; os 4 / 8 / 16 / 32.
  Part B  ex07's case: the three loudest clock-profile spur tables, spurs
          off and on (noise on -- the spurs are gated with it), no DPD and
          array DPD: the change in EVM and ACLR1 the spurs make; os 4 / 8 / 16.
  Part C  noise on, no DPD, survey: the random floor.  The DTC jitter is
          drawn per update (it times an edge) and the LO on the grid (the
          band above the clock's Nyquist drawn fresh, the rest carried over).
"""
import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.lo import ClockProfileLO, list_bundled
from arraytx.metrics import aclr1_vs_direction, ota_metrics, power_vs_direction_db
from arraytx.report import table

THETA0 = 30.0
OS = [4, 8] if smoke() else [4, 8, 16, 32]
REF, CHECK = (8, None) if smoke() else (16, 32)
OS_B = [4, 8] if smoke() else [4, 8, 16]
N_SYMBOLS = 2 if smoke() else 8
SCHEMES = ("none", "per_element") if smoke() else ("none", "per_element", "array")
COUPLINGS = ("survey",) if smoke() else ("survey", "analytic")
THETAS = np.arange(-90.0, 90.0 + 0.5, 6.0 if smoke() else 3.0)
# ------------------------------------------------- written before the run
TOL = {"ACLR1": 0.3, "ACLR2": 0.3, "EVM": 0.1, "EVM tone": 0.1, "mask": 0.3, "mask full": 0.3,
       "SL ACLR1": 0.3, "worst lit ACLR1": 0.3}
FFT_RATE = 4096 * 120e3


def sim_for(cfg_path, os_, *, noise, profile=None, spurs=False):
    cfg = load_config(cfg_path)
    cfg.sim.oversampling = os_
    cfg.sim.noise = noise
    if profile is not None:
        cfg.element.lo.clock_profile = f"bundled:{profile}"
        cfg.element.lo.spurs = spurs
    return ArraySim(cfg, n_symbols=N_SYMBOLS)


def worst_lit(sim, rs):
    """Worst ACLR1 over the lit directions, the far field synthesised a few
    directions at a time (61 directions of a 15.7 GS/s burst would be 1 GB).
    Lit: the power within the clock's Nyquist -- the hold's images radiate
    elsewhere and would light directions the signal does not (first full run:
    worst lit ACLR1 os 32 - os 16 up to +1.32 dB from that alone)."""
    a, p = [], []
    for chunk in np.array_split(THETAS, max(1, len(THETAS) // 8)):
        e = sim.far_field_many(rs, chunk)
        a.append(aclr1_vs_direction(e, sim.wf, chunk))
        p.append(power_vs_direction_db(e, sim.wf))
    a, p = np.concatenate(a), np.concatenate(p)
    return float(np.max(a[(p - p.max()) >= -15.0]))


def beam_numbers(sim, scheme):
    r = sim.run(THETA0, scheme, conducted_diagnostics=False)
    tone = ota_metrics(r.far["beam"][1], sim.wf, THETA0, "beam", equalize="per_tone", with_sem=False)
    # the out-of-band margin (polar_tx ex22's): the worst margin includes the in-band
    # reference, which pins it at 0 once the out-of-band part passes
    oob = r.beam.sem["oob_margin_db"]
    return {"ACLR1": r.beam.aclr1_db, "ACLR2": r.beam.aclr2_db, "EVM": r.beam.evm_db, "EVM tone": tone.evm_db,
            # at os 4 the grid IS the visible band: its whole-grid mask is the visible one
            "mask": oob, "mask full": r.beam.extra.get("sem_full", {}).get("oob_margin_db", oob),
            "SL ACLR1": r.sidelobe.aclr1_db, "worst lit ACLR1": worst_lit(sim, r.rs)}


s0 = sim_for("configs/fr2_4el_survey.yaml", 4, noise=False)
t0 = banner("ex22  the grid around the 4x element clock: are the FR2 numbers converged? (reading P, polar_tx#22)", s0)
print(f"  oversampling {OS} -> fs {', '.join(f'{FFT_RATE * k / 1e9:.3f}' for k in OS)} GS/s, "
      f"{', '.join(str(k // 4) for k in OS)} grid samples per update of the {FFT_RATE * 4 / 1e6:.2f} MHz clock; "
      f"{N_SYMBOLS} symbols")
print("  tolerance (pre-registered): " + ", ".join(f"{m} {t}" for m, t in TOL.items()) + " dB; "
      f"os 4 against os {REF}" + (f", os {REF} against os {CHECK}" if CHECK else ""))

# ------------------------------------------------------------------ Part A
print(f"\nPart A — ex04's case, beam {THETA0:.0f} deg, noise off: reading per grid")
rowsA = []
for cpl in COUPLINGS:
    path = f"configs/fr2_4el_{cpl}.yaml"
    for sch in SCHEMES:
        got = {}
        for k in OS:
            got[k] = beam_numbers(sim_for(path, k, noise=False), sch)
            print(f"  {cpl:8s} {sch:12s} os {k:2d}: " + "  ".join(f"{m} {v:.2f}" for m, v in got[k].items()), flush=True)
        for m in TOL:
            row = {"coupling": cpl, "scheme": sch, "metric": m}
            row.update({f"os {k}": got[k][m] for k in OS})
            row[f"os4-os{REF}"] = got[4][m] - got[REF][m]
            row["os 4 ok"] = abs(row[f"os4-os{REF}"]) <= TOL[m]
            if CHECK:
                row[f"os{CHECK}-os{REF}"] = got[CHECK][m] - got[REF][m]
                row[f"os {REF} ok"] = abs(row[f"os{CHECK}-os{REF}"]) <= TOL[m]
            rowsA.append(row)
print(table(rowsA))
print("\n  per metric over every case (difference to os %d):" % REF)
for m in TOL:
    rs_ = [r for r in rowsA if r["metric"] == m]
    d4 = [r[f"os4-os{REF}"] for r in rs_]
    line = f"    {m:16s}: os 4 {min(d4):+.2f} .. {max(d4):+.2f} dB, converged at {sum(r['os 4 ok'] for r in rs_)}/{len(rs_)}"
    if CHECK:
        dc = [r[f"os{CHECK}-os{REF}"] for r in rs_]
        line += f"; os {CHECK} {min(dc):+.2f} .. {max(dc):+.2f} dB, os {REF} converged at {sum(r[f'os {REF} ok'] for r in rs_)}/{len(rs_)}"
    print(line)

# ------------------------------------------------------------------ Part B
print(f"\nPart B — ex07's case: the loudest spur tables, change spurs-on minus spurs-off (noise on), beam {THETA0:.0f} deg")
names = [n for n in list_bundled() if ClockProfileLO(f"bundled:{n}").spurs]
names.sort(key=lambda n: -ClockProfileLO(f"bundled:{n}", fout_hz=28e9).spur_rms_rad())
names = names[:1] if smoke() else names[:3]
schB = ("none",) if smoke() else ("none", "array")
refB = OS_B[-1]
rowsB = []
for name in names:
    for sch in schB:
        rec = {"profile": name, "scheme": sch}
        for k in OS_B:
            off = sim_for("configs/fr2_4el_survey.yaml", k, noise=True, profile=name, spurs=False).run(
                THETA0, sch, conducted_diagnostics=False)
            on = sim_for("configs/fr2_4el_survey.yaml", k, noise=True, profile=name, spurs=True).run(
                THETA0, sch, conducted_diagnostics=False)
            rec[f"dEVM os{k}"] = on.beam.evm_db - off.beam.evm_db
            rec[f"dACLR1 os{k}"] = on.beam.aclr1_db - off.beam.aclr1_db
        rec[f"dEVM os4-os{refB}"] = rec["dEVM os4"] - rec[f"dEVM os{refB}"]
        rec[f"dACLR1 os4-os{refB}"] = rec["dACLR1 os4"] - rec[f"dACLR1 os{refB}"]
        rowsB.append(rec)
        print(f"  {name:40s} {sch:5s}: dEVM " + ", ".join("%+.2f" % rec[f"dEVM os{k}"] for k in OS_B)
              + " dB, dACLR1 " + ", ".join("%+.2f" % rec[f"dACLR1 os{k}"] for k in OS_B) + " dB", flush=True)
print(table(rowsB))

# ------------------------------------------------------------------ Part C
print(f"\nPart C — noise on, no DPD, survey, beam {THETA0:.0f} deg: the random floor against the grid")
rowsC = []
for k in OS:
    r = sim_for("configs/fr2_4el_survey.yaml", k, noise=True).run(THETA0, "none", conducted_diagnostics=False)
    q = sim_for("configs/fr2_4el_survey.yaml", k, noise=False).run(THETA0, "none", conducted_diagnostics=False)
    rowsC.append({"os": k, "fs GS/s": FFT_RATE * k / 1e9, "EVM noise on": r.beam.evm_db, "EVM noise off": q.beam.evm_db,
                  "ACLR1 noise on": r.beam.aclr1_db, "ACLR1 noise off": q.beam.aclr1_db,
                  "ACLR2 noise on": r.beam.aclr2_db, "ACLR2 noise off": q.beam.aclr2_db})
print(table(rowsC))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
for m, mk in (("ACLR1", "o-"), ("ACLR2", "s--"), ("EVM", "x:"), ("mask", "d-."), ("worst lit ACLR1", "v-.")):
    for cpl in COUPLINGS:
        for sch, col in zip(SCHEMES, ("#8a8a85", "#2a78d6", "#d6652a")):
            r = next(x for x in rowsA if x["coupling"] == cpl and x["scheme"] == sch and x["metric"] == m)
            ax[0].plot(OS, [r[f"os {k}"] - r[f"os {REF}"] for k in OS], mk, color=col, alpha=0.75,
                       label=f"{m}, {sch}" if cpl == COUPLINGS[0] else None)
ax[0].axhspan(-0.3, 0.3, color="#eef4fb", zorder=0)
ax[0].set_xscale("log", base=2)
ax[0].set_xticks(OS, [str(k) for k in OS])
ax[0].set(xlabel="oversampling (clock 4x; grid samples per update = os / 4)", ylabel=f"reading - its os-{REF} value [dB]",
          title="Part A: noise off, beam 30 deg (band = ACLR tolerance)" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=5, ncol=2)
for key, mk, col in (("ACLR1", "o", "#2a78d6"), ("ACLR2", "s", "#d6652a")):
    ax[1].plot([r["os"] for r in rowsC], [r[f"{key} noise on"] for r in rowsC], mk + "-", color=col, label=f"{key} noise on")
    ax[1].plot([r["os"] for r in rowsC], [r[f"{key} noise off"] for r in rowsC], mk + "--", color=col, label=f"{key} noise off")
ax[1].set_xscale("log", base=2)
ax[1].set_xticks(OS, [str(k) for k in OS])
ax[1].set(xlabel="oversampling", ylabel="beam ACLR [dBc]", title="Part C: no DPD, survey, noise on vs off")
ax[1].legend(fontsize=7)
done(t0, fig, "ex22_oversampling_convergence.png")
