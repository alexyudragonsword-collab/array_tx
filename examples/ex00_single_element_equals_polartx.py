"""ex00 — one element is one polar_tx chain, bit for bit.

Part 1: the sub-6 anchor config (polar_tx nr_dtc FR1 default, 1 element,
S = 0, element errors off) runs through the whole array path — CFR outside
the chain, pinned full scale, steering, coupling, far field — and the result
is compared with polar_tx's own nr_dtc().run() sample for sample.
Part 2: the same metrics read OTA (broadside) and at the conducted port
coincide for one element, which is the only case where they may.
"""
import numpy as np

from _common import banner, diagnostic_table, done, plt
from arraytx import ArraySim, load_config
from arraytx.report import table
from arraytx.vendor.polartx import nr_dtc
from arraytx.vendor.polartx.vendor.padpd.metrics import psd

cfg = load_config("configs/sub6_1el_anchor.yaml")
sim = ArraySim(cfg)
t0 = banner("ex00  single element == polar_tx (regression anchor)", sim)

r = sim.run(0.0, "none")
ref = nr_dtc().tx.run(sim.wf, noise=True, seed=sim.elements[0].run_seed)
same = bool(np.array_equal(r.ys[0], ref.y)) and bool(np.array_equal(r.far["beam"][1], ref.y))
print(f"\nbit-identical to polar_tx nr_dtc().run(): {same}")
print(f"  max |arraytx - polartx| = {np.abs(r.far['beam'][1] - ref.y).max():.3g}")
print(f"  polar_tx EVM {ref.evm().db:.2f} dB | arraytx OTA (broadside) EVM {r.beam.evm_db:.2f} dB")
print("\nOTA metrics (acceptance):")
print(table([r.beam.row()]))
print()
print(diagnostic_table(r))

f, p_a = psd(r.far["beam"][1], sim.fs)
_, p_r = psd(ref.y, sim.fs)
fig, ax = plt.subplots(1, 2, figsize=(10, 3.4))
ax[0].plot(f / 1e6, p_r, color="#2a78d6", label="polar_tx nr_dtc()")
ax[0].plot(f / 1e6, p_a, color="#eb6834", ls="--", lw=1.0, label="arraytx 1 element, S = 0 (OTA)")
ax[0].set(xlabel="baseband frequency [MHz]", ylabel="PSD [dB rel. peak]", title="spectra overlay")
ax[0].legend()
ax[1].plot(f / 1e6, p_a - p_r, color="#1baf7a")
ax[1].set(xlabel="baseband frequency [MHz]", ylabel="difference [dB]", title=f"difference (bit-identical: {same})")
done(t0, fig, "ex00_anchor.png")
