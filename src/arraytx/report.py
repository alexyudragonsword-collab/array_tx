"""Printing helpers: the engine line every example prints, the disclaimer
that goes with a linearised engine, and small tables."""
from __future__ import annotations

from typing import Iterable

LINEARISED_ENGINES = ("dtc_openloop", "response", "rfdac")
DISCLAIMER = ("线性化引擎，不能背书：杂散 / 互调结论只做趋势比较 "
              "(linearised engine: spur / IM conclusions are trend-only, not evidence)")


def engine_line(modes: Iterable[str], topology: str) -> str:
    """One line naming the phase-modulation engine(s) the run used, with the
    disclaimer when the engine is a linearised one."""
    modes = sorted(set(str(m) for m in modes))
    s = f"engine: {', '.join(modes) or 'n/a'} (topology {topology})"
    if any(m in LINEARISED_ENGINES for m in modes):
        s += " — " + DISCLAIMER
    return s


def table(rows: list[dict], columns: list[str] | None = None, fmt: str = "{:>10}") -> str:
    """Fixed-width text table from dict rows (numbers to 2 decimals)."""
    if not rows:
        return "(empty)"
    cols = columns or list(rows[0].keys())

    def cell(v):
        if isinstance(v, float):
            return f"{v:.2f}"
        return str(v)
    widths = {c: max(len(c), *(len(cell(r.get(c, ""))) for r in rows)) for c in cols}
    line = "  ".join(c.rjust(widths[c]) for c in cols)
    out = [line, "  ".join("-" * widths[c] for c in cols)]
    for r in rows:
        out.append("  ".join(cell(r.get(c, "")).rjust(widths[c]) for c in cols))
    return "\n".join(out)
