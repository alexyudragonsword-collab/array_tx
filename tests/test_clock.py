"""The element clock and the simulation grid (arraytx.clock, polar_tx@0e7b7ac).

The digital front end runs at the 4x update clock on any grid, and a finer
grid adds only what the hold does on the grid: its in-band droop and its
images at multiples of the clock.  These tests hold that, end to end."""
import numpy as np
import pytest

from arraytx import ArraySim, load_config
from arraytx.clock import clock_hold, to_clock, to_grid

N_SYM = 2


def _sim(os_, **edit):
    cfg = load_config("configs/fr2_4el_survey.yaml")
    cfg.sim.oversampling = os_
    cfg.sim.noise = False
    for path, v in edit.items():
        obj = cfg
        *head, last = path.split(".")
        for h in head:
            obj = getattr(obj, h)
        setattr(obj, last, v)
    return ArraySim(cfg, n_symbols=N_SYM)


@pytest.mark.parametrize("n", [96, 97])
@pytest.mark.parametrize("m", [1, 2, 4])
def test_to_grid_passes_through_the_clock_samples_and_to_clock_inverts_it(n, m):
    rng = np.random.default_rng(3)
    x = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    g = to_grid(x, m)
    assert g.size == n * m and np.array_equal(g[::m], x)        # bit for bit: the chain reads these
    assert np.allclose(to_clock(g, m), x, atol=1e-12)
    if m == 1:
        assert g is x and to_clock(x, 1) is x


def test_to_clock_drops_the_images_and_keeps_the_band():
    """An ideal receiver at the clock: a tone inside the clock's Nyquist passes,
    its image one clock up (where the hold puts it) is removed."""
    n, m = 256, 4
    t = np.arange(n * m)
    inband = np.exp(2j * np.pi * 10 * t / (n * m))               # bin 10 of the clock's 256
    image = 0.1 * np.exp(2j * np.pi * (10 + n) * t / (n * m))    # one clock above it
    y = to_clock(inband + image, m)
    assert np.allclose(y, np.exp(2j * np.pi * 10 * np.arange(n) / n), atol=1e-12)


def test_the_chain_reads_the_same_samples_on_every_grid():
    """burst_on_grid and CFR at the clock: the update-instant samples of the
    common drive are the os-4 drive bit for bit, at os 8 and os 16; so is the
    pinned full scale (read at the clock)."""
    s4 = _sim(4)
    for k in (8, 16):
        s = _sim(k)
        m = k // 4
        assert s.hold == m == clock_hold(s.wf) and all(el.hold == m for el in s.elements)
        assert np.array_equal(s.wf.x[::m], s4.wf.x) and np.array_equal(s.x[::m], s4.x)
        assert [el.fs_scale for el in s.elements] == [el.fs_scale for el in s4.elements]
        assert s.standard.update_oversampling.source == "survey"


