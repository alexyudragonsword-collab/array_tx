"""ex06 — how many elements before the squint reaches the beam EVM?

Milestone 1 found (cairn/LOG.md, "refuted expectations") that for 4 elements
the band-edge squint at 60 deg is a POINTING effect only: the beam is so
wide that 0.7 deg of band-edge offset costs nothing at the beam.  The beam
narrows as 1/n while the squint angle does not depend on n, so somewhere the
squint has to become a beam-EVM effect -- and because it is a linear,
deterministic frequency response H(f) at the beam (beam.beam_response), it
is also exactly what a per-tone equaliser removes.  This example finds the
crossover for the FR2 400 MHz carrier.

Part 1: n in {4 .. 128}, 0 / 30 / 60 deg, phase-shifter vs true-time-delay
steering, no DPD, default (survey) coupling and element errors; OTA EVM at
the beam under the scalar equaliser (polar_tx's default convention) and the
per-tone one.  Next to each measured phase-minus-TTD penalty, the closed
form: the scalar-equaliser residual of H(f) over the active tones, added to
the TTD floor in power.  Part 2: the closed form alone, as a function of n,
with the n at which it crosses the TTD floor.
"""
import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.beam import beamwidth_3db_deg, squint_analytic_deg, squint_evm_closed_form_db, tone_frequencies_hz
from arraytx.geometry import LinearArray
from arraytx.metrics import ota_metrics
from arraytx.report import table

NS = [4, 16, 64] if smoke() else [4, 8, 16, 32, 64, 128]
ANGLES = [0.0, 30.0, 60.0]
CFG = "configs/fr2_4el_survey.yaml"
# categorical slots: angle -> colour (fixed), steering -> marker
COLORS = {0.0: "#2a78d6", 30.0: "#eb6834", 60.0: "#1baf7a"}


def sims_for(n):
    cfg_p = load_config(CFG)
    cfg_p.array.n_elements = n
    cfg_t = load_config(CFG)
    cfg_t.array.n_elements = n
    cfg_t.beam.steering = "ttd"
    return ArraySim(cfg_p), ArraySim(cfg_t)


def evm_per_tone(sim, r):
    th, e = r.far["beam"]
    return ota_metrics(e, sim.wf, th, "beam", offsets=(1,), equalize="per_tone", with_sem=False).evm_db


def power_add_db(floor_db, extra_db):
    return 10 * np.log10(10 ** (floor_db / 10) + 10 ** (extra_db / 10))


sim0, _ = sims_for(NS[0])
t0 = banner("ex06  element count vs squint: when the pointing error becomes a beam EVM", sim0)
f_tones = tone_frequencies_hz(sim0.wf)
rows, store = [], {}
for n in NS:
    sp, st = sims_for(n)
    for th in ANGLES:
        rp = sp.run(th, "none", conducted_diagnostics=False)
        rt = rp if th == 0.0 else st.run(th, "none", conducted_diagnostics=False)   # broadside: identical by construction
        pt_p, pt_t = evm_per_tone(sp, rp), (evm_per_tone(st, rt) if th != 0.0 else None)
        sq = squint_evm_closed_form_db(sp.geom, th, f_tones)
        bw3 = beamwidth_3db_deg(sp.geom, th)
        dth = abs(squint_analytic_deg(th, sp.f0, 200e6))
        pred = power_add_db(rt.beam.evm_db, sq) - rt.beam.evm_db if np.isfinite(sq) else 0.0
        store[(n, th)] = dict(evm_phase=rp.beam.evm_db, evm_ttd=rt.beam.evm_db, pt_phase=pt_p, pt_ttd=pt_t,
                              squint_db=sq, bw3=bw3, dth=dth, pred=pred,
                              aclr_phase=rp.beam.aclr1_db, aclr_ttd=rt.beam.aclr1_db, s=rp.seconds)
        rows.append({"n": n, "beam deg": th, "3dB bw deg": bw3, "squint@+200M deg": dth,
                     "squint/bw": dth / bw3, "EVM ttd": rt.beam.evm_db, "EVM phase": rp.beam.evm_db,
                     "penalty": rp.beam.evm_db - rt.beam.evm_db, "pred": pred, "closed-form sq": sq,
                     "EVM phase/tone": pt_p, "EVM ttd/tone": pt_t if pt_t is not None else pt_p,
                     "ACLR1 phase": rp.beam.aclr1_db, "s": rp.seconds})
        print(f"  n={n:4d} {th:4.0f} deg: EVM ttd {rt.beam.evm_db:7.2f}  phase {rp.beam.evm_db:7.2f}  "
              f"penalty {rp.beam.evm_db - rt.beam.evm_db:+5.2f} (pred {pred:+5.2f})  per-tone phase {pt_p:7.2f}  "
              f"[{rp.seconds:.1f} s]", flush=True)

