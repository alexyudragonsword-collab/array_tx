"""The local host: the API the page speaks, jobs in child processes with
progress and cancel, the POST header, no files outside www, and the
desktop lifecycle (closing the app window stops the server)."""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from arraytx import load_config
from arraytx import webhost
from arraytx.guispec import values_from_config

ROOT = Path(__file__).resolve().parent.parent
SMOKE_SYMBOLS = 2


@pytest.fixture(scope="module")
def server():
    srv = webhost.make_server(0, cfg=load_config(ROOT / "configs" / "fr2_4el_survey.yaml"), workers=1)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()
    srv.server_close()


def _get(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_code": e.code, **json.loads(e.read())}


def _post(url: str, payload: dict, header: bool = True) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **({webhost.POST_HEADER: "1"} if header else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_code": e.code, **json.loads(e.read())}


def _wait(server: str, jid: str, timeout: float = 240.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = _get(server + f"api/jobs/{jid}")["job"]
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.2)
    raise TimeoutError(jid)


def test_version_spec_and_config(server):
    v = _get(server + "api/version")
    assert v["lib"] == "arraytx" and v["pins"]["polar_tx"] == "b007e60" and v["workers"] == 1
    s = _get(server + "api/spec")
    assert s["ok"] and len(s["controls"]) >= 50 and s["schemes"] == ["none", "per_element", "array"]
    c = _get(server + "api/config")
    assert c["source_path"].endswith("fr2_4el_survey.yaml") and c["values"]["coupling.source"] == "survey"
    want = load_config("configs/fr2_4el_survey.yaml").provenance["coupling.survey.c1_db"]          # the config's own label
    got = c["provenance"]["coupling.survey.c1_db"]
    assert (got["source"], got["ref"]) == (want.source, want.ref) and "arraytx_config" in c["yaml"]


def test_validate_reports_the_diff_and_refuses_bad_values(server):
    cfg = load_config(ROOT / "configs" / "fr2_4el_survey.yaml")
    vals = values_from_config(cfg)
    vals["array.n_elements"] = 8
    v = _post(server + "api/validate", {"values": vals})
    assert v["ok"] and v["diff"] == [{"path": "array.n_elements", "a": 4, "b": 8}] and "n_elements: 8" in v["yaml"]
    vals["dpd.scheme"] = "magic"
    bad = _post(server + "api/validate", {"values": vals})
    assert bad["ok"] is False and "dpd.scheme" in bad["error"] and bad["_code"] == 400
    assert _post(server + "api/validate", {"values": {}}, header=False)["_code"] == 403
    assert _post(server + "api/nope", {})["_code"] == 404


def test_run_job_returns_the_report(server):
    cfg = load_config(ROOT / "configs" / "fr2_4el_survey.yaml")
    j = _post(server + "api/run", {"values": values_from_config(cfg), "theta0_deg": 30, "scheme": "none",
                                   "n_symbols": SMOKE_SYMBOLS})
    assert j["ok"] and j["job"]["status"] in ("queued", "running") and j["job"]["label"].startswith("+30°")
    done = _wait(server, j["job"]["id"])
    assert done["status"] == "done", done.get("error")
    rep = done["rows"][0]
    assert rep["ota"]["beam"]["domain"] == "ota" and rep["plots"]["direction"]["beam_deg"] == 30.0
    assert rep["info"]["n_symbols"] == SMOKE_SYMBOLS and "线性化引擎" in rep["engine_line"]
    assert done["config_sha256"] == rep["repro"]["config_sha256"]
    listing = _get(server + "api/jobs")["jobs"]
    assert any(x["id"] == done["id"] and "rows" not in x and x["n_rows"] == 1 for x in listing)


def test_zero_coupling_report_serialises_and_rows_can_be_fetched_from_an_index(server):
    """coupling.scale_db = -inf (the sweep placeholder's own first value)
    puts coupling_max_offdiag_db = -inf in the report; the host must still
    answer every job GET with JSON (json refuses non-finite floats), and the
    page's poll fetches only the rows it has not seen."""
    cfg = load_config(ROOT / "configs" / "fr2_4el_survey.yaml")
    vals = {**values_from_config(cfg), "coupling.scale_db": "-inf"}
    j = _post(server + "api/run", {"values": vals, "theta0_deg": 0, "scheme": "none", "n_symbols": SMOKE_SYMBOLS})
    assert j["ok"], j
    done = _wait(server, j["job"]["id"])
    assert done["status"] == "done", done.get("error")
    assert done["rows"][0]["info"]["coupling_max_offdiag_db"] == "-inf" and done["rows_from"] == 0
    assert webhost.dumps({"a": float("nan"), "b": float("inf"), "c": [1.5, float("-inf")]}) == '{"a": "nan", "b": "inf", "c": [1.5, "-inf"]}'
    tail = _get(server + f"api/jobs/{done['id']}/rows/1")["job"]
    assert tail["rows"] == [] and tail["rows_from"] == 1 and tail["n_rows"] == 1
    assert _get(server + f"api/jobs/{done['id']}/rows/0")["job"]["rows"] == done["rows"]
    assert _get(server + f"api/jobs/{done['id']}/nope")["_code"] == 404


def test_scan_job_streams_rows_and_can_be_cancelled(server):
    cfg = load_config(ROOT / "configs" / "fr2_4el_survey.yaml")
    vals = values_from_config(cfg)
    j = _post(server + "api/scan", {"values": vals, "scan_deg": [0, 30], "schemes": ["none", "array"],
                                    "n_symbols": SMOKE_SYMBOLS})["job"]
    assert j["progress"] == [0, 4]
    done = _wait(server, j["id"])
    assert done["status"] == "done" and done["progress"] == [4, 4] and len(done["rows"]) == 4
    assert [(r["theta0_deg"], r["scheme"]) for r in done["rows"]] == [(0.0, "none"), (0.0, "array"), (30.0, "none"), (30.0, "array")]
    assert done["summary"]["scan_deg"] == [0.0, 30.0]
    # cancel: a long scan is stopped, whatever rows landed stay
    big = _post(server + "api/scan", {"values": vals, "scan_deg": [0, 10, 20, 30, 40, 50, 60], "schemes": ["array"],
                                      "n_symbols": SMOKE_SYMBOLS})["job"]
    time.sleep(1.0)
    assert _post(server + f"api/jobs/{big['id']}/cancel", {})["ok"]
    c = _wait(server, big["id"], timeout=60)
    assert c["status"] == "cancelled" and len(c["rows"]) < 7
    assert _post(server + f"api/jobs/{big['id']}/cancel", {})["ok"] is False
    assert _get(server + "api/jobs/999")["ok"] is False


def test_sweep_job_runs_one_leaf_over_points_and_validates_first(server):
    cfg = load_config(ROOT / "configs" / "fr2_4el_survey.yaml")
    vals = values_from_config(cfg)
    bad = _post(server + "api/sweep", {"values": vals, "path": "dpd.scheme", "points": ["none", "magic"], "n_symbols": SMOKE_SYMBOLS})
    assert bad["ok"] is False and "dpd.scheme" in bad["error"]          # every point is validated before anything runs
    assert _post(server + "api/sweep", {"values": vals, "path": "nope.leaf", "points": [1]})["ok"] is False
    assert _post(server + "api/sweep", {"values": vals, "path": "array.n_elements", "points": [2], "group_path": "array.n_elements",
                                        "group_values": [4]})["ok"] is False                    # group must be another leaf
    assert _post(server + "api/sweep", {"values": vals, "path": "array.n_elements", "points": [2], "group_path": "beam.steering",
                                        "group_values": []})["ok"] is False
    g = _post(server + "api/sweep", {"values": vals, "path": "array.n_elements", "points": [2], "group_path": "beam.steering",
                                     "group_values": ["phase", "ttd"], "theta0_deg": 60, "scheme": "none", "n_symbols": SMOKE_SYMBOLS})["job"]
    assert g["progress"] == [0, 2] and "⊗" in g["label"]
    gd = _wait(server, g["id"])
    assert [r["sweep"]["group_value"] for r in gd["rows"]] == ["phase", "ttd"] and gd["summary"]["group_path"] == "beam.steering"
    j = _post(server + "api/sweep", {"values": vals, "path": "array.n_elements", "points": [2, 4], "theta0_deg": 60,
                                     "scheme": "none", "n_symbols": SMOKE_SYMBOLS})["job"]
    assert j["kind"] == "sweep" and j["progress"] == [0, 2] and "n_elements" in j["label"]
    done = _wait(server, j["id"])
    assert done["status"] == "done" and [r["sweep"]["value"] for r in done["rows"]] == [2, 4]
    assert done["rows"][0]["info"]["n_elements"] == 2 and done["summary"]["path"] == "array.n_elements"


def test_config_text_and_save_round_trip(server, tmp_path):
    cfg = load_config(ROOT / "configs" / "fr2_4el_analytic.yaml")
    c = _post(server + "api/config/text", {"yaml": (ROOT / "configs" / "fr2_4el_analytic.yaml").read_text(encoding="utf-8")})
    assert c["ok"] and c["values"]["coupling.source"] == "analytic"
    vals = c["values"]
    vals["seed"] = 7
    out = tmp_path / "saved.yaml"
    s = _post(server + "api/save", {"values": vals, "path": str(out)})
    assert s["ok"] and s["source_path"] == str(out) and load_config(out).seed == 7
    back = _post(server + "api/config/load", {"path": str(ROOT / "configs" / "fr2_4el_survey.yaml")})
    assert back["ok"] and back["values"]["seed"] == cfg.seed == 1


def test_host_serves_nothing_outside_www(server):
    for path in ("../webhost.py", "..%2Fwebhost.py", "../../../pyproject.toml"):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(server + path, timeout=10)
        assert e.value.code == 404


# ------------------------------------------------------------ lifecycle
_FAKE_BROWSER = r"""
import json, sys, urllib.request
url, out = sys.argv[1], sys.argv[2]
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
ver = json.loads(op.open(url + "api/version", timeout=60).read())
open(out, "w").write(json.dumps({"lib": ver["lib"]}))
"""


def test_closing_the_window_stops_the_server(monkeypatch, tmp_path):
    out = tmp_path / "seen.json"
    monkeypatch.setattr(webhost, "find_app_browser", lambda: sys.executable)
    monkeypatch.setattr(webhost, "app_window_command", lambda b, url, p: [b, "-c", _FAKE_BROWSER, url, str(out)])
    monkeypatch.setattr(webhost, "HANDOFF_S", 0.0)
    monkeypatch.delenv("ARRAYTX_NO_BROWSER", raising=False)
    box: dict = {}

    def target():
        try:
            webhost.main(["--port", "0", "--workers", "1"])
        except BaseException as exc:            # noqa: BLE001
            box["exc"] = exc
    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(90)
    assert not th.is_alive() and "exc" not in box
    assert json.loads(out.read_text())["lib"] == "arraytx"


def test_app_window_is_chromeless_on_its_own_profile_and_the_browser_can_be_overridden(monkeypatch):
    cmd = webhost.app_window_command("edge", "http://127.0.0.1:1/", Path("p"))
    assert "--app=http://127.0.0.1:1/" in cmd and f"--user-data-dir={Path('p')}" in cmd
    monkeypatch.setenv("ARRAYTX_BROWSER", "/somewhere/chromium")
    assert webhost.find_app_browser() == "/somewhere/chromium"
