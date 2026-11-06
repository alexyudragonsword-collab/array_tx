"""The page in a real Chromium against the real host: the form is built
from the spec, a run lands in the table / cards / plots, the engine line
and the diagnostic label are shown, a baseline gives deltas, the phone
layout switches panes.  Assertions are on wiring and physics labels, not
on pixels or snapshot numbers.

Needs Playwright and a Chromium: skips without them, except when
ARRAYTX_REQUIRE_BROWSER=1 (CI's test-gui job), where the skip is a failure
so a green run that tested nothing cannot pass for one that did.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

import pytest

from arraytx import load_config
from arraytx.webhost import POST_HEADER, WWW, make_server

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def server():
    srv = make_server(0, cfg=load_config(ROOT / "configs" / "fr2_4el_survey.yaml"), workers=1)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()
    srv.server_close()


def test_the_page_speaks_only_routes_the_host_answers():
    """Every api("...") in app.js is a route webhost serves, and every POST
    carries the header the host demands (the parity rule polar_tx keeps
    between its page and its bridge)."""
    js = (WWW / "app.js").read_text(encoding="utf-8")
    host = (ROOT / "src" / "arraytx" / "webhost.py").read_text(encoding="utf-8")
    routes = {r.strip("/") for r in re.findall(r'api\("([a-z/]+)"', js)}
    served = set(re.findall(r'route == "([a-z/]+)"', host)) | {"jobs", "spec", "config", "version"}
    assert routes <= served, routes - served
    assert POST_HEADER in js
    assert "线性化引擎" in (ROOT / "src" / "arraytx" / "report.py").read_text(encoding="utf-8")


def _browser():
    required = os.environ.get("ARRAYTX_REQUIRE_BROWSER") == "1"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if required:
            raise
        pytest.skip("playwright not installed")
    pw = sync_playwright().start()
    import glob
    # ARRAYTX_CHROMIUM, else Playwright's own download, else any Chromium under PLAYWRIGHT_BROWSERS_PATH
    exes = [os.environ.get("ARRAYTX_CHROMIUM"), None] + sorted(glob.glob(
        os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), "chromium-*", "chrome-linux", "chrome")))
    last = None
    for exe in exes:
        if exe == "" or (exe is None and exes[0]):
            continue
        try:
            b = pw.chromium.launch(executable_path=exe, args=["--no-sandbox"]) if exe else pw.chromium.launch(args=["--no-sandbox"])
            return pw, b
        except Exception as exc:                # noqa: BLE001 (try the next one)
            last = exc
    pw.stop()
    if required:
        raise RuntimeError(f"no Chromium: {last}")
    pytest.skip(f"no Chromium: {last}")


@pytest.fixture(scope="module")
def browser():
    pw, b = _browser()
    yield b
    b.close()
    pw.stop()


def test_form_is_the_spec_and_a_run_lands_everywhere(server, browser):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1&run=30,none")
    page.wait_for_selector("#form .row", timeout=30000)
    n_rows = page.evaluate("document.querySelectorAll('#form .row').length")
    n_spec = page.evaluate("fetch('api/spec').then(r => r.json()).then(s => s.controls.length)")
    assert n_rows == n_spec >= 50
    # provenance pills come from the config: the pill says what the config says
    want = load_config("configs/fr2_4el_survey.yaml").provenance["coupling.survey.c1_db"].source
    assert page.evaluate("document.querySelector('.row[data-path=\"coupling.survey.c1_db\"] .pill').textContent") == want
    # analytic rows are hidden while the source is survey
    assert page.evaluate("document.querySelector('.row[data-path=\"coupling.analytic.c1_db\"]').hidden") is True
    page.wait_for_function("document.querySelectorAll('#table tbody tr').length >= 1", timeout=180000)
    assert not errors, errors
    title = page.text_content("#res-title")
    assert "+30.0°" in title and "无 DPD" in title
    assert "线性化引擎" in page.text_content("#engine")
    cards = page.text_content("#cards")
    assert "EVM" in cards and "ACLR1" in cards and "OTA" in cards and "stylized" in cards
    assert "conducted_" in page.text_content("details.diag summary")          # the diagnostic is labelled, collapsed
    for pid in ("direction", "spectrum", "constellation"):
        assert page.evaluate(f"document.querySelector('#plot-{pid} svg') !== null"), pid
    assert "seed 1" in page.text_content("#repro") and "008cc90" in page.text_content("#repro")
    # a baseline gives deltas on the cards
    page.click("#btn-pin")
    page.click("#btn-run")
    page.wait_for_function("document.querySelectorAll('#table tbody tr').length >= 2", timeout=180000)
    assert "对基线" in page.text_content("#cards")
    # editing a survey number marks the form modified and the validate line reports the diff
    page.fill(".row[data-path=\"coupling.survey.c1_db\"] input", "-18")
    page.keyboard.press("Tab")
    page.wait_for_function("document.getElementById('validate').textContent.includes('1 处')", timeout=20000)
    assert "未保存" in page.text_content("#cfg-chip")
    assert page.evaluate("document.querySelector('.row[data-path=\"coupling.survey.c1_db\"] .pill').textContent") == "assumed"
    page.close()


def test_phone_layout_switches_panes(server, browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(server)
    page.wait_for_selector("#form .row", state="attached", timeout=30000)      # the config pane starts hidden here
    assert page.evaluate("getComputedStyle(document.getElementById('bottom-nav')).display") == "flex"
    assert page.evaluate("getComputedStyle(document.getElementById('config')).display") == "none"
    page.click("#bottom-nav button[data-pane='config']")
    assert page.evaluate("getComputedStyle(document.getElementById('config')).display") == "block"
    assert page.evaluate("getComputedStyle(document.getElementById('results')).display") == "none"
    page.close()


def test_a_sweep_draws_as_it_lands_and_history_survives_a_reload(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1&sweep=array.n_elements,2,4")
    # the host still holds the earlier tests' jobs, so wait for THIS sweep's last row, not a row count
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr')].some(tr => tr.textContent.includes('n_elements=4'))", timeout=240000)
    assert not errors, errors
    assert "n_elements" in page.text_content("#pt-grid") and page.evaluate("document.querySelector('#plot-grid svg circle') !== null")
    assert "array.n_elements=4" in page.text_content("#res-title")
    # a reload restores the stored reports; ones the host still holds are replaced by the live rows (no duplicates)
    page.goto(server)
    page.wait_for_selector("#form .row", timeout=30000)
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr')].some(tr => tr.textContent.includes('n_elements=4'))", timeout=15000)
    page.wait_for_timeout(800)
    assert "↺" not in page.text_content("#table tbody")
    assert page.evaluate("[...document.querySelectorAll('#table tbody tr')].filter(tr => tr.textContent.includes('n_elements=4')).length") == 1
    # a report from a host that is gone (another job id) comes back marked restored
    page.evaluate("""() => { const k = 'arraytx.reports.' + location.port; const a = JSON.parse(localStorage.getItem(k));
                          a.forEach(r => { r.jobId = '999'; r.key = '999.' + r.i; }); localStorage.setItem(k, JSON.stringify(a)); }""")
    page.goto(server)
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr td')].some(td => td.textContent.includes('↺'))", timeout=15000)
    ctx.close()


def test_grouped_study_and_the_language_toggle(server, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1&theta=60&sweep=array.n_elements,2,4&group=beam.steering,phase,ttd")
    # the shared host still holds earlier tests' sweeps: wait for THIS study's last group
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr')].filter(tr => tr.textContent.includes('steering=ttd')).length >= 2", timeout=300000)
    assert not errors, errors
    assert "⊗ beam.steering" in page.text_content("#pt-grid")
    assert page.evaluate("document.querySelectorAll('#plot-grid svg circle').length") >= 4          # two lines, two points each
    assert "beam.steering=ttd" in page.text_content("#res-title")
    # the language toggle relabels the static text and the rendered results, and survives a reload
    page.click("#lang")
    assert page.text_content("#btn-run").strip() == "▶ Run" and "no DPD" in page.text_content("#res-title")
    assert "Queue" in page.text_content("#side .pane-h")
    page.reload()
    page.wait_for_selector("#form .row", timeout=30000)
    assert page.text_content("#btn-run").strip() == "▶ Run"
    page.click("#lang")
    assert page.text_content("#btn-run").strip() == "▶ 运行"
    ctx.close()


def test_a_backoff_study_draws_against_drain_efficiency(server, browser):
    """ex10's trade on the page: element.pa.backoff_db x load pull on / off,
    drawn with the average drain efficiency (a number the report carries,
    not one the page computes) on the x axis."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1&theta=60&sweepx=eta&sweep=element.pa.backoff_db,0,3&group=element.pa.load_pull.enabled,false,true")
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr')].filter(tr => tr.textContent.includes('backoff_db=3') && tr.textContent.includes('enabled=true')).length >= 1", timeout=300000)
    page.wait_for_function("document.querySelector('#pt-grid').textContent.includes('4/4')", timeout=60000)
    assert not errors, errors
    assert page.input_value("#sweep-x") == "eta"
    assert "阵列漏极效率" in page.text_content("#plot-grid") and page.evaluate("document.querySelectorAll('#plot-grid svg circle').length") >= 4
    assert "阵列漏极效率" in page.text_content("#cards")
    page.select_option("#sweep-x", "value")
    assert "element.pa.backoff_db" in page.text_content("#plot-grid")
    ctx.close()


