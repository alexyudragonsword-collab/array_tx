"""ex08 — the planar array: 8 x 8 against the 64 x 1 row it has the same
element count as.

Milestone 2a adds rows (array.n_rows, row-major element order) and the
azimuth of the scan plane (beam.plane_phi_deg).  Everything else -- the
element chains, the coupling path, the far-field synthesis, the DPD -- is
the milestone-1 code with a 2-D position table, so what changes is the
GEOMETRY of the result: the 8 x 8 grid's beam is as wide as an 8-row's in
either principal plane (8 elements across the cut), the 64-row's is eight
times narrower in its one plane and a full 180 deg across it.  The squint
law is the same in any plane (it is a function of sin theta alone), but
whether it costs EVM depends on the beamwidth in THAT plane (ex06): the
64-row pays 0.5 dB at 60 deg, the 8 x 8 pays nothing in either cut.

Part 1: both arrays, 0 / 30 / 60 deg, phase-shifter and TTD steering, in
the x-z plane (phi = 0) and, for the grid, the y-z plane (phi = 90) and the
diagonal (phi = 45): beam EVM / ACLR1, the highest sidelobe of each cut, the
beamwidth.  Part 2: ACLR1 vs direction in the three cuts of the grid with
the array DPD at 30 deg -- where the distortion the beam does not carry
goes.  Part 3: the 2-D coupling matrix of the grid (neighbour classes).
"""
import numpy as np

from _common import banner, done, plt, smoke
from arraytx import ArraySim, load_config
from arraytx.beam import beamwidth_3db_deg
from arraytx.guiutil import direction_scan
from arraytx.report import table

CFG = "configs/fr2_4el_survey.yaml"
ANGLES = [0.0, 30.0, 60.0]
COLORS = {0.0: "#2a78d6", 45.0: "#eb6834", 90.0: "#1baf7a"}


def sim_for(n_x, n_y, phi, steering="phase"):
    cfg = load_config(CFG)
    cfg.array.n_elements, cfg.array.n_rows = n_x, n_y
    cfg.beam.plane_phi_deg, cfg.beam.steering = phi, steering
    return ArraySim(cfg)


grid0 = sim_for(8, 8, 0.0)
t0 = banner("ex08  planar array: 8 x 8 vs 64 x 1 at the same element count", grid0)
rows = []
layouts = [("64 x 1", 64, 1, 0.0), ("8 x 8", 8, 8, 0.0), ("8 x 8", 8, 8, 90.0), ("8 x 8", 8, 8, 45.0)]
if smoke():
    layouts = [("64 x 1", 64, 1, 0.0), ("8 x 8", 8, 8, 0.0), ("8 x 8", 8, 8, 90.0)]
store = {}
for name, nx, ny, phi in layouts:
    for steering in ("phase", "ttd"):
        sim = sim_for(nx, ny, phi, steering)
        for th in ANGLES:
            if th == 0.0 and steering == "ttd":
                continue                                            # identical to phase at broadside by construction
            r = sim.run(th, "none", conducted_diagnostics=False)
            store[(name, phi, steering, th)] = r
            rows.append({"array": name, "plane phi": phi, "steering": steering, "beam deg": th,
                         "3dB bw deg": beamwidth_3db_deg(sim.geom, th, steering),
                         "EVM dB": r.beam.evm_db, "ACLR1": r.beam.aclr1_db,
                         "sidelobe deg": r.sidelobe_deg if r.sidelobe_deg is not None else float("nan"),
                         "SL ACLR1": r.sidelobe.aclr1_db if r.sidelobe else float("nan"), "s": r.seconds})
            print(f"  {name:6s} phi {phi:3.0f} {steering:5s} {th:3.0f} deg: EVM {r.beam.evm_db:7.2f}  ACLR1 {r.beam.aclr1_db:6.1f}  "
                  f"bw {rows[-1]['3dB bw deg']:6.2f}  [{r.seconds:.1f} s]", flush=True)
print("\nPart 1 — OTA at the beam, highest sidelobe of the same cut (survey coupling, element errors on, no DPD):")
print(table(rows))
print("\nphase - TTD EVM penalty at 60 deg:")
for name, nx, ny, phi in layouts:
    p, t = store[(name, phi, "phase", 60.0)], store[(name, phi, "ttd", 60.0)]
    print(f"  {name} phi {phi:.0f}: {p.beam.evm_db - t.beam.evm_db:+.2f} dB  (3 dB beamwidth {beamwidth_3db_deg(sim_for(nx, ny, phi).geom, 60.0):.2f} deg)")

print("\nPart 2 — ACLR1 vs direction, 8 x 8 with the array DPD at the 30 deg beam, three cuts:")
th_grid = np.arange(-90.0, 90.5, 1.0)
cuts = {}
for phi in (COLORS if not smoke() else (0.0, 90.0)):
    sim = sim_for(8, 8, phi)
    r = sim.run(30.0, "array", conducted_diagnostics=False)
    a, p = direction_scan(sim, r.rs, th_grid)
    p = p - p.max()
    cuts[phi] = (a, p, r)
    vis = p > -15
    print(f"  phi {phi:3.0f}: beam ACLR1 {r.beam.aclr1_db:6.1f} dBc, worst in-pattern direction {th_grid[vis][np.argmax(a[vis])]:+.0f} deg "
          f"at {a[vis].max():6.1f} dBc, sidelobe {r.sidelobe_deg:+.1f} deg")

print("\nPart 3 — the 8 x 8 coupling matrix at f0 (survey; element 11 = row 1, column 3 and its neighbours):")
S = grid0.coupling.at(grid0.f0)
k = 11
names = {k - 1: "x1 left", k + 1: "x1 right", k - 2: "x2", k + 2: "x2", k - 8: "y1 up", k + 8: "y1 down", k - 9: "d1", k - 7: "d1", k + 7: "d1", k + 9: "d1", k + 16: "y2"}
crow = [{"to": j, "class": names[j], "|S| dB": 20 * np.log10(abs(S[k, j])), "phase deg": np.degrees(np.angle(S[k, j]))} for j in sorted(names)]
print(table(crow))
print(f"  non-zero pairs: {len(grid0.coupling.nonzero_pairs())} of {64 * 63} (classes x1 / x2 / y1 / y2 / d1); max |S| {grid0.coupling.max_offdiag_db():.1f} dB")

fig, ax = plt.subplots(1, 2, figsize=(11, 4))
for phi, (a, p, r) in cuts.items():
    vis = p > -15
    ax[0].plot(th_grid, p, color=COLORS[phi], lw=1, ls=":", label=f"pattern phi {phi:.0f}")
    ax[1].plot(th_grid[vis], a[vis], color=COLORS[phi], lw=1.6, label=f"ACLR1 phi {phi:.0f} (array DPD)")
ax[0].set(ylim=(-45, 2), xlabel="theta [deg]", ylabel="radiated power [dB]", title="8 x 8 pattern, beam 30 deg, three cuts" + (" (smoke)" if smoke() else ""))
ax[1].set(xlabel="theta [deg]", ylabel="OTA ACLR1 [dBc]  (lower is better)", title="where the distortion goes (nulls not shown)")
ax[0].legend(fontsize=8); ax[1].legend(fontsize=8)
done(t0, fig, "ex08_planar_array.png")
