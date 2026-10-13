"""Invariant 5: random instances are seeded, independent and reproducible."""
import numpy as np
import pytest

from arraytx.seeds import ELEMENT_STREAMS, GLOBAL_STREAMS, SeedTree


def _draws(tree, k):
    return {s: tree.rng(s, k).standard_normal(4) for s in ELEMENT_STREAMS}


def test_same_seed_reproduces_bitwise():
    a, b = SeedTree(7, 4), SeedTree(7, 4)
    for k in range(4):
        for s in ELEMENT_STREAMS:
            assert np.array_equal(_draws(a, k)[s], _draws(b, k)[s])
    for s in GLOBAL_STREAMS:
        assert np.array_equal(a.rng(s).standard_normal(3), b.rng(s).standard_normal(3))


def test_streams_are_independent_across_elements_and_names():
    t = SeedTree(1, 4)
    seen = {}
    for k in range(4):
        for s in ELEMENT_STREAMS:
            v = tuple(t.rng(s, k).standard_normal(3))
            assert v not in seen.values(), f"stream {s}@{k} collides with {[kk for kk, vv in seen.items() if vv == v]}"
            seen[(s, k)] = v
    for s in GLOBAL_STREAMS:
        assert tuple(t.rng(s).standard_normal(3)) not in seen.values()


def test_adding_elements_keeps_existing_draws():
    """spawn is indexed, not positional: an 8-element array's first four
    elements draw exactly what the 4-element array drew."""
    a, b = SeedTree(3, 4), SeedTree(3, 8)
    for k in range(4):
        da, db = _draws(a, k), _draws(b, k)
        for s in ELEMENT_STREAMS:
            assert np.array_equal(da[s], db[s])
    for s in GLOBAL_STREAMS:
        assert np.array_equal(a.rng(s).standard_normal(3), b.rng(s).standard_normal(3))


def test_int_seed_is_stable_and_distinct():
    t = SeedTree(5, 3)
    seeds = [t.int_seed("run", k) for k in range(3)] + [t.int_seed("dpa_mismatch", k) for k in range(3)]
    assert len(set(seeds)) == 6
    assert all(0 <= s < 2 ** 31 for s in seeds)
    assert t.int_seed("run", 1) == SeedTree(5, 3).int_seed("run", 1)


def test_bad_stream_or_index_raises():
    t = SeedTree(1, 2)
    with pytest.raises(KeyError):
        t.rng("nope", 0)
    with pytest.raises(IndexError):
        t.rng("gain", 2)
    with pytest.raises(ValueError):
        SeedTree(1, 0)
