"""Printing helpers: the engine line every example prints, the disclaimer
that goes with an engine and grid whose numbers are not evidence (and
why), and small tables."""
from __future__ import annotations

from typing import Iterable

#: every disclaimer carries this phrase; tests and the page look for it
NOT_EVIDENCE = "不能背书"

#: grid samples per update of the polar element's clock at which ex22 (reading P,
#: clock at 4 x the FFT rate) found ACLR1 / ACLR2, scalar and per-tone EVM and the
#: visible-band mask converged: os 16, within 0.15 dB of os 32 on every one of them
#: (polar_tx's grid.CONVERGED_HOLD is the same 4; tests/test_metrics.py holds that)
CONVERGED_HOLD = 4

#: why a run's numbers are not evidence, per engine and grid (cairn/dtc-openloop-grid.md)
DISCLAIMERS = {
    "response": ("线性化引擎，不能背书：杂散 / 互调结论只做趋势比较 "
                 "(linearised engine: spur / IM conclusions are trend-only, not evidence)"),
    "dtc_openloop": ("采样网格未收敛（每次更新 < 4 个网格点，即 4× 时钟上 os < 16；ex22：ACLR1 偏保守 0.3–0.5 dB、"
                     "ACLR2 偏保守约 2.1 dB、可见带模板偏保守 0.4–0.6 dB，可作上界；scalar EVM 少算保持下垂，偏乐观至多 0.5 dB；"
                     "看不到时钟镜像；per-tone EVM 已收敛），不能背书：杂散 / 模板结论只做趋势比较 "
                     "(grid not converged, < 4 grid samples per update: ACLR and mask read pessimistic, scalar EVM "
                     "optimistic, per-tone EVM converged; spur / mask conclusions are trend-only, not evidence)"),
    "dtc_openloop_tied": ("更新时钟随网格（polar_tx 只给 polar 链分开了时钟）：提高 os 换的是更快的硬件，网格收敛未验证，"
                          "不能背书：杂散 / 模板结论只做趋势比较 "
                          "(update clock tied to the grid, raising os clocks the hardware faster; grid convergence "
                          "unverified: spur / mask conclusions are trend-only, not evidence)"),
    "rfdac": ("RF-DAC 模型只有失配、没有压缩，时钟随网格、网格收敛未验证，不能背书：杂散 / 互调结论只做趋势比较 "
              "(RF-DAC model has mismatch only, its clock tied to the grid: spur / IM conclusions are trend-only, "
              "not evidence)"),
    "full_span": ("全幅模板（sem_full）：时钟镜像未滤波（没有输出滤波器模型），镜像电平 os 16 → 32 还动 0.56 dB，不能背书 "
                  "(full-span mask: the clock images are unfiltered and still move 0.56 dB from os 16 to 32, not evidence)"),
}
#: kept for callers that print the generic wording
DISCLAIMER = DISCLAIMERS["response"]
#: what a converged run's engine line says instead of the grid disclaimer
CONVERGED_NOTE = ("采样网格已收敛（每次更新 ≥ 4 个网格点；ex22：ACLR、scalar / per-tone EVM、可见带模板 os 32 与 os 16 差 ≤ 0.15 dB）"
                  " (grid converged, >= 4 grid samples per update: ACLR, EVM and the visible-band mask, ex22)")


def disclaimer_for(mode: str, topology: str, hold: int | None) -> str | None:
    """The disclaimer one engine's run needs for its ACLR / EVM / visible-band
    mask readings, or None when they are evidence.  ``hold`` is the grid
    samples per update of the element clock (``ArraySim.hold``; None =
    unknown, treated as not converged).  Only what ex22 checked is cleared:
    dtc_openloop on the polar chain, the clock held >= CONVERGED_HOLD
    samples (os >= 16).  The other topologies keep their clock on the grid
    (polar_tx models the split for the polar chain only), so a finer grid
    is a faster chip there, never a converged reading.  The full-span mask
    is not cleared on any grid (``engine_line`` says so)."""
    if mode == "dtc_openloop":
        if topology != "polar":
            return DISCLAIMERS["dtc_openloop_tied"]
        if hold is None or hold < CONVERGED_HOLD:
            return DISCLAIMERS["dtc_openloop"]
        return None
    return DISCLAIMERS.get(mode)


def engine_line(modes: Iterable[str], topology: str, oversampling: int | None = None,
                hold: int | None = None) -> str:
    """One line naming the phase-modulation engine(s) the run used and the
    grid, with the reason its numbers are not evidence when they are not
    (``disclaimer_for``).  A converged run says so, and that its full-span
    mask still is not evidence (the clock images are unfiltered)."""
    modes = sorted(set(str(m) for m in modes))
    grid = "" if oversampling is None else f", os {int(oversampling)}"
    if hold is not None and hold > 1:
        grid += f", {int(hold)} grid samples per update"
    s = f"engine: {', '.join(modes) or 'n/a'} (topology {topology}{grid})"
    notes = [d for d in dict.fromkeys(disclaimer_for(m, topology, hold) for m in modes) if d]
    if notes:
        s += " — " + " / ".join(notes)
    elif "dtc_openloop" in modes:
        s += " — " + CONVERGED_NOTE + " / " + DISCLAIMERS["full_span"]
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
