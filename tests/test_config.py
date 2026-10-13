"""Invariant 1: the YAML config is the one truth; every number is sourced."""
import glob
import math

import pytest

from arraytx.config import (ArrayConfig, config_from_dict, default_config,
                            form_fields, load_config)

CONFIGS = sorted(glob.glob("configs/*.yaml"))


def test_all_shipped_configs_load():
    assert len(CONFIGS) >= 4
    for p in CONFIGS:
        cfg = load_config(p)
        assert isinstance(cfg, ArrayConfig)
        assert cfg.source_path == p


def test_unknown_key_rejected():
    with pytest.raises(ValueError, match="unknown key"):
        config_from_dict({"array": {"n_element": 4}})


def test_bad_choice_rejected():
    with pytest.raises(ValueError, match="not in"):
        config_from_dict({"coupling": {"source": "guess"}})


def test_type_coercion_and_inf():
    cfg = config_from_dict({"coupling": {"scale_db": "-inf"}, "array": {"n_elements": 2}})
    assert cfg.coupling.scale_db == -math.inf
    with pytest.raises(ValueError):
        config_from_dict({"array": {"n_elements": 2.5}})
    with pytest.raises(ValueError):
        config_from_dict({"sim": {"noise": "yes"}})


def test_survey_numbers_must_carry_a_written_provenance():
    """A bare scalar in the survey block does not load; survey needs a
    citation; an honest assumed/derived label with a note is allowed."""
    with pytest.raises(ValueError, match="coupling.survey"):
        config_from_dict({"coupling": {"survey": {"c1_db": -15.0}}})
    with pytest.raises(ValueError, match="coupling.survey"):
        config_from_dict({"coupling": {"survey": {"c1_db": {"value": -15.0, "source": "survey"}}}})
    cfg = config_from_dict({"coupling": {"survey": {"c1_db": {"value": -15.0, "source": "survey", "ref": "paper X"}}}})
    assert cfg.provenance["coupling.survey.c1_db"].ref == "paper X"
    cfg = config_from_dict({"coupling": {"survey": {"c1_deg_at_f0": {"value": 90.0, "source": "assumed", "ref": "why"}}}})
    assert cfg.provenance["coupling.survey.c1_deg_at_f0"].source == "assumed"
    with pytest.raises(ValueError, match="needs a ref"):
        config_from_dict({"coupling": {"survey": {"c1_deg_at_f0": {"value": 90.0, "source": "assumed"}}}})


def test_all_numbers_sourced_in_shipped_configs():
    """Every numeric leaf in every shipped config has a provenance entry, and
    the survey block never says anything but survey."""
    for p in CONFIGS:
        cfg = load_config(p)
        for ff in form_fields():
            v = _get(cfg, ff.path)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                assert ff.path in cfg.provenance, (p, ff.path)
                src = cfg.provenance[ff.path].source
                assert src in ("survey", "derived", "assumed", "measured"), (p, ff.path, src)
                if ff.path.startswith("coupling.survey."):
                    assert cfg.provenance[ff.path].ref, (p, ff.path)
                    if src == "assumed":
                        assert cfg.provenance[ff.path].ref.startswith("assumed"), (p, ff.path)


def test_form_fields_cover_every_leaf_with_help_and_unit_keys():
    ffs = form_fields()
    paths = [f.path for f in ffs]
    assert len(paths) == len(set(paths))
    assert "coupling.source" in paths and "dpd.gmp.order" in paths and "beam.scan_deg" in paths
    for f in ffs:
        assert f.help, f.path
        if f.choices is not None:
            assert f.default in f.choices, f.path


def test_default_matches_shipped_default_config():
    """The dataclass defaults and configs/fr2_4el_survey.yaml agree, so there
    is no second set of defaults hiding in code (invariant 1)."""
    d = default_config().to_dict()
    y = load_config("configs/fr2_4el_survey.yaml").to_dict()
    assert d == y


def test_touchstone_requires_path():
    with pytest.raises(ValueError, match="touchstone"):
        config_from_dict({"coupling": {"source": "touchstone"}})


def _get(obj, path):
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def test_shipped_survey_refs_equal_declared_refs():
    """The YAML carries the citations (it is the truth); the dataclass carries
    the same text so a config that omits the block still loads sourced.  The
    two must not diverge."""
    cfg = load_config("configs/fr2_4el_survey.yaml")
    for ff in form_fields():
        if ff.path.startswith("coupling.survey.") and ff.source:
            assert cfg.provenance[ff.path].ref == ff.ref, ff.path


def test_list_defaults_are_not_shared_between_configs():
    a = default_config()
    a.beam.scan_deg.append(45.0)
    a.metrics.aclr_offsets[0] = 9
    b = default_config()
    assert b.beam.scan_deg == [0.0, 30.0, 60.0] and b.metrics.aclr_offsets == [1, 2]
    assert form_fields()[[f.path for f in form_fields()].index("beam.scan_deg")].default == [0.0, 30.0, 60.0]


def test_sidelobe_and_scan_deg_validation():
    cfg = config_from_dict({"beam": {"sidelobe": -45.0}})
    assert cfg.beam.sidelobe == -45.0
    assert config_from_dict({"beam": {"sidelobe": "auto"}}).beam.sidelobe == "auto"
    with pytest.raises(ValueError, match="sidelobe"):
        config_from_dict({"beam": {"sidelobe": "left"}})
    with pytest.raises(ValueError, match="scan_deg"):
        config_from_dict({"beam": {"scan_deg": []}})
    with pytest.raises(ValueError, match="scan_deg"):
        config_from_dict({"beam": {"scan_deg": [0.0, 90.0]}})
