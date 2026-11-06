"""ex20 — per-element backoff from each element's own |1 + Gamma_k| (ROADMAP B9).

ex19 picks ONE backoff per scan angle from the array-mean |1 + Gamma| and
meets the targets at every untrained coupling phase, but on 8 x 8 it backs
off more than needed (1.3 efficiency points below the oracle), and the mean
hides the edge / interior spread.  ``element.pa.backoff_per_element_db``
lets every element sit at its own backoff; an element backed off more
really gives its power up (its radiated amplitude drops by b_k - min b).

Same training as ex19 (180 deg, uniform backoff, CFR 6.5 dB, the least
backoff meeting the targets per angle vs the mean |1 + Gamma| there; rule
tol 0).  At each test (phase, angle):

  uniform      ex19: b = rule(mean_k |1 + Gamma_k|) for every element;
  per element  b_k = rule(|1 + Gamma_k|) for element k (same rule);
  +1 dB        if per element misses, every b_k + 1 (reported as such).

Each is a real run (per-element DPD retrained there).  Reported: meets the
targets, array efficiency, and the beam power the backoff costs relative to
the uniform pick, 20 log10(sum_k 10^(-b_k/20) / (N 10^(-b_u/20))) -- power
given up by backing elements off is power the beam does not get.
Targets as ex16 (assumed design choices).  4 x 1 full burst; 8 x 8 4 symbols.
"""
import numpy as np

from _common import (TABLE_MARGIN_DB, backoff_rule, banner, design_sweep, done, element_loads, least_backoff, meets, plt,
                     smoke)
from arraytx import ArraySim, load_config
from arraytx.report import table

