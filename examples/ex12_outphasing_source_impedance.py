"""ex12 — outphasing with a finite branch source impedance (ROADMAP B3,
option A of cairn/outphasing-load-proposal.md).

The ideal Chireix combiner (polar_tx) is a vector sum: nothing in the signal
path depends on the load.  With each branch PA a voltage source behind rho
(relative to the branch load, source: assumed) and the Chireix
compensation +-jB at the branch node, the combined output becomes

    y = [y1 / (1 + j rho B) + y2 / (1 - j rho B)] / (S / 2)  x  F(Gamma)

-- an AM-AM distortion set by rho B, and the array's active reflection
Gamma entering only as the complex gain F (Thevenin).  The proposal's four
predictions, checked here:

  1. rho = 0 is polar_tx bit for bit (tests/test_outphasing_load.py);
  2. one element, no coupling: ACLR1 gets worse with rho; a per-element DPD
     recovers most of it (the outphasing DPD finally has something to fit);
  3. an array under load pull: the two DPDs within 0.1 dB of each other, and
     a DPD trained at 0 deg used at 60 deg loses < 0.1 dB -- the opposite of
     the polar DPA's 2.8 dB;
  4. the beam: Gamma moves with the scan, so does each element's complex
     gain; main-lobe power and sidelobe level shift by a fraction of a dB,
     of order rho |Gamma|.
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.dpd import predistort_drives
from arraytx.metrics import ota_metrics
from arraytx.report import table

CFG = "configs/fr2_4el_survey.yaml"
RHOS = [0.0, 0.05] if smoke() else [0.0, 0.02, 0.05, 0.1]
ANGLES = [0.0, 60.0] if smoke() else [0.0, 30.0, 60.0]


def sim_for(*, rho, n=4, load_pull=False, coupling=True):
    cfg = load_config(CFG)
    cfg.element.topology = "outphasing"
    cfg.element.outphasing.source_impedance_rel = rho
    cfg.array.n_elements = n
    cfg.element.pa.load_pull.enabled = load_pull
    if not coupling:
        cfg.coupling.scale_db = float("-inf")
    return ArraySim(cfg)


def beam_power_db(r, label):
    return 10 * np.log10(np.mean(np.abs(r.far[label][1]) ** 2))


def apply(sim, bank, theta):
    drives = predistort_drives(bank, sim.x, sim.geom, theta, sim.fs, sim.cfg.beam.steering)
    _, _, rs = sim.radiate(drives)
    return ota_metrics(sim.far_field(rs, theta), sim.wf, theta, "beam", offsets=(1,), with_sem=False)


s0 = sim_for(rho=0.05, load_pull=True)
t0 = banner("ex12  outphasing: branch source impedance x Chireix susceptance; the array load as a complex gain", s0)

# ------------------------------------------------------------------ 2
print("\nPart 1 — one element, no coupling: OTA ACLR1 / EVM vs rho (prediction 2):")
rows1 = []
for rho in RHOS:
    sim = sim_for(rho=rho, n=1, coupling=False)
    a, b = sim.run(0.0, "none", conducted_diagnostics=False), sim.run(0.0, "per_element", conducted_diagnostics=False)
    rows1.append({"rho": rho, "ACLR1 none": a.beam.aclr1_db, "ACLR1 DPD": b.beam.aclr1_db, "EVM none": a.beam.evm_db, "EVM DPD": b.beam.evm_db})
    print(f"  rho {rho:.2f}: ACLR1 {a.beam.aclr1_db:7.2f} -> {b.beam.aclr1_db:7.2f} dBc with DPD   EVM {a.beam.evm_db:6.2f} -> {b.beam.evm_db:6.2f} dB", flush=True)
print(table(rows1))

# ------------------------------------------------------------------ 3
rho3 = 0.05
print(f"\nPart 2 — 4 x 1 survey, rho {rho3}, load pull off vs on: the two DPDs at their training angle (prediction 3):")
s_off, s_on = sim_for(rho=rho3), sim_for(rho=rho3, load_pull=True)
rows2, banks0 = [], {}
for th in ANGLES:
    for sch in ("none", "per_element", "array"):
        a, b = s_off.run(th, sch, conducted_diagnostics=False), s_on.run(th, sch, conducted_diagnostics=False)
        if th == 0.0 and sch != "none":
            banks0[sch] = b.dpd
        lp = b.info["load_pull"]
        rows2.append({"beam deg": th, "scheme": SCHEME_LABELS[sch], "ACLR1 off": a.beam.aclr1_db, "ACLR1 on": b.beam.aclr1_db,
                      "beam P on-off dB": beam_power_db(b, "beam") - beam_power_db(a, "beam"),
                      "sidelobe P on-off dB": (beam_power_db(b, "sidelobe") - beam_power_db(a, "sidelobe")) if "sidelobe" in b.far else float("nan"),
                      "|G| max": max(lp["abs_gamma_max"])})
        print(f"  {th:3.0f} deg {SCHEME_LABELS[sch]:22}: ACLR1 off {a.beam.aclr1_db:7.2f}  on {b.beam.aclr1_db:7.2f}", flush=True)
print(table(rows2))
for th in ANGLES:
    pe = next(x for x in rows2 if x["beam deg"] == th and x["scheme"] == SCHEME_LABELS["per_element"])
    ar = next(x for x in rows2 if x["beam deg"] == th and x["scheme"] == SCHEME_LABELS["array"])
    print(f"  {th:.0f} deg: array - per-element ACLR1 = {ar['ACLR1 on'] - pe['ACLR1 on']:+.3f} dB with load pull "
          f"({ar['ACLR1 off'] - pe['ACLR1 off']:+.3f} without); load pull moves per-element ACLR1 by {pe['ACLR1 on'] - pe['ACLR1 off']:+.3f} dB")
print("\n  DPD trained at 0 deg used at 60 deg, load pull on (polar DPA: +2.87 / +2.51 dB in ex09):")
for sch, bank in banks0.items():
    moved = apply(s_on, bank, 60.0).aclr1_db
    ret = next(x for x in rows2 if x["beam deg"] == 60.0 and x["scheme"] == SCHEME_LABELS[sch])["ACLR1 on"]
    print(f"  {SCHEME_LABELS[sch]:22}: trained@0 {moved:7.2f}  retrained {ret:7.2f}  penalty {moved - ret:+.3f} dB")

# ------------------------------------------------------------------ 4
print("\nPart 3 — the beam under load pull vs rho (no DPD; prediction 4: of order rho |Gamma|):")
rows3 = []
for rho in [r for r in RHOS if r > 0]:
    a_sim, b_sim = sim_for(rho=rho), sim_for(rho=rho, load_pull=True)
    for th in ANGLES:
        a, b = a_sim.run(th, "none", conducted_diagnostics=False), b_sim.run(th, "none", conducted_diagnostics=False)
        g = max(b.info["load_pull"]["abs_gamma_max"])
        rows3.append({"rho": rho, "beam deg": th, "beam P on-off dB": beam_power_db(b, "beam") - beam_power_db(a, "beam"),
                      "sidelobe P on-off dB": beam_power_db(b, "sidelobe") - beam_power_db(a, "sidelobe"),
                      "ACLR1 on-off dB": b.beam.aclr1_db - a.beam.aclr1_db, "rho |G|max": rho * g})
print(table(rows3))

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
ax[0].plot([r["rho"] for r in rows1], [r["ACLR1 none"] for r in rows1], "o-", color=SCHEME_COLORS["none"], label=SCHEME_LABELS["none"])
ax[0].plot([r["rho"] for r in rows1], [r["ACLR1 DPD"] for r in rows1], "o-", color=SCHEME_COLORS["per_element"], label=SCHEME_LABELS["per_element"])
ax[0].set(xlabel="branch source impedance rho (relative)", ylabel="OTA ACLR1 [dBc]  (lower is better)",
          title="one outphasing element, Chireix 60 deg" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=8)
for rho, mk in zip([r for r in RHOS if r > 0], ("o", "s", "^")):
    pts = [r for r in rows3 if r["rho"] == rho]
    ax[1].plot([p["beam deg"] for p in pts], [p["ACLR1 on-off dB"] for p in pts], mk + "-", label=f"ACLR1, rho {rho}")
    ax[1].plot([p["beam deg"] for p in pts], [p["beam P on-off dB"] for p in pts], mk + ":", mfc="none", label=f"beam power, rho {rho}")
ax[1].axhline(0, color="#8a8a85", lw=0.8)
ax[1].set(xlabel="beam [deg]", ylabel="load pull on - off [dB]", title="4 x 1: the array load is a complex gain")
ax[1].legend(fontsize=7)
done(t0, fig, "ex12_outphasing_source_impedance.png")