def test_the_efficiency_axis_falls_back_when_every_point_has_the_same_efficiency(server, browser):
    """The EVM equaliser does not touch the codes: both points have the same
    efficiency, so there is nothing to spread along x.  The study keeps its
    cell grid (two cells) instead of a zero-width line chart."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1&theta=30&sweepx=eta&sweep=metrics.evm_equalize,scalar,per_tone")
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr')].filter(tr => tr.textContent.includes('evm_equalize=per_tone')).length >= 1", timeout=300000)
    page.wait_for_function("document.querySelector('#pt-grid').textContent.includes('2/2')", timeout=60000)
    assert not errors, errors
    assert page.evaluate("document.querySelectorAll('#plot-grid svg rect').length") >= 2
    assert "NaN" not in page.inner_html("#plot-grid")
    ctx.close()


def test_the_page_works_through_an_injected_host_bridge(server, browser):
    """The Android path without Android: inject a window.host whose call()
    answers through the real Api (via the server) and replies by
    window.onHostReply, exactly as the WebView activity does.  The page must
    take that transport for every request."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    page = ctx.new_page()
    page.add_init_script("""
      window.host = { calls: 0, call(id, route, argsJson) {
        window.host.calls++;
        const isGet = ["version", "spec", "config", "jobs"].includes(route) || (route.startsWith("jobs/") && !route.endsWith("/cancel"));
        fetch("api/" + route, isGet ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-ArrayTX": "1" }, body: argsJson })
          .then(r => r.text()).then(t => window.onHostReply(id, t))
          .catch(e => window.onHostReply(id, JSON.stringify({ ok: false, error: String(e) })));
      } };
    """)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1&run=0,none")
    page.wait_for_function("[...document.querySelectorAll('#table tbody tr')].some(tr => tr.textContent.includes('0°'))", timeout=180000)
    assert not errors, errors
    assert page.evaluate("window.host.calls") >= 4                      # spec, config, validate, run, jobs...
    assert "线性化引擎" in page.text_content("#engine")
    ctx.close()


