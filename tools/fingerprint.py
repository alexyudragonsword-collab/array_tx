#!/usr/bin/env python3
"""Numerical fingerprint of the library (invariant 6), after Halo_Serdes.

``record OUT.json`` runs a fixed set of smoke-size scenarios and stores, for
every array, a SHA-256 digest (first 16 hex) over its float64 bytes, and for
every scalar its ``repr``.  ``compare A.json B.json`` lists the entries that
differ and exits 1 if any do.  Exceptions are recorded as values too, so two
sides failing the same way compare equal and the failure is visible.

A refactor must come back ``bit-identical``.  A fix may change only the
entries it explains, and the commit message lists them (CONTRIBUTING 3).
Bit-exact means the same machine and library versions.

Usage::

    python tools/fingerprint.py record before.json
    python tools/fingerprint.py record after.json
    python tools/fingerprint.py compare before.json after.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

os.environ.setdefault("ARRAYTX_SMOKE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

SCENARIOS = [
    ("anchor", "configs/sub6_1el_anchor.yaml", 0.0, ("none",)),
    ("fr2_survey", "configs/fr2_4el_survey.yaml", 30.0, ("none", "per_element", "array")),
    ("fr2_analytic", "configs/fr2_4el_analytic.yaml", 60.0, ("none", "array")),
    ("fr2_ttd", "configs/fr2_4el_survey.yaml", 60.0, ("none",)),
]


def digest(a) -> str:
    a = np.ascontiguousarray(np.asarray(a))
    if np.iscomplexobj(a):
        a = np.ascontiguousarray(a.astype(np.complex128))
    else:
        a = np.ascontiguousarray(a.astype(np.float64))
    return hashlib.sha256(a.tobytes()).hexdigest()[:16]


def _guarded(out: dict, key: str, fn) -> None:
    try:
        out[key] = fn()
    except Exception as e:                           # recorded, not raised
        out[key] = {"error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc().splitlines()[-1]}


def record() -> dict:
    from arraytx import ArraySim, load_config
    out: dict = {"_smoke": os.environ.get("ARRAYTX_SMOKE", "")}
    for name, path, theta, schemes in SCENARIOS:
        cfg = load_config(path)
        if name == "fr2_ttd":
            cfg.beam.steering = "ttd"
        sim = ArraySim(cfg)
        out[f"{name}.x"] = digest(sim.x)
        out[f"{name}.coupling.s"] = digest(sim.coupling.s)
        for k, el in enumerate(sim.elements):
            e = el.errors
            out[f"{name}.el{k}.errors"] = repr((e.gain_db, e.phase_deg, e.delay_s, e.pa_dev))
            out[f"{name}.el{k}.seeds"] = repr((el.run_seed, el.dpa_cfg.seed, el.lo_pn_seed, el.fs_scale))
        for s in schemes:
            def run(sim=sim, theta=theta, s=s):
                r = sim.run(theta, s)
                d = {"ys": digest(r.ys), "rs": digest(r.rs), "far_beam": digest(r.far["beam"][1]),
                     "drive0": digest(r.drives[0]),
                     "beam": {k: repr(v) for k, v in r.beam.row().items()},
                     "sidelobe_deg": repr(r.sidelobe_deg)}
                if r.sidelobe is not None:
                    d["sidelobe"] = {k: repr(v) for k, v in r.sidelobe.row().items()}
                d["conducted"] = [repr(c.aclr1_db) for c in r.conducted]
                return d
            _guarded(out, f"{name}.{theta:g}.{s}", run)
    return out


def flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def compare(a: dict, b: dict) -> int:
    fa, fb = flatten(a), flatten(b)
    keys = sorted(set(fa) | set(fb))
    diff = [k for k in keys if fa.get(k) != fb.get(k)]
    errs = [k for k in keys if k.endswith(".error")]
    for k in diff:
        print(f"DIFF {k}\n    A: {fa.get(k)!r}\n    B: {fb.get(k)!r}")
    if errs:
        print(f"{len(errs)} recorded error(s) (equal on both sides unless listed above): " + ", ".join(errs))
    print(f"{len(keys)} entries, {len(diff)} differ")
    if diff:
        return 1
    print("bit-identical")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record"); r.add_argument("out")
    c = sub.add_parser("compare"); c.add_argument("a"); c.add_argument("b")
    args = ap.parse_args(argv)
    if args.cmd == "record":
        out = record()
        Path(args.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        n = len(flatten(out))
        print(f"wrote {args.out}: {n} entries")
        return 0
    return compare(json.loads(Path(args.a).read_text()), json.loads(Path(args.b).read_text()))


if __name__ == "__main__":
    raise SystemExit(main())