def test_a_finer_grid_adds_only_the_hold_in_the_far_field():
    """No DPD, noise off: the far field at os 8, observed at the clock, is the
    os-4 far field through the centred hold's in-band response
    sin(pi k / n) / (m sin(pi k / N)) -- coupling, steering, the elements'
    analog errors and the far-field synthesis on the grid change nothing else."""
    s4, s8 = _sim(4), _sim(8)
    r4, r8 = s4.run(30.0, "none", conducted_diagnostics=False), s8.run(30.0, "none", conducted_diagnostics=False)
    e4, e8 = r4.far["beam"][1], r8.far["beam"][1]
    n, m = e4.size, 2
    k = np.fft.fftfreq(n) * n
    with np.errstate(invalid="ignore", divide="ignore"):
        d = np.where(k == 0, 1.0, np.sin(np.pi * k / n) / (m * np.sin(np.pi * k / (n * m))))
    # the clock's Nyquist bin is one bin at os 4 and two (+-fs4/2) on the finer grid,
    # where a delay or a frequency-dependent coupling acts on each half separately:
    # it has no os-4 counterpart, so it is left out of the comparison
    keep = np.abs(k) < n // 2

    def gap(a8, a4):
        want = np.fft.fft(a4) * d * keep
        return np.max(np.abs(np.fft.fft(to_clock(a8, m)) * keep - want)) / np.max(np.abs(want))
    # the element outputs (chain, hold, analog gain / phase / delay errors): to FFT rounding
    assert max(gap(r8.ys[i], r4.ys[i]) for i in range(len(s4.elements))) < 1e-12
    # after coupling: S(f) is tabulated at 257 points across f0 +- fs/2 and interpolated
    # linearly (coupling.build_coupling), so a wider grid tabulates it more coarsely --
    # ~1e-7 here, a property of the coupling table, not of the clock
    assert gap(e8, e4) < 1e-6
    # and the hold's first image is there, on the grid: centred on the clock (1966 MHz, the
    # os-8 grid's edge), where the hold's sinc is zero; the two images hold ~-22 dB of the signal
    sp = np.abs(np.fft.fft(e8)) ** 2
    f = np.fft.fftfreq(e8.size, 1 / s8.fs)
    img = np.abs(f) > s8.fs / m - s8.wf.bw / 2
    assert sp[img].sum() > 1e-3 * sp.sum()
    assert "sem_full_margin_db" in r8.beam.row() and "sem_full_margin_db" not in r4.beam.row()


def test_dpd_runs_at_the_clock():
    """The bank remembers its clock; every drive is a clock-rate predistorter
    output on the grid (its update-instant samples are the GMP's output)."""
    s8 = _sim(8)
    for scheme in ("per_element", "array"):
        r = s8.run(30.0, scheme, conducted_diagnostics=False)
        assert r.dpd.hold == 2
        assert all(d.size == s8.wf.n for d in r.drives)
    r = s8.run(30.0, "per_element", conducted_diagnostics=False)
    from arraytx.beam import steer
    dr = steer(s8.x, s8.geom, 30.0, s8.fs, s8.cfg.beam.steering)
    assert np.array_equal(r.drives[1][::2], r.dpd.per_element[1](dr[1][::2]))


def test_load_pull_takes_the_load_at_the_update_instants():
    s8 = _sim(8, **{"element.pa.load_pull.enabled": True})
    assert s8.load_pull_active
    s8.run(30.0, "none", conducted_diagnostics=False)
    el = s8.elements[0]
    assert el.load.size == s8.wf.n and el.tx.dpa.gamma.size == s8.wf.n // 2
    assert np.array_equal(el.tx.dpa.gamma, el.load[::2])


def test_topologies_without_the_split_keep_their_clock_on_the_grid():
    """polar_tx models the clock / grid split for the polar chain only:
    outphasing on a finer grid runs with its clock tied to the grid."""
    s = _sim(8, **{"element.topology": "outphasing"})
    assert s.hold == 1 and all(el.hold == 1 for el in s.elements)
    s.run(0.0, "none", conducted_diagnostics=False)


def test_the_grid_must_hold_whole_updates():
    for bad in (2, 6):
        with pytest.raises(ValueError, match="multiple"):
            _sim(bad)


def test_direction_readings_follow_the_grid():
    """On a finer grid the direction scan reads the clock grid's resolution and
    the power within the clock's Nyquist (the hold's images radiate elsewhere):
    the page's per-segment scan still matches the exact path."""
    from arraytx.guiutil import direction_scan
    from arraytx.metrics import aclr1_vs_direction, power_vs_direction_db
    s8 = _sim(8)
    r = s8.run(30.0, "none", conducted_diagnostics=False)
    th = np.arange(-90.0, 91.0, 6.0)
    a, p = direction_scan(s8, r.rs, th)
    e = s8.far_field_many(r.rs, th)
    a0, p0 = aclr1_vs_direction(e, s8.wf, th), power_vs_direction_db(e, s8.wf)
    assert np.abs(a - a0).max() < 0.05
    assert np.abs((p - p.max()) - (p0 - p0.max())).max() < 0.05
    full = power_vs_direction_db(e)                       # whole grid: the images are in it
    assert np.all(full >= p0 - 1e-9) and np.max(full - p0) > 0.01