print("\nPart 1 — OTA EVM at the beam (dB), scalar equaliser unless '/tone'; penalty = phase - ttd, pred = closed form:")
print(table(rows))

print("\nPart 2 — the squint alone (closed form, scalar equaliser) vs n, and where it crosses the TTD floor:")
crows = []
n_grid = [4, 8, 16, 32, 64, 128, 256]
for th in (30.0, 60.0):
    floor = store[(NS[-1], th)]["evm_ttd"]
    cross = None
    for n in n_grid:
        sq = squint_evm_closed_form_db(LinearArray(n, 0.5, sim0.f0), th, f_tones)
        crows.append({"beam deg": th, "n": n, "closed-form squint EVM dB": sq,
                      "3dB bw deg": beamwidth_3db_deg(LinearArray(n, 0.5, sim0.f0), th)})
        if cross is None and sq > floor:
            cross = n
    print(f"  {th:.0f} deg: TTD floor {floor:.2f} dB (n={NS[-1]}); the squint alone exceeds it from n = {cross}")
print(table(crows))

print("\nheadline:")
for th in (30.0, 60.0):
    a, b = store[(NS[0], th)], store[(NS[-1], th)]
    print(f"  {th:.0f} deg: n={NS[0]} penalty {a['pred']:+.2f} pred / {a['evm_phase'] - a['evm_ttd']:+.2f} measured; "
          f"n={NS[-1]} penalty {b['pred']:+.2f} pred / {b['evm_phase'] - b['evm_ttd']:+.2f} measured; "
          f"per-tone equalised the phase array reads {b['pt_phase']:.2f} vs TTD {b['pt_ttd']:.2f} dB")

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
for th in ANGLES:
    ep = [store[(n, th)]["evm_phase"] for n in NS]
    et = [store[(n, th)]["evm_ttd"] for n in NS]
    pp = [store[(n, th)]["pt_phase"] for n in NS]
    ax[0].plot(NS, ep, "o-", color=COLORS[th], label=f"{th:.0f} deg, phase shifters")
    if th != 0.0:
        ax[0].plot(NS, et, "s--", color=COLORS[th], mfc="none", label=f"{th:.0f} deg, true time delay")
        ax[0].plot(NS, pp, "x:", color=COLORS[th], label=f"{th:.0f} deg, phase, per-tone EQ")
        ax[1].plot(n_grid, [squint_evm_closed_form_db(LinearArray(n, 0.5, sim0.f0), th, f_tones) for n in n_grid],
                   "-", color=COLORS[th], label=f"{th:.0f} deg closed form")
        ax[1].axhline(store[(NS[-1], th)]["evm_ttd"], color=COLORS[th], ls="--", lw=1, label=f"{th:.0f} deg TTD floor (n={NS[-1]})")
for a in ax:
    a.set_xscale("log", base=2); a.set_xlabel("elements n (lambda/2 linear)")
ax[0].set(ylabel="OTA EVM at the beam [dB]  (lower is better)", title="simulated" + (" (smoke)" if smoke() else ""))
ax[1].set(ylabel="squint-only EVM, scalar EQ [dB]", title="closed form: scalar-EQ residual of H(f)")
ax[0].legend(fontsize=7, ncol=2); ax[1].legend(fontsize=7)
done(t0, fig, "ex06_element_count_squint.png")
