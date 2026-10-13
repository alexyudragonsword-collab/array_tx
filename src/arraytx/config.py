"""The one configuration that is the truth (invariant 1).

Array geometry, element topology, standard, coupling source, DPD scheme and
scan angles all live in one YAML file, loaded into the dataclass tree below.
Nothing in the simulation reads a default from anywhere else.

Form-field declarations
-----------------------
Every leaf field carries ``metadata`` with a unit, a help string and, where
it applies, the allowed choices.  ``form_fields()`` walks the tree and returns
them as a flat list — the declaration a GUI (not built this round, polar_tx
style) would render, and what ``tests/test_config.py`` checks for coverage.

Provenance
----------
A numeric leaf in the YAML may be a plain scalar or a mapping
``{value: -16.0, source: survey, ref: "..."}``.  Plain scalars are recorded as
``source: assumed``.  The ``coupling.survey`` block is special: every number
in it must say ``survey`` and carry a ref, or the file does not load — a
survey value without a citation is not allowed into the config (AGENTS.md).
``ArrayConfig.provenance`` maps the dotted path of every numeric leaf to its
:class:`~arraytx.standards.Sourced`.
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from .standards import STANDARDS, Sourced

CONFIG_VERSION = 1


def _f(default, unit: str, help: str, choices: tuple | None = None,
       source: str | None = None, ref: str | None = None, **kw):
    """A leaf field with its form declaration (and, for a default that is an
    external number, its provenance — used when the YAML leaves it out)."""
    md = {"unit": unit, "help": help}
    if choices is not None:
        md["choices"] = tuple(choices)
    if source is not None:
        md["source"] = source
        md["ref"] = ref or ""
    if isinstance(default, (list, dict, tuple)):
        return field(default_factory=lambda: default, metadata=md, **kw)
    return field(default=default, metadata=md, **kw)


@dataclass
class ArrayGeometryCfg:
    n_elements: int = _f(4, "", "number of elements in the linear array")
    spacing_lambda: float = _f(0.5, "lambda0", "element pitch in carrier wavelengths (0.5 = half wave)")
    element_pattern: str = _f("isotropic", "", "element pattern applied to the far field", ("isotropic", "cos"))


@dataclass
class ElementErrorsCfg:
    enabled: bool = _f(True, "", "draw per-element gain/phase/delay errors and PA deviations (off: drawn, then zeroed)")
    gain_sigma_db: float = _f(0.5, "dB", "per-element gain error, 1 sigma")
    phase_sigma_deg: float = _f(5.0, "deg", "per-element phase error at the carrier, 1 sigma")
    delay_sigma_ps: float = _f(2.0, "ps", "per-element group-delay error, 1 sigma")
    pa_dev_sigma: float = _f(0.05, "", "relative 1-sigma deviation of the PA's compression knee (rapp drive) and AM-PM scale")


@dataclass
class ElementPACfg:
    n_bits: int = _f(10, "bit", "DPA amplitude resolution (polar_tx DPAConfig)")
    n_thermo: int = _f(6, "bit", "thermometer-coded MSBs (polar_tx DPAConfig)")
    sigma_cell: float = _f(0.002, "", "relative random unit-cell mismatch (polar_tx DPAConfig)")
    amam: str = _f("rapp", "", "AM-AM law (ideal = polar_tx nr_dtc default)", ("ideal", "rapp"))
    rapp_p: float = _f(2.0, "", "Rapp smoothness (CMOS PA ~1-3); used when amam=rapp")
    rapp_drive: float = _f(1.0, "", "Rapp drive at full scale (compression depth); used when amam=rapp")
    ampm_deg_at_fs: float = _f(8.0, "deg", "AM-PM at full scale, quadratic in amplitude (0 = none)")


@dataclass
class ElementLOCfg:
    shared: bool = _f(True, "", "one physical LO for all elements (identical LO phase-noise sample; jitter stays per element)")
    clock_profile: str | None = _f(None, "path", "pll_simulator clock-profile YAML for the shared LO; null = polar_tx preset LO")
    loop_bw_hz: float = _f(400e3, "Hz", "LO PLL loop bandwidth below which the profile is flattened (polar_tx convention)")


@dataclass
class ElementCfg:
    topology: str = _f("polar", "", "element TX topology (polar_tx class)", ("polar", "outphasing", "rfdac"))
    errors: ElementErrorsCfg = field(default_factory=ElementErrorsCfg)
    pa: ElementPACfg = field(default_factory=ElementPACfg)
    lo: ElementLOCfg = field(default_factory=ElementLOCfg)


@dataclass
class CouplingAnalyticCfg:
    c1_db: float = _f(-16.0, "dB", "adjacent-element coupling magnitude, flat over frequency")
    c1_deg: float = _f(180.0, "deg", "adjacent-element coupling phase, flat over frequency")
    c2_rel_db: float = _f(-6.0, "dB", "next-adjacent coupling relative to c1; further neighbours are zero")


SURVEY_REF_C1 = ("abstract-level only (full texts unreachable from the build environment, see ROADMAP A1); "
                 "arXiv:2407.09944 — 28 GHz FR-2 linear patch array, elements at ~lambda0/2, CATR OTA measurements; "
                 "adjacent coupling in the -13..-16 dB class for uncompensated lambda/2 patches; "
                 "US patent 10910732 — 28 GHz array, measured mutual coupling better than -16 dB; "
                 "Int. J. Electron. Commun. (ScienceDirect S1434841126001263) — lambda/2 (5.4 mm) SIW endfire array, "
                 "adjacent coupling below -15 dB in the lower band")
SURVEY_REF_PHASE = ("sign convention only: the adjacent coupled wave arrives half a wavelength (pi) later at f0 for "
                    "lambda/2 pitch; the papers above do not publish the phase")
SURVEY_REF_C2 = ("next-adjacent coupling 6 dB below adjacent is the common reading of published S-parameter plots "
                 "for lambda/2 patch rows (free-space 1/r over twice the distance); no paper-level number")


@dataclass
class CouplingSurveyCfg:
    c1_db: float = _f(-16.0, "dB", "adjacent-element coupling magnitude at f0 from published lambda/2 patch arrays at 28 GHz",
                      source="survey", ref=SURVEY_REF_C1)
    c1_deg_at_f0: float = _f(180.0, "deg", "adjacent coupling phase at f0", source="survey", ref=SURVEY_REF_PHASE)
    c2_rel_db: float = _f(-6.0, "dB", "next-adjacent coupling relative to c1", source="survey", ref=SURVEY_REF_C2)
    path_delay_from_spacing: bool = _f(True, "", "phase slope vs frequency = free-space delay over the element pitch (linear phase)")


@dataclass
class CouplingTouchstoneCfg:
    path: str | None = _f(None, "path", ".sNp file with N = n_elements ports; interpolated onto the baseband grid")


@dataclass
class CouplingCfg:
    source: str = _f("survey", "", "where the coupling matrix comes from", ("analytic", "survey", "touchstone"))
    scale_db: float = _f(0.0, "dB", "overall scaling of the off-diagonal terms (sweeps); -inf = no coupling")
    analytic: CouplingAnalyticCfg = field(default_factory=CouplingAnalyticCfg)
    survey: CouplingSurveyCfg = field(default_factory=CouplingSurveyCfg)
    touchstone: CouplingTouchstoneCfg = field(default_factory=CouplingTouchstoneCfg)


@dataclass
class BeamCfg:
    steering: str = _f("phase", "", "phase shifters (aligned at f0, squints) or true time delay", ("phase", "ttd"))
    scan_deg: list = _f([0.0, 30.0, 60.0], "deg", "scan angles to evaluate")
    sidelobe: str = _f("auto", "", "sidelobe direction for the second metric set: auto = highest sidelobe of the array factor at f0")


@dataclass
class GMPCfg:
    """Defaults from the milestone-1 sweep (cairn/LOG.md 2026-10-13): the
    element chain is nearly memoryless (DPA + DTC, no measured memory model),
    so memory taps only fit noise and cost ACLR2 (order 9: -48.3 dBc at one
    tap, -44.8 at five); a memoryless 7th order is the best of the 24
    settings tried on ACLR1, ACLR2 and EVM alike, with 7 coefficients."""
    order: int = _f(7, "", "GMP aligned nonlinearity order")
    memory_depth: int = _f(1, "taps", "GMP aligned memory depth (1 = memoryless)")
    lag_order: int = _f(0, "", "GMP lagging cross-term order (0 disables)")
    lag_memory: int = _f(0, "taps", "GMP lagging memory")
    lag_span: int = _f(0, "taps", "GMP lagging span")
    lead_order: int = _f(0, "", "GMP leading cross-term order (0 disables)")
    lead_memory: int = _f(0, "taps", "GMP leading memory")
    lead_span: int = _f(0, "taps", "GMP leading span")


@dataclass
class DPDCfg:
    scheme: str = _f("none", "", "none | one ILA-GMP per element (trained at its conducted port) | one ILA-GMP for the array (trained on the OTA observation at the beam)", ("none", "per_element", "array"))
    n_iterations: int = _f(2, "", "ILA iterations")
    regularization: float = _f(1e-9, "", "relative ridge in the GMP least squares")
    gmp: GMPCfg = field(default_factory=GMPCfg)
    per_element_observe: str = _f("pa_output", "", "what the per-element DPD observes: its own PA forward output, or the antenna port including coupled leakage", ("pa_output", "antenna_port"))


@dataclass
class MetricsCfg:
    aclr_offsets: list = _f([1, 2], "channels", "ACLR adjacent-channel offsets to report")
    evm_equalize: str = _f("scalar", "", "EVM equalisation convention (polar_tx evm_equalize_default)", ("scalar", "per_tone"))


@dataclass
class SimCfg:
    n_symbols: int = _f(8, "symbols", "OFDM symbols per burst")
    smoke_n_symbols: int = _f(2, "symbols", "burst length when ARRAYTX_SMOKE=1 (CI)")
    noise: bool = _f(True, "", "random impairments on (polar_tx run(noise=))")
    cfr_papr_db: float | None = _f(8.5, "dB", "CFR target PAPR applied to the common signal before steering/DPD; null = off")


@dataclass
class ArrayConfig:
    arraytx_config: int = _f(CONFIG_VERSION, "", "config schema version")
    seed: int = _f(1, "", "the one seed every random stream derives from")
    standard: str = _f("fr2_nr400", "", "radio standard", tuple(sorted(STANDARDS)))
    array: ArrayGeometryCfg = field(default_factory=ArrayGeometryCfg)
    element: ElementCfg = field(default_factory=ElementCfg)
    coupling: CouplingCfg = field(default_factory=CouplingCfg)
    beam: BeamCfg = field(default_factory=BeamCfg)
    dpd: DPDCfg = field(default_factory=DPDCfg)
    metrics: MetricsCfg = field(default_factory=MetricsCfg)
    sim: SimCfg = field(default_factory=SimCfg)
    provenance: dict = field(default_factory=dict, metadata={"internal": True})
    source_path: str | None = field(default=None, metadata={"internal": True})

    def validate(self) -> None:
        if self.arraytx_config != CONFIG_VERSION:
            raise ValueError(f"arraytx_config must be {CONFIG_VERSION}")
        for ff in form_fields():
            if ff.choices is not None:
                v = _get(self, ff.path)
                if v not in ff.choices:
                    raise ValueError(f"{ff.path}={v!r} not in {ff.choices}")
        if self.array.n_elements < 1:
            raise ValueError("array.n_elements must be >= 1")
        if self.coupling.source == "touchstone" and not self.coupling.touchstone.path:
            raise ValueError("coupling.source=touchstone needs coupling.touchstone.path")
        if self.dpd.n_iterations < 1:
            raise ValueError("dpd.n_iterations must be >= 1")
        # survey numbers must be cited (AGENTS.md: no uncited survey value)
        for p, s in self.provenance.items():
            if p.startswith("coupling.survey.") and isinstance(_get(self, p), (int, float)) \
                    and not isinstance(_get(self, p), bool):
                if s.source != "survey" or not s.ref:
                    raise ValueError(f"{p}: coupling.survey numbers must carry source: survey and a ref (got {s.source!r})")

    def to_dict(self) -> dict:
        d = _asdict_public(self)
        return d


# --------------------------------------------------------------- utilities
@dataclass(frozen=True)
class FormField:
    path: str
    type: str
    default: Any
    unit: str
    help: str
    choices: tuple | None = None
    source: str | None = None     # provenance of the DEFAULT value, if declared
    ref: str | None = None


def form_fields(cls=ArrayConfig, prefix: str = "") -> list[FormField]:
    """Flat list of every leaf field with its declaration (GUI contract)."""
    out: list[FormField] = []
    for fd in fields(cls):
        if fd.metadata.get("internal"):
            continue
        path = f"{prefix}{fd.name}"
        if is_dataclass(fd.type) or (isinstance(fd.type, str) and fd.type.endswith("Cfg")):
            sub = fd.type if is_dataclass(fd.type) else globals()[fd.type]
            out.extend(form_fields(sub, path + "."))
            continue
        default = fd.default if fd.default is not dataclasses.MISSING else fd.default_factory()  # type: ignore[misc]
        out.append(FormField(path, str(fd.type), default, fd.metadata.get("unit", ""),
                             fd.metadata.get("help", ""), fd.metadata.get("choices"),
                             fd.metadata.get("source"), fd.metadata.get("ref")))
    return out


def _get(obj, path: str):
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _asdict_public(obj):
    if is_dataclass(obj):
        return {fd.name: _asdict_public(getattr(obj, fd.name)) for fd in fields(obj)
                if not fd.metadata.get("internal")}
    if isinstance(obj, (list, tuple)):
        return [_asdict_public(v) for v in obj]
    return obj


def _coerce(value, typ: str, path: str):
    if value is None:
        if "None" in typ:
            return None
        raise ValueError(f"{path}: null not allowed")
    if typ.startswith("bool"):
        if not isinstance(value, bool):
            raise ValueError(f"{path}: expected bool, got {value!r}")
        return value
    if typ.startswith("int"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError(f"{path}: expected int, got {value!r}")
        return int(value)
    if typ.startswith("float"):
        if isinstance(value, str) and value.lower() in ("-inf", "inf", "-.inf", ".inf"):
            return -math.inf if value.startswith("-") else math.inf
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{path}: expected number, got {value!r}")
        return float(value)
    if typ.startswith("str"):
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected string, got {value!r}")
        return value
    if typ.startswith("list"):
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{path}: expected list, got {value!r}")
        return list(value)
    return value


def _build(cls, data: dict, prefix: str, prov: dict):
    if not isinstance(data, dict):
        raise ValueError(f"{prefix or 'root'}: expected a mapping")
    known = {fd.name: fd for fd in fields(cls) if not fd.metadata.get("internal")}
    unknown = set(data) - set(known)
    if unknown:
        raise ValueError(f"{prefix or 'root'}: unknown key(s) {sorted(unknown)}; known: {sorted(known)}")
    kw = {}
    for name, fd in known.items():
        path = f"{prefix}{name}"
        sub = fd.type if is_dataclass(fd.type) else (globals().get(fd.type) if isinstance(fd.type, str) else None)
        if is_dataclass(sub):
            kw[name] = _build(sub, data.get(name, {}), path + ".", prov)
            continue
        if name not in data:
            continue   # dataclass default
        raw = data[name]
        if isinstance(raw, dict) and "value" in raw:
            extra = set(raw) - {"value", "source", "ref"}
            if extra:
                raise ValueError(f"{path}: unknown provenance key(s) {sorted(extra)}")
            src = raw.get("source", "assumed")
            ref = raw.get("ref", "")
            if isinstance(ref, (list, tuple)):
                ref = "; ".join(str(r) for r in ref)
            val = _coerce(raw["value"], str(fd.type), path)
            try:
                prov[path] = Sourced(val, src, ref)
            except ValueError as e:
                raise ValueError(f"{path}: {e}") from None
        else:
            val = _coerce(raw, str(fd.type), path)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                prov[path] = Sourced(val, "assumed")
        kw[name] = val
    return cls(**kw)


def config_from_dict(data: dict, source_path: str | None = None) -> ArrayConfig:
    prov: dict[str, Sourced] = {}
    cfg = _build(ArrayConfig, data, "", prov)
    # default (not-in-file) numeric leaves are assumed too
    for ff in form_fields():
        if ff.path not in prov and isinstance(_get(cfg, ff.path), (int, float)) \
                and not isinstance(_get(cfg, ff.path), bool):
            prov[ff.path] = Sourced(_get(cfg, ff.path), ff.source or "assumed", ff.ref or "")
    cfg.provenance = prov
    cfg.source_path = source_path
    cfg.validate()
    return cfg


def load_config(path: str | Path) -> ArrayConfig:
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cfg = config_from_dict(data, str(path))
    # a touchstone path is relative to the config file
    ts = cfg.coupling.touchstone.path
    if ts and not Path(ts).is_absolute():
        cfg.coupling.touchstone.path = str((path.parent / ts).resolve())
    return cfg


def default_config() -> ArrayConfig:
    return config_from_dict({})