CFR = 6.5
BACKOFFS = [0.0, 1.0, 2.0, 3.0] if smoke() else [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
SETUPS = {
    "4 x 1": {"cfg": "configs/fr2_4el_survey.yaml", "n_symbols": None,
              "train": [0.0, 60.0] if smoke() else [float(a) for a in np.arange(0.0, 60.0 + 1e-9, 7.5)],
              "test": [0.0, 60.0] if smoke() else [0.0, 15.0, 30.0, 45.0, 60.0],
              "phases": [0.0] if smoke() else [180.0, 0.0, 90.0, 270.0]},
    "8 x 8": {"cfg": "configs/fr2_8x8_survey.yaml", "n_symbols": 4,
              "train": [0.0, 15.0, 30.0, 45.0, 60.0], "test": [0.0, 30.0, 60.0], "phases": [180.0, 0.0, 90.0]},
}
if smoke():
    SETUPS = {"4 x 1": SETUPS["4 x 1"]}                       # CI time: the 8 x 8 answer comes from the full run
NOMINAL = 180.0


def cfg_for(path, ph, per_element=None, uniform=None):
    cfg = load_config(path)
    cfg.element.pa.load_pull.enabled = True
    cfg.coupling.survey.c1_deg_at_f0 = ph
    cfg.sim.cfr_papr_db = CFR
    if per_element is not None:
        cfg.element.pa.backoff_per_element_db = [float(b) for b in per_element]
    if uniform is not None:
        cfg.element.pa.backoff_db = float(uniform)
    return cfg


def loads(path, ph, theta, n_symbols):
    """|1 + Gamma_k| per element, undistorted drives, the config's CFR, no backoff (as ex19)."""
    cfg = load_config(path)
    cfg.element.pa.load_pull.enabled = True
    cfg.coupling.survey.c1_deg_at_f0 = ph
    return element_loads(ArraySim(cfg, n_symbols=n_symbols), theta)


def score(cfg, theta, n_symbols, margin):
    r = ArraySim(cfg, n_symbols=n_symbols).run(theta, "per_element", conducted_diagnostics=False)
    x = {"ACLR1": r.beam.aclr1_db, "EVM": r.beam.evm_db, "eta %": 100 * r.info["efficiency"]["eta_array_loaded"]}
    return x, bool(meets(x, margin))


def beam_cost_db(bk, bu):
    bk = np.asarray(bk, dtype=float)
    return float(20 * np.log10(np.sum(10 ** (-bk / 20)) / (bk.size * 10 ** (-bu / 20))))


s0 = ArraySim(load_config(SETUPS["4 x 1"]["cfg"]))
t0 = banner("ex20  per-element backoff from |1 + Gamma_k| (ROADMAP B9): each element gives up only what it must", s0)

results, spread = {}, {}
for lab, st in SETUPS.items():
    margin, ns = TABLE_MARGIN_DB[lab], st["n_symbols"]
    print(f"\n{lab} — training at {NOMINAL:.0f} deg (uniform backoff, CFR {CFR} dB), as ex19:")
    rows = design_sweep(st["cfg"], st["train"], BACKOFFS, [CFR], n_symbols=ns, label=lab,
                        tweak=lambda c: setattr(c.coupling.survey, "c1_deg_at_f0", NOMINAL))
    ms = [float(loads(st["cfg"], NOMINAL, th, ns).mean()) for th in st["train"]]
    bs = [least_backoff(rows, th, margin) for th in st["train"]]
    keep = [i for i, b in enumerate(bs) if np.isfinite(b)]
    rule, m_sorted, b_mono, slope = backoff_rule([ms[i] for i in keep], [bs[i] for i in keep])
    print("  rule: " + ", ".join(f"{m:.3f}->{b:.0f} dB" for m, b in zip(m_sorted, b_mono)) + f"; above: {slope:.2f} dB per unit")

    out = []
    for ph in st["phases"]:
        for th in st["test"]:
            mk = loads(st["cfg"], ph, th, ns)
            spread[(lab, ph, th)] = mk
            bu, _ = rule(float(mk.mean()))
            bk = np.array([rule(float(m))[0] for m in mk])
            xu, oku = score(cfg_for(st["cfg"], ph, uniform=bu), th, ns, margin)
            xp, okp = score(cfg_for(st["cfg"], ph, per_element=bk), th, ns, margin)
            plus = 0
            if not okp:
                plus = 1
                xp, okp = score(cfg_for(st["cfg"], ph, per_element=bk + 1.0), th, ns, margin)
            rec = {"array": lab, "phase deg": ph, "beam deg": th, "|1+G| min/max": f"{mk.min():.2f}/{mk.max():.2f}",
                   "uniform BO": bu, "uniform ok": oku, "uniform eta %": xu["eta %"],
                   "per-elem BO min/max": f"{bk.min() + plus:.0f}/{bk.max() + plus:.0f}", "+1 needed": bool(plus),
                   "per-elem ok": okp, "per-elem eta %": xp["eta %"], "per-elem ACLR1": xp["ACLR1"], "per-elem EVM": xp["EVM"],
                   "beam power vs uniform dB": beam_cost_db(bk + plus, bu)}
            out.append(rec)
            print(f"  {lab} phase {ph:5.0f} deg, {th:4.1f} deg: uniform {bu:.0f} dB {'ok' if oku else 'MISS'} {xu['eta %']:.2f} %  |"
                  f"  per element {rec['per-elem BO min/max']} dB{' (+1)' if plus else ''} {'ok' if okp else 'MISS'} {xp['eta %']:.2f} %"
                  f"  beam {rec['beam power vs uniform dB']:+.2f} dB", flush=True)
    results[lab] = out
    print(table([{k: v for k, v in r.items() if k != "array"} for r in out]))
    for kind in ("uniform", "per-elem"):
        ok = [r for r in out if r[f"{kind} ok"]]
        print(f"  {lab} {kind:9}: meets {len(ok)}/{len(out)}; mean efficiency {np.mean([r[f'{kind} eta %'] for r in out]):.2f} %"
              + (f"; +1 dB needed at {sum(r['+1 needed'] for r in out)}" if kind == "per-elem" else ""))
    print(f"  {lab} beam power vs uniform: mean {np.mean([r['beam power vs uniform dB'] for r in out]):+.2f} dB, "
          f"range {min(r['beam power vs uniform dB'] for r in out):+.2f} .. {max(r['beam power vs uniform dB'] for r in out):+.2f} dB")

fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
allr = [r for lab in results for r in results[lab]]
x = np.arange(len(allr))
ax[0].bar(x - 0.2, [r["uniform eta %"] for r in allr], 0.4, color="#d6652a", label="uniform (ex19)")
ax[0].bar(x + 0.2, [r["per-elem eta %"] for r in allr], 0.4, color="#2a78d6", label="per element")
for i, r in enumerate(allr):
    for dx, key in ((-0.2, "uniform ok"), (0.2, "per-elem ok")):
        if not r[key]:
            ax[0].annotate("x", (i + dx, 1.0), ha="center", fontsize=7, color="k")
ax[0].set_xticks(x, [f"{r['array'][0]}:{r['phase deg']:.0f}/{r['beam deg']:.0f}" for r in allr], rotation=90, fontsize=6)
ax[0].set(ylabel="array efficiency [%] (x = misses targets)", title="uniform vs per-element backoff" + (" (smoke)" if smoke() else ""))
ax[0].legend(fontsize=7, loc="lower right")
ax[1].bar(x, [r["beam power vs uniform dB"] for r in allr], 0.6, color="#5a9e3c")
ax[1].axhline(0.0, color="#8a8a85", lw=0.8)
ax[1].set_xticks(x, [f"{r['array'][0]}:{r['phase deg']:.0f}/{r['beam deg']:.0f}" for r in allr], rotation=90, fontsize=6)
ax[1].set(ylabel="beam power vs the uniform pick [dB]", title="what backing single elements off costs the beam")
done(t0, fig, "ex20_per_element_backoff.png")
