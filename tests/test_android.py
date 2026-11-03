"""The Android shell, checked from text: no permissions, the activity calls
the module that exists, the Gradle assets path is the page, and the page's
bilingual markup follows the rule the WebView taught polar_tx (a data-zh
element must not wrap another element: textContent replaces children)."""
import re
from pathlib import Path

from arraytx.webhost import WWW

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "android"


def test_manifest_asks_for_no_permission():
    m = (ANDROID / "app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    assert "<uses-permission" not in m
    assert 'android:name=".MainActivity"' in m


def test_activity_calls_the_bridge_that_exists_and_gradle_bundles_the_page():
    kt = (ANDROID / "app/src/main/java/com/arraytx/app/MainActivity.kt").read_text(encoding="utf-8")
    assert 'getModule("arraytx.appbridge")' in kt and 'callAttr("call"' in kt
    assert "window.onHostReply" in kt and 'addJavascriptInterface(HostBridge(), "host")' in kt
    import arraytx.appbridge as ab
    assert callable(ab.call)
    gradle = (ANDROID / "app/build.gradle.kts").read_text(encoding="utf-8")
    assets = re.search(r'assets\.setSrcDirs\(listOf\("([^"]+)"\)\)', gradle).group(1)
    assert (ANDROID / "app" / assets).resolve() == WWW.parent.resolve()
    assert 'version = "3.10"' in gradle and 'install("pyyaml")' in gradle
    for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
        assert (ANDROID / f"app/src/main/res/mipmap-{density}/ic_launcher.png").is_file()


def test_page_speaks_the_bridge_and_bilingual_markup_wraps_no_controls():
    js = (WWW / "app.js").read_text(encoding="utf-8")
    assert "window.onHostReply" in js and "window.host.call(id, route" in js
    html = (WWW / "index.html").read_text(encoding="utf-8")
    # a [data-zh] element's content is replaced by textContent on every
    # language switch; one that wraps an <input>/<select>/<button> would
    # delete that control from the DOM
    for m in re.finditer(r"<(\w+)([^>]*\bdata-zh=[^>]*)>(.*?)</\1>", html, flags=re.S):
        inner = m.group(3)
        assert "<" not in inner, f"data-zh element wraps markup: {m.group(0)[:80]}"
    assert html.count("data-zh=") == html.count("data-en=") >= 20
