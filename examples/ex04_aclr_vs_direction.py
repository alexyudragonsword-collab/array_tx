"""ex04 — where does the nonlinear distortion radiate?

For the beam at 30 deg, the far field is synthesised on a 1-degree grid
from -90 to +90 and the first-adjacent ACLR read in every direction, for the
three DPD schemes, under the analytic and the survey coupling.  The array
DPD is trained on the beam direction only: whatever it leaves behind
elsewhere shows up here as the gap between the curves away from the beam.
"""
import numpy as np

from _common import SCHEME_COLORS, SCHEME_LABELS, banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.metrics import aclr1_vs_direction, power_vs_direction_db

theta0 = 30.0
schemes = ("none", "per_element", "array")
thetas = np.arange(-90.0, 90.0 + 0.5, 3.0 if smoke() else 1.0)
sims = {k: ArraySim(load_config(f"configs/fr2_4el_{k}.yaml")) for k in ("analytic", "survey")}
t0 = banner("ex04  ACLR vs direction (beam 30 deg)", sims["survey"])

fig, ax = plt.subplots(2, 2, figsize=(11, 6.4), sharex=True)
for col, (k, sim) in enumerate(sims.items()):
    print(f"\n[{k}]  beam {theta0:.0f} deg, |S21| {sim.coupling.max_offdiag_db():.1f} dB")
    for s in schemes:
        r = sim.run(theta0, s, conducted_diagnostics=False)
        e = sim.far_field_many(r.rs, thetas)
        a = aclr1_vs_direction(e, sim.wf, thetas)
        p = power_vs_direction_db(e)
        p -= p.max()
        i_beam = int(np.argmin(np.abs(thetas - theta0)))
        # ACLR in a pattern null is the distortion of the neighbours over a
        # vanishing carrier: real, but not a direction anyone transmits in.
        # The "worst direction" is read where the pattern is within 15 dB.
        lit = p >= -15.0
        i_worst = int(np.flatnonzero(lit)[np.argmax(a[lit])])
        print(f"  {SCHEME_LABELS[s]:24s}: ACLR1 at beam {a[i_beam]:6.1f} dBc | worst lit direction (pattern >= -15 dB) "
              f"{thetas[i_worst]:+5.0f} deg: {a[i_worst]:6.1f} dBc | sidelobe {r.sidelobe_deg:+.1f} deg: "
              f"{r.sidelobe.aclr1_db:6.1f} dBc | in the nulls up to {a.max():6.1f} dBc")
        if s == "none":
            ax[0, col].plot(thetas, p, color="#8a8a85", lw=1.2)
        ax[1, col].plot(thetas, a, color=SCHEME_COLORS[s], label=SCHEME_LABELS[s])
    ax[0, col].set(title=f"{k} coupling (|S21| {sim.coupling.max_offdiag_db():.0f} dB) — radiated power pattern", ylabel="pattern [dB rel. peak]")
    ax[0, col].set_ylim(-40, 2)
    ax[1, col].set(xlabel="direction [deg]", ylabel="OTA ACLR1 [dBc]", title="ACLR1 vs direction (lower is better; nulls shaded)")
    ax[1, col].set_ylim(-20, -50)
    ax[1, col].fill_between(thetas, -20, -50, where=~lit, color="#e3e2dd", alpha=0.6, lw=0)
    for a_ in ax[:, col]:
        a_.axvline(theta0, color="#8a8a85", lw=0.8, ls=":")
ax[1, 0].legend(fontsize=8)
fig.suptitle("ex04 — where the distortion radiates" + (" (smoke)" if smoke() else ""), y=1.0)
done(t0, fig, "ex04_aclr_vs_direction.png")
