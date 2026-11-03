"""ex10 — load modulation on the 8 x 8 grid, and what it costs to buy the
60 deg ACLR back (ROADMAP A2 follow-up; cairn/load-pull-proposal.md).

ex09 ran the DPD comparison on 4 x 1 and found that load pull HELPS at
broadside (the 180 deg neighbour wave cancels swing) and HURTS at 60 deg
beyond what either DPD can recover (the DPA is pushed into its full-scale
clip).  Two questions are left:

Part A  prediction 2c -- on the grid the interior elements have twelve
        neighbours and the farthest |1 + Gamma| (1.30 at 60 deg): the three
        schemes at their training angle, load pull off vs on, and the DPD
        trained at 0 deg used at 60 deg (4 x 1 numbers in ex09 / LOG).
Part B  the design answer at 60 deg: output power backoff
        (``element.pa.backoff_db``: the pinned full scale sits that much
        above the undistorted peak) and CFR depth (``sim.cfr_papr_db``),
        each priced with polar_tx's average drain efficiency of the code
        stream (the DPA's own SCPA law on the MATCHED-load table: Gamma does
        not enter the efficiency; source: polar_tx default law, assumed).
        4 x 1 first (cheap, dense grid), then the three decisive points on
        8 x 8.

Everything is OTA at the beam; conducted numbers are not read.
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.dpd import predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

CFG_GRID = "configs/fr2_8x8_survey.yaml"
CFG_ROW = "configs/fr2_4el_survey.yaml"
ANGLES = [0.0, 30.0, 60.0]
N_SYMBOLS_GRID = 2 if smoke() else 4      # 8 x 8 with load pull: ~60 s per run at 8 symbols; 4 keeps the matrix under an hour


def sim_for(cfg_path, *, load_pull=True, errors=True, backoff_db=0.0, cfr_papr_db=None, n_symbols=None):
    cfg = load_config(cfg_path)
    cfg.element.pa.load_pull.enabled = load_pull
    cfg.element.errors.enabled = errors
    cfg.element.pa.backoff_db = backoff_db
    if cfr_papr_db is not None:
        cfg.sim.cfr_papr_db = cfr_papr_db
    return ArraySim(cfg, n_symbols=n_symbols)


def beam_metrics_at(sim, bank, theta):
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False)


def eta_pct(r):
    return 100.0 * r.info["efficiency"]["eta_avg_mean"]


grid_on = sim_for(CFG_GRID, n_symbols=N_SYMBOLS_GRID)
t0 = banner("ex10  8 x 8 under load modulation; buying the 60 deg ACLR back with backoff / CFR", grid_on)
print(f"  grid runs use {N_SYMBOLS_GRID} OFDM symbols ({grid_on.wf.n} samples per element)")

# ------------------------------------------------------------------ Part A
print("\nPart A — 8 x 8, three schemes at their training angle, load pull off vs on (OTA beam ACLR1 dBc / EVM dB):")
grid_off = sim_for(CFG_GRID, load_pull=False, n_symbols=N_SYMBOLS_GRID)
angles_a = [60.0] if smoke() else ANGLES
schemes_a = ("none", "per_element") if smoke() else ("none", "per_element", "array")
rowsA, bank0 = [], {}
for th in angles_a:
    for sch in schemes_a:
        a = grid_off.run(th, sch, conducted_diagnostics=False)
        b = grid_on.run(th, sch, conducted_diagnostics=False)
        if th == 0.0 and sch != "none":
            bank0[sch] = b.dpd
        lp = b.info["load_pull"]
        rowsA.append({"beam deg": th, "scheme": SCHEME_LABELS[sch], "ACLR1 off": a.beam.aclr1_db, "ACLR1 on": b.beam.aclr1_db,
                      "EVM off": a.beam.evm_db, "EVM on": b.beam.evm_db, "|1+G| max": max(lp["abs_1pg_mean"]), "eta on %": eta_pct(b), "s": b.seconds})
        print(f"  {th:3.0f} deg {SCHEME_LABELS[sch]:22}: off {a.beam.aclr1_db:7.2f}  on {b.beam.aclr1_db:7.2f} dBc   EVM {a.beam.evm_db:6.2f} / {b.beam.evm_db:6.2f}"
              f"   [{a.seconds:.0f} + {b.seconds:.0f} s]", flush=True)
print(table(rowsA))
for th in angles_a:
    pe = next((x for x in rowsA if x["beam deg"] == th and x["scheme"] == SCHEME_LABELS["per_element"]), None)
    ar = next((x for x in rowsA if x["beam deg"] == th and x["scheme"] == SCHEME_LABELS["array"]), None)
    if pe and ar:
        print(f"  {th:.0f} deg: array - per-element ACLR1 = {ar['ACLR1 on'] - pe['ACLR1 on']:+.2f} dB with load pull "
              f"({ar['ACLR1 off'] - pe['ACLR1 off']:+.2f} without)   (4 x 1 in ex09: +0.09 / +0.09 / +0.33 at 0 / 30 / 60)")

if bank0:
    print("\nPart A' — 8 x 8, DPD trained at 0 deg used at 60 deg (load pull on) vs retrained:")
    for sch, bank in bank0.items():
        moved = beam_metrics_at(grid_on, bank, 60.0)
        retrained = next(x for x in rowsA if x["beam deg"] == 60.0 and x["scheme"] == SCHEME_LABELS[sch])["ACLR1 on"]
        print(f"  {SCHEME_LABELS[sch]:22}: trained@0 used@60 {moved.aclr1_db:7.2f}  retrained {retrained:7.2f}  penalty {moved.aclr1_db - retrained:+.2f} dB"
              f"   (4 x 1: +2.87 per-element / +2.51 array)")

# ------------------------------------------------------------------ Part B
print("\nPart B — 60 deg, per-element DPD, load pull on: output backoff vs CFR depth, priced in drain efficiency (4 x 1, full burst):")
backoffs = [0.0, 3.0] if smoke() else [0.0, 1.0, 2.0, 3.0, 4.0, 6.0]
cfrs = [8.5] if smoke() else [8.5, 7.5, 6.5]
rowsB = []
ref_off = sim_for(CFG_ROW, load_pull=False).run(60.0, "per_element", conducted_diagnostics=False)
print(f"  reference, load pull OFF, no backoff: ACLR1 {ref_off.beam.aclr1_db:.2f} dBc  eta {eta_pct(ref_off):.1f} %")
for cfr in cfrs:
    for bo in backoffs:
        sim = sim_for(CFG_ROW, backoff_db=bo, cfr_papr_db=cfr)
        r = sim.run(60.0, "per_element", conducted_diagnostics=False)
        rowsB.append({"CFR PAPR dB": cfr, "backoff dB": bo, "ACLR1": r.beam.aclr1_db, "EVM": r.beam.evm_db, "eta %": eta_pct(r),
                      "|1+G| max": max(r.info["load_pull"]["abs_1pg_mean"]), "s": r.seconds})
        print(f"  CFR {cfr:.1f} dB  backoff {bo:.0f} dB: ACLR1 {r.beam.aclr1_db:7.2f}  EVM {r.beam.evm_db:6.2f}  eta {eta_pct(r):5.1f} %   [{r.seconds:.1f} s]", flush=True)
print(table(rowsB))
target = ref_off.beam.aclr1_db
for cfr in cfrs:
    pts = [x for x in rowsB if x["CFR PAPR dB"] == cfr]
    hit = next((x for x in pts if x["ACLR1"] <= target), None)
    base = pts[0]
    if hit:
        print(f"  CFR {cfr:.1f} dB: the first backoff that recovers the no-load-pull ACLR1 ({target:.2f}) is {hit['backoff dB']:.0f} dB, "
              f"eta {base['eta %']:.1f} -> {hit['eta %']:.1f} % ({hit['eta %'] - base['eta %']:+.1f} points)")
    else:
        print(f"  CFR {cfr:.1f} dB: no backoff up to {backoffs[-1]:.0f} dB reaches {target:.2f} dBc (best {min(x['ACLR1'] for x in pts):.2f})")

rowsC = []
if not smoke():
    print("\nPart B' — the same three points on 8 x 8 (60 deg, per-element DPD, load pull on):")
    for bo in (0.0, 2.0, 3.0):
        r = sim_for(CFG_GRID, backoff_db=bo, n_symbols=N_SYMBOLS_GRID).run(60.0, "per_element", conducted_diagnostics=False)
        rowsC.append({"backoff dB": bo, "ACLR1": r.beam.aclr1_db, "EVM": r.beam.evm_db, "eta %": eta_pct(r), "s": r.seconds})
        print(f"  8 x 8 backoff {bo:.0f} dB: ACLR1 {r.beam.aclr1_db:7.2f}  EVM {r.beam.evm_db:6.2f}  eta {eta_pct(r):5.1f} %   [{r.seconds:.0f} s]", flush=True)
    print(table(rowsC))

# ------------------------------------------------------------------- plot
fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
x = np.arange(len(angles_a))
for i, sch in enumerate(schemes_a):
    off = [next(r["ACLR1 off"] for r in rowsA if r["beam deg"] == th and r["scheme"] == SCHEME_LABELS[sch]) for th in angles_a]
    on = [next(r["ACLR1 on"] for r in rowsA if r["beam deg"] == th and r["scheme"] == SCHEME_LABELS[sch]) for th in angles_a]
    ax[0].plot(x + (i - 1) * 0.18, off, "s", mfc="none", ms=7, color=SCHEME_COLORS[sch])
    ax[0].plot(x + (i - 1) * 0.18, on, "o", ms=7, color=SCHEME_COLORS[sch], label=SCHEME_LABELS[sch])
ax[0].set_xticks(x, [f"{t:.0f} deg" for t in angles_a]); ax[0].set_xlim(-0.6, len(angles_a) - 0.4)
ax[0].set(ylabel="OTA ACLR1 at the beam [dBc]  (lower is better)", title="8 x 8: open = linear leakage, filled = load pull" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=8)
for cfr, col in zip(cfrs, ("#2a78d6", "#d6652a", "#5a9e3c")):
    pts = [x for x in rowsB if x["CFR PAPR dB"] == cfr]
    ax[1].plot([p["eta %"] for p in pts], [p["ACLR1"] for p in pts], "o-", color=col, label=f"4 x 1, CFR {cfr:.1f} dB")
    for p in pts:
        ax[1].annotate(f"{p['backoff dB']:.0f}", (p["eta %"], p["ACLR1"]), textcoords="offset points", xytext=(4, 3), fontsize=7)
if rowsC:
    ax[1].plot([p["eta %"] for p in rowsC], [p["ACLR1"] for p in rowsC], "s--", color="#444", label="8 x 8, CFR 8.5 dB")
ax[1].axhline(ref_off.beam.aclr1_db, color="#8a8a85", lw=0.8, ls=":", label="4 x 1, load pull off")
ax[1].set(xlabel="average drain efficiency [%]  (matched-load DPA law)", ylabel="OTA ACLR1 at 60 deg [dBc]",
          title="backoff (labels, dB) buys ACLR with efficiency")
ax[1].legend(fontsize=7)
done(t0, fig, "ex10_grid_load_pull_backoff.png")
