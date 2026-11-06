"""The GUI contract (guispec): every control is a YAML leaf, defaults are
read not typed, values round-trip through the same loader a file uses, and
the YAML the page writes loads back with its provenance intact."""
import yaml

from arraytx import load_config
from arraytx.config import config_from_dict, default_config, form_fields
from arraytx.guispec import (GROUPS, HIDDEN, METRICS, PLOTS, controls, diff, spec, to_yaml,
                             values_from_config, values_to_config)


def test_every_control_is_a_config_leaf_and_every_leaf_is_a_control_or_hidden():
    paths = {ff.path for ff in form_fields()}
    ctl = {c.path for c in controls()}
    assert ctl <= paths
    assert paths - ctl == set(HIDDEN)
    assert all(c.group in GROUPS for c in controls())
    kinds = {c.kind for c in controls()}
    assert kinds <= {"int", "float", "bool", "choice", "text", "list", "path", "optional_float"}


def test_defaults_are_read_from_the_config_never_typed():
    d = values_from_config(default_config())
    for c in controls():
        assert c.default == d[c.path], c.path
    # and the default form builds the default config, leaf for leaf
    built = values_to_config({c.path: c.default for c in controls()})
    assert diff(built, default_config()) == []


def test_choices_come_from_the_library():
    by = {c.path: c for c in controls()}
    assert set(by["dpd.scheme"].choices) == {"none", "per_element", "array"}
    assert by["element.lo.clock_profile"].kind == "choice" and None in by["element.lo.clock_profile"].choices
    assert any(str(x).startswith("bundled:") for x in by["element.lo.clock_profile"].choices)
    assert by["coupling.survey.c1_db"].source == "assumed" and "arXiv" in (by["coupling.survey.c1_db"].ref or "")
    assert by["coupling.survey.c1_db"].visible_when == ("coupling.source", ("survey",))


def test_spec_is_json_ready_and_declares_the_domains():
    import json
    s = spec()
    json.dumps(s)                       # no numpy, no dataclasses
    assert {m["domain"] for m in METRICS.values()} == {"ota", "info", "diagnostic"}
    assert all(k.startswith("conducted_") for k, m in METRICS.items() if m["domain"] == "diagnostic")
    assert [p["id"] for p in PLOTS] == ["direction", "spectrum", "constellation"]
    assert len(s["controls"]) == len(controls()) and s["schemes"] == ["none", "per_element", "array"]


def test_values_round_trip_and_keep_provenance():
    cfg = load_config("configs/fr2_4el_survey.yaml")
    flat = values_from_config(cfg)
    back = values_to_config(flat, cfg)
    assert diff(cfg, back) == []
    assert back.provenance["coupling.survey.c1_db"].ref == cfg.provenance["coupling.survey.c1_db"].ref
    # an edited survey number is no longer a citation
    flat["coupling.survey.c1_db"] = -18.0
    edited = values_to_config(flat, cfg)
    s = edited.provenance["coupling.survey.c1_db"]
    assert edited.coupling.survey.c1_db == -18.0 and s.source == "assumed" and "edited in the GUI" in s.ref
    assert diff(cfg, edited) == [{"path": "coupling.survey.c1_db", "a": -16.0, "b": -18.0}]


def test_yaml_written_by_the_page_loads_back_the_same(tmp_path):
    cfg = load_config("configs/fr2_4el_survey.yaml")
    text = to_yaml(cfg)
    p = tmp_path / "out.yaml"
    p.write_text(text, encoding="utf-8")
    back = load_config(p)
    assert diff(cfg, back) == []
    assert {k: (v.source, v.ref) for k, v in back.provenance.items()} == \
           {k: (v.source, v.ref) for k, v in cfg.provenance.items()}
    data = yaml.safe_load(text)
    assert isinstance(data["coupling"]["survey"]["c1_db"], dict)       # written in {value, source, ref} form
    assert data["coupling"]["survey"]["c1_db"]["source"] == "assumed"
    assert not isinstance(data["array"]["n_elements"], dict)           # a design choice stays a bare scalar
    assert diff(config_from_dict(data), cfg) == []
