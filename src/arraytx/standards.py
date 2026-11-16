"""Radio standards the array can transmit (invariant 1: numbers come from the
config's ``standard`` key, and every external number here carries a source).

Two coexist from day one:

* ``sub6_nr100`` — polar_tx's own FR1 preset (``nr_dtc(bw=100e6)``), used as
  the "bit-identical to one polar_tx chain" regression anchor.  Nothing here
  is re-derived: the preset factory and its waveform maker are polar_tx's.
* ``fr2_nr400`` — 5G NR FR2, 28 GHz carrier, 400 MHz channel, 120 kHz SCS.
  polar_tx's ``nr_dtc`` carries the FR2 element chain (28 GHz, 120 kHz,
  64-QAM, mmWave LO) and, since polar_tx@008cc90, the 400 MHz numerology
  row too; the waveform is polar_tx's own ``nr_waveform``.

Sources are listed per number; ``survey`` means read from the cited spec
clause (the clause text itself could not be re-opened from this environment,
which the LOG records), ``derived`` means computed from survey numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .vendor.polartx import nr_dtc
from .vendor.polartx.presets import TxPreset, burst_on_grid
from .vendor.polartx.waveforms.base import Waveform
from .vendor.polartx.waveforms.ofdm import NR_NUMEROLOGY, nr_waveform

TS38101_2 = "3GPP TS 38.101-2 (NR UE radio transmission and reception; Part 2: Range 2 Standalone)"


@dataclass(frozen=True)
class Sourced:
    """A number with its provenance."""
    value: Any
    source: str          # survey | derived | assumed | measured
    ref: str = ""

    def __post_init__(self):
        if self.source not in ("survey", "derived", "assumed", "measured"):
            raise ValueError(f"bad source {self.source!r}")
        if self.source in ("survey", "measured") and not self.ref:
            raise ValueError(f"source {self.source!r} needs a ref")


@dataclass(frozen=True)
class Standard:
    name: str
    carrier_hz: Sourced
    bandwidth_hz: Sourced
    scs_hz: Sourced
    fft_size: Sourced
    n_rb: Sourced
    qam: Sourced
    oversampling: Sourced
    evm_limit_pct: Sourced
    update_oversampling: Sourced            # the polar element's DTC / DPA clock, x FFT rate
    polartx_native: bool = False   # waveform and preset come from polar_tx as-is
    oversampling_overridden: bool = False   # set by with_oversampling (config sim.oversampling)
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def fs_hz(self) -> float:
        return float(self.fft_size.value * self.scs_hz.value * self.oversampling.value)

    @property
    def n_active_tones(self) -> int:
        return int(12 * self.n_rb.value)

    def numbers(self) -> dict[str, Sourced]:
        return {k: getattr(self, k) for k in
                ("carrier_hz", "bandwidth_hz", "scs_hz", "fft_size", "n_rb",
                 "qam", "oversampling", "update_oversampling", "evm_limit_pct")}

    def clock_hold(self, *, tied: bool = False) -> int:
        """Grid samples per update of the polar element's clock; 1 when the
        clock is ``tied`` to the grid (outphasing / RF-DAC: polar_tx models the
        clock / grid split for the polar chain only)."""
        return 1 if tied else int(self.oversampling.value) // int(self.update_oversampling.value)

    def with_oversampling(self, k: int) -> "Standard":
        """This standard on a k-times oversampled grid (config ``sim.oversampling``):
        the same symbols and numerology, fs = FFT x SCS x k.  The value is a study
        setting, so it is labelled assumed.  The polar element's clock stays at
        ``update_oversampling`` (4 x the FFT rate): a finer grid holds each
        update for k / 4 samples (arraytx.clock), so k must be a multiple of 4."""
        k = int(k)
        if self.polartx_native:
            # the anchor's waveform is polar_tx's own preset waveform: an override
            # would not reach it, and a silently ignored setting is worse than none
            raise ValueError(f"{self.name}: sim.oversampling cannot override the polar_tx-native anchor")
        u = int(self.update_oversampling.value)
        if k < u or k % u:
            raise ValueError(f"sim.oversampling must be a multiple of the element clock's {u} "
                             f"(the grid holds a whole number of samples per update), got {k}")
        return replace(self, oversampling=Sourced(k, "assumed", "config sim.oversampling (study setting)"),
                       oversampling_overridden=True)

    # ------------------------------------------------------- construction
    def preset(self, **overrides) -> TxPreset:
        """polar_tx's ``nr_dtc`` preset for this standard.

        ``overrides`` are forwarded (``cfr_papr_db``, ``dpa``, ``lo_pn`` ...).
        For the native sub-6 anchor the defaults are polar_tx's own.  The
        DTC / DPA clock is ``update_oversampling`` x the FFT rate on any grid
        (polar_tx's ``ChainConfig.f_clock``): a finer grid holds its output,
        it does not clock the chain faster.
        """
        kw: dict[str, Any] = dict(bw=float(self.bandwidth_hz.value))
        if not self.polartx_native:
            kw.update(scs=float(self.scs_hz.value), qam=int(self.qam.value),
                      fout=float(self.carrier_hz.value),
                      oversampling=int(self.oversampling.value),
                      update_oversampling=int(self.update_oversampling.value))
        kw.update(overrides)
        return nr_dtc(**kw)

    def make_waveform(self, n_symbols: int, seed: int, *, tied: bool = False) -> Waveform:
        """The burst on the simulation grid, generated at the element clock and
        interpolated onto the grid (polar_tx ``burst_on_grid``: the chain reads
        the update-rate burst bit for bit at any grid, so a grid study compares
        one input).  ``tied``: the clock is the grid (outphasing / RF-DAC), the
        burst is generated on the grid.  ``meta["clock_hold"]`` carries the
        grid samples per update (arraytx.clock)."""
        m = self.clock_hold(tied=tied)
        if self.polartx_native:
            wf = self.preset().make_waveform(n_symbols=n_symbols, seed=seed)
            return replace(wf, meta={**wf.meta, "clock_hold": m})
        # polar_tx@008cc90 carries the 400 MHz @ 120 kHz row, so the FR2
        # waveform is polar_tx's own nr_waveform; the table's FFT / RB must
        # agree with this standard's sourced numbers (tested).
        fft, n_rb = NR_NUMEROLOGY[(float(self.bandwidth_hz.value), float(self.scs_hz.value))]
        if (fft, n_rb) != (int(self.fft_size.value), int(self.n_rb.value)):
            raise ValueError(f"{self.name}: polar_tx numerology {(fft, n_rb)} disagrees with "
                             f"the standard's {(self.fft_size.value, self.n_rb.value)}")
        k = int(self.oversampling.value)
        wf = burst_on_grid(
            lambda os_: nr_waveform(float(self.bandwidth_hz.value), float(self.scs_hz.value),
                                    int(self.qam.value), n_symbols=int(n_symbols),
                                    oversampling=os_, seed=int(seed)),
            k, None if m == 1 else k // m)
        return replace(wf, meta={**wf.meta, "clock_hold": m})


FR2_NR400 = Standard(
    name="fr2_nr400",
    carrier_hz=Sourced(28e9, "survey", f"{TS38101_2} Table 5.2-1: n257 26.5-29.5 GHz, n261 27.5-28.35 GHz; 28 GHz is inside both"),
    bandwidth_hz=Sourced(400e6, "survey", f"{TS38101_2} Table 5.3.5-1: 400 MHz channel bandwidth for 120 kHz SCS"),
    scs_hz=Sourced(120e3, "survey", f"{TS38101_2} Table 5.3.5-1: 120 kHz SCS supports 400 MHz"),
    fft_size=Sourced(4096, "derived", "smallest power of two above N_RB*12 = 3168 tones (same convention as polar_tx nr_waveform / 38.104)"),
    n_rb=Sourced(264, "survey", f"{TS38101_2} Table 5.3.2-1: N_RB = 264 for 400 MHz at 120 kHz SCS (cross-checked against the 9860 kHz minimum guardband in Table 5.3.3-1)"),
    qam=Sourced(64, "survey", f"{TS38101_2} Table 6.4.2.1-1: FR2 UE EVM limit given up to 64-QAM (polar_tx's nr_dtc FR2 branch uses the same)"),
    oversampling=Sourced(4, "derived", "fs >= 4.9*BW is what aclr_multi needs for ACLR2 (polar_tx metrics/aclr_ext.py); 4 x 491.52 = 1966.08 MS/s"),
    evm_limit_pct=Sourced(8.0, "survey", f"{TS38101_2} Table 6.4.2.1-1: 64-QAM EVM 8 %"),
    update_oversampling=Sourced(4, "survey", "polar_tx@0e7b7ac presets.py nr_dtc update_oversampling default: "
                                             "the DTC / DPA update clock is 4 x the FFT rate, 1966.08 MHz"),
    notes=("Relative bandwidth 400 MHz / 28 GHz = 1.43 %: wide enough for squint and wideband coupling to show.",
           "The FR2 element chain is polar_tx nr_dtc's bw>100 MHz branch (open-loop DTC, -100 dBc/Hz @ 1 MHz LO)."),
)

SUB6_NR100 = Standard(
    name="sub6_nr100",
    carrier_hz=Sourced(3.5e9, "survey", "polar_tx presets.py nr_dtc FR1 default (n78)"),
    bandwidth_hz=Sourced(100e6, "survey", "polar_tx presets.py nr_dtc default"),
    scs_hz=Sourced(30e3, "survey", "polar_tx presets.py nr_dtc FR1 default"),
    fft_size=Sourced(4096, "survey", "polar_tx waveforms/ofdm.py NR_NUMEROLOGY[(100e6, 30e3)]"),
    n_rb=Sourced(273, "survey", "polar_tx waveforms/ofdm.py NR_NUMEROLOGY[(100e6, 30e3)]"),
    qam=Sourced(256, "survey", "polar_tx presets.py nr_dtc FR1 default"),
    oversampling=Sourced(4, "survey", "polar_tx waveforms/ofdm.py nr_waveform default"),
    evm_limit_pct=Sourced(3.5, "survey", "polar_tx presets.py nr_dtc docstring: 256-QAM 3.5 %"),
    update_oversampling=Sourced(4, "survey", "polar_tx@0e7b7ac presets.py nr_dtc update_oversampling default "
                                             "(4 x 122.88 MHz = 491.52 MHz)"),
    polartx_native=True,
    notes=("Regression anchor: waveform and chain are polar_tx's nr_dtc() verbatim; one element with S = 0 must reproduce it bit for bit.",),
)

STANDARDS: dict[str, Standard] = {s.name: s for s in (FR2_NR400, SUB6_NR100)}


def get_standard(name: str) -> Standard:
    try:
        return STANDARDS[name]
    except KeyError:
        raise KeyError(f"unknown standard {name!r}; one of {sorted(STANDARDS)}") from None
