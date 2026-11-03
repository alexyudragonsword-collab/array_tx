"""guiutil arranges ArraySim's numbers for a renderer: every metric in a
report equals the ArraySim result it came from, the plots carry what the
examples draw, and the diagnostic rows are labelled as such."""
import json

import numpy as np

from arraytx import ArraySim, load_config
from arraytx.guispec import spec
from arraytx.guiutil import config_sha, pins, run_report, scan_report, yaml_text


def test_report_carries_the_efficiency_number_from_the_sim():
    rep = run_report(load_config("configs/fr2_4el_survey.yaml"), 0.0, "none", n_symbols=2, with_plots=False)
    assert 20.0 < rep["info"]["eta_avg_pct"] < 80.0 and rep["info"]["backoff_db"] == 0.0
    assert "eta_avg_pct" in spec()["metrics"] and spec()["metrics"]["eta_avg_pct"]["domain"] == "info"


def test_run_report_equals_the_arraysim_result_item_for_item(fr2_sim):
    r = fr2_sim.run(30.0, "none")
    rep = run_report(fr2_sim.cfg, 30.0, "none")
    json.dumps(rep)                                            # JSON-ready
    b = rep["ota"]["beam"]
    assert b["domain"] == "ota" and b["evm_db"] == r.beam.evm_db and b["aclr1_dbc"] == r.beam.aclr1_db
    assert b["sem_margin_db"] == r.beam.sem["worst_margin_db"] and b["sem_source"] == "stylized"
    assert rep["ota"]["sidelobe"]["theta_deg"] == r.sidelobe_deg
    assert b["evm_per_tone_db"] < b["evm_db"]                   # per-tone EQ removes the linear part
    d = rep["diagnostic"]
    assert len(d) == fr2_sim.geom.n and d[0]["conducted_evm_db"] == r.conducted[0].evm_db
    assert all(k.startswith("conducted_") for k in d[0] if k not in ("element", "errors"))
    assert "线性化引擎" in rep["engine_line"] and rep["engine_modes"] == ["dtc_openloop"]
    assert rep["info"]["n_elements"] == 4 and abs(rep["info"]["squint_deg"]) < 0.3
    assert rep["repro"]["seed"] == 1 and len(rep["repro"]["config_sha256"]) == 64
    assert rep["repro"]["pins"] == {"polar_tx": "008cc90", "PA_DPD": "08b9725", "pll_simulator": "00e48a2"}
    assert "sim.run(theta0_deg=30.0, scheme='none')" in rep["repro"]["call"]


def test_report_plots_carry_what_the_examples_draw(fr2_sim):
    rep = run_report(fr2_sim.cfg, 30.0, "none")
    p = rep["plots"]
    d = p["direction"]
    assert len(d["theta_deg"]) == 181 and d["theta_deg"][0] == -90.0 and d["beam_deg"] == 30.0
    assert any(v is None for v in d["aclr1_dbc"]) and max(d["pattern_db"]) == 0.0      # nulls greyed, peak at 0 dB
    i = d["theta_deg"].index(30.0)
    assert abs(d["aclr1_dbc"][i] - rep["ota"]["beam"]["aclr1_dbc"]) < 1.5             # 1 deg grid vs exact beam
    s = p["spectrum"]
    assert len(s["f_mhz"]) == len(s["psd_db"]) == len(s["mask_db"]) and s["mask_source"] == "stylized"
    assert not s["mask_is_conformance"] and s["bw_mhz"] == 400.0
    c = p["constellation"]
    assert len(c["i"]) == len(c["q"]) <= 4000 and c["qam"] == 64
    assert 0.5 < np.std(c["i"]) < 2.0                                               # unit-ish QAM after the scalar EQ


def test_scan_report_runs_one_sim_and_streams_rows(fr2_sim):
    seen = []
    rep = scan_report(fr2_sim.cfg, [0.0, 30.0], ["none", "array"], with_plots=False,
                      progress=lambda i, n, row: seen.append((i, n, row["theta0_deg"], row["scheme"])))
    assert seen == [(1, 4, 0.0, "none"), (2, 4, 0.0, "array"), (3, 4, 30.0, "none"), (4, 4, 30.0, "array")]
    assert [r["theta0_deg"] for r in rep["rows"]] == [0.0, 0.0, 30.0, 30.0] and "plots" not in rep["rows"][0]
    direct = fr2_sim.run(30.0, "array")
    assert rep["rows"][3]["ota"]["beam"]["aclr1_dbc"] == direct.beam.aclr1_db   # same sim, same draws, same number


