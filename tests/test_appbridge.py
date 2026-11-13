"""The Android bridge: the same Api as the local server, through one string
-> string function, with jobs on threads.  Runs on a laptop in seconds;
this is what makes the phone's surface a tested one."""
import json
import time

import pytest

from arraytx import appbridge
from arraytx.webhost import Api, JobQueue, State
from arraytx.config import default_config, load_config
from arraytx.guispec import values_from_config

SMOKE_SYMBOLS = 2


@pytest.fixture(autouse=True)
def fresh_bridge(tmp_path, monkeypatch):
    monkeypatch.setenv("ARRAYTX_HOME", str(tmp_path))
    appbridge.reset()
    yield
    appbridge.reset()


def _call(route, args=None):
    return json.loads(appbridge.call(route, json.dumps(args or {})))


def _wait(jid, timeout=240.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = _call(f"jobs/{jid}")["job"]
        if j["status"] in ("done", "error", "cancelled"):
            return j
        time.sleep(0.2)
    raise TimeoutError(jid)


def test_envelope_never_raises():
    assert _call("version")["lib"] == "arraytx" and _call("version")["workers"] == 1
    assert _call("spec")["schemes"] == ["none", "per_element", "array"]
    bad = _call("nope")
    assert bad["ok"] is False and "no such route" in bad["error"]
    garbled = json.loads(appbridge.call("validate", "{not json"))
    assert garbled["ok"] is False and "JSONDecodeError" in garbled["error"]
    notobj = json.loads(appbridge.call("validate", "[1, 2]"))
    assert notobj["ok"] is False
    assert _call("validate", {"values": {"dpd.scheme": "magic"}})["ok"] is False


def test_a_run_on_the_thread_backend_lands_the_same_report(tmp_path):
    cfg = load_config("configs/fr2_4el_survey.yaml")
    vals = values_from_config(cfg)
    j = _call("run", {"values": vals, "theta0_deg": 30, "scheme": "none", "n_symbols": SMOKE_SYMBOLS})["job"]
    done = _wait(j["id"])
    assert done["status"] == "done" and done["rows"][0]["ota"]["beam"]["domain"] == "ota"
    assert "不能背书" in done["rows"][0]["engine_line"]
    # the phone writes YAML under its own directory (relative paths land in ARRAYTX_HOME)
    saved = _call("save", {"values": vals, "path": "mine.yaml"})
    assert saved["ok"] and (tmp_path / "mine.yaml").exists() and saved["source_path"] == str(tmp_path / "mine.yaml")
    back = _call("config/load", {"path": "mine.yaml"})
    assert back["ok"] and back["values"]["coupling.source"] == "survey"


def test_thread_backend_cancels_between_rows_and_reports_errors():
    q = JobQueue(workers=1, backend="thread")
    cfg = load_config("configs/fr2_4el_survey.yaml")
    angles = [float(a) for a in range(-80, 81, 8)]                        # 21 rows: no runner finishes them before the cancel
    job = q.submit("scan", cfg, {"scan_deg": angles, "schemes": ["none"], "n_symbols": SMOKE_SYMBOLS}, "x")
    t0 = time.time()
    while q.get(job["id"])["n_rows"] < 1 and time.time() - t0 < 120:       # cancel as soon as the first row has landed
        time.sleep(0.05)
    assert q.cancel(job["id"])
    t0 = time.time()
    while q.get(job["id"])["status"] == "running" and time.time() - t0 < 120:
        time.sleep(0.2)
    j = q.get(job["id"])
    assert j["status"] == "cancelled" and 0 < len(j["rows"]) < len(angles)    # stopped after the row that was running
    bad = q.submit("sweep", cfg, {"path": "array.n_elements", "points": [0], "n_symbols": SMOKE_SYMBOLS}, "y")
    t0 = time.time()
    while q.get(bad["id"])["status"] in ("queued", "running") and time.time() - t0 < 60:
        time.sleep(0.2)
    assert q.get(bad["id"])["status"] == "error" and "n_elements" in q.get(bad["id"])["error"]
    with pytest.raises(ValueError):
        JobQueue(backend="fork")


def test_api_dispatch_is_the_one_the_server_uses():
    api = Api(State(default_config(), 1, backend="thread"))
    assert api.call("version")[0] == 200 and api.call("jobs/42")[0] == 404 and api.call("nope")[0] == 404
    code, obj = api.call("validate", {"values": {"array.n_elements": -1}})
    assert code == 400 and obj["ok"] is False
    assert set(Api.GET_ROUTES) == {"version", "spec", "config", "jobs"}


def test_the_backoff_rule_study_runs_through_the_bridge():
    cfg = load_config("configs/fr2_4el_survey.yaml")
    vals = values_from_config(cfg)
    vals["element.pa.load_pull.enabled"] = True
    j = _call("rule", {"values": vals, "scan_deg": [0, 60], "backoffs": [0, 2], "aclr_target_dbc": -45, "evm_target_db": -25,
                       "margin_db": 0.3, "n_symbols": SMOKE_SYMBOLS})["job"]
    assert j["kind"] == "rule" and j["progress"] == [0, 4]
    done = _wait(j["id"])
    assert done["status"] == "done" and len(done["rows"]) == 4 and done["rows"][0]["sweep"]["path"] == "element.pa.backoff_db"
    s = done["summary"]
    assert [t["theta_deg"] for t in s["table"]] == [0.0, 60.0] and s["targets"]["source"] == "assumed"
    assert _call("rule", {"values": vals, "backoffs": [-1]})["ok"] is False
