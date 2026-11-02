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
    # provenance pills come from the config: the survey number says survey
    assert page.evaluate("document.querySelector('.row[data-path=\"coupling.survey.c1_db\"] .pill').textContent") == "survey"
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