def test_config_sha_follows_the_leaves_and_yaml_text_loads(tmp_path):
    a = load_config("configs/fr2_4el_survey.yaml")
    b = load_config("configs/fr2_4el_analytic.yaml")
    assert config_sha(a) != config_sha(b) and config_sha(a) == config_sha(load_config("configs/fr2_4el_survey.yaml"))
    p = tmp_path / "c.yaml"
    p.write_text(yaml_text(a), encoding="utf-8")
    assert config_sha(load_config(p)) == config_sha(a)
    assert set(pins()) == {"polar_tx", "PA_DPD", "pll_simulator"}
    assert isinstance(ArraySim(a).cfg.seed, int)


def test_direction_scan_equals_the_exact_far_field_path(fr2_sim):
    """The page's ACLR-vs-direction curve is Welch on segment-combined
    element signals; the exact path synthesises the far field per
    direction.  Same ACLR to 0.05 dB, same pattern to 0.05 dB, 8x faster."""
    from arraytx.guiutil import direction_scan
    from arraytx.metrics import aclr1_vs_direction, power_vs_direction_db
    r = fr2_sim.run(30.0, "none")
    th = np.arange(-90.0, 91.0, 3.0)
    a, p = direction_scan(fr2_sim, r.rs, th)
    e = fr2_sim.far_field_many(r.rs, th)
    a0, p0 = aclr1_vs_direction(e, fr2_sim.wf, th), power_vs_direction_db(e)
    assert np.abs(a - a0).max() < 0.05
    assert np.abs((p - p.max()) - (p0 - p0.max())).max() < 0.05
    assert abs(a[np.argmin(np.abs(th - 30.0))] - r.beam.aclr1_db) < 0.05


def test_sweep_report_changes_one_leaf_and_keeps_the_rest(fr2_sim):
    """A sweep point is the config with one leaf changed through
    values_to_config: the n=4 point of an element-count sweep equals the
    plain run, and a spurs on/off sweep over a profile with no spurs is a
    pair of identical rows (the switch is drawn-then-zeroed either way)."""
    from arraytx.guiutil import sweep_report
    rep = sweep_report(fr2_sim.cfg, "array.n_elements", [2, 4], 60.0, "none", with_plots=False)
    assert [r["sweep"]["value"] for r in rep["rows"]] == [2, 4] and rep["path"] == "array.n_elements"
    assert rep["rows"][1]["ota"]["beam"]["aclr1_dbc"] == fr2_sim.run(60.0, "none").beam.aclr1_db
    assert rep["rows"][0]["info"]["n_elements"] == 2
    off_on = sweep_report(fr2_sim.cfg, "element.lo.spurs", [False, True], 30.0, "none", with_plots=False)
    a, b = (r["ota"]["beam"]["evm_db"] for r in off_on["rows"])
    assert a == b                                      # the preset LO has no spur table: nothing to inject


def test_sweep_report_groups_by_a_second_leaf(fr2_sim):
    """ex06's two lines on the page: the same points once per value of a
    second leaf; the group runs in order and each row names its group."""
    from arraytx.guiutil import sweep_report
    rep = sweep_report(fr2_sim.cfg, "array.n_elements", [2, 4], 60.0, "none", with_plots=False,
                       group_path="beam.steering", group_values=["phase", "ttd"])
    assert rep["group_values"] == ["phase", "ttd"] and len(rep["rows"]) == 4
    assert [(r["sweep"]["group_value"], r["sweep"]["value"]) for r in rep["rows"]] == [("phase", 2), ("phase", 4), ("ttd", 2), ("ttd", 4)]
    assert rep["rows"][3]["steering"] == "ttd" and rep["rows"][1]["steering"] == "phase"
    assert rep["rows"][0]["sweep"]["n_groups"] == 2