def test_the_backoff_rule_table_comes_from_the_job_summary(server, browser):
    """ex19 Part 1 on the page: load pull switched on in the form, angles
    from the form's beam.scan_deg, backoffs and targets typed in; the table
    under the study plot shows the summary's numbers (one row per angle)."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server + "?smoke=1")
    page.wait_for_selector("#form .row", timeout=30000)
    # the element group starts folded; the switch is a button
    page.evaluate("document.querySelector('.row[data-path=\"element.pa.load_pull.enabled\"]').closest('details').open = true")
    page.click('.row[data-path="element.pa.load_pull.enabled"] button.sw')
    page.wait_for_function("document.querySelector('.row[data-path=\"element.pa.load_pull.enabled\"] button.sw').classList.contains('on')")
    page.fill("#rule-backoffs", "0, 2")
    page.fill("#rule-targets", "-45, -25, 0.3")
    page.click("#btn-rule")
    page.wait_for_function("document.querySelectorAll('#rule-table tbody tr').length === 3", timeout=300000)
    assert not errors, errors
    txt = page.text_content("#rule-box")
    assert "assumed" in txt and "-45 dBc" in txt and "|1+Γ|" in txt
    first = page.text_content("#rule-table tbody tr:first-child td:nth-child(2)")
    assert first != "—" and 0.5 < float(first) < 1.5                      # |1+Γ| mean is there because load pull is on
    ctx.close()
