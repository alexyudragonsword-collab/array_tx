package com.arraytx.app

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.system.Os
import android.webkit.JavascriptInterface
import android.webkit.JsPromptResult
import android.webkit.WebChromeClient
import android.webkit.WebView
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * A WebView shell around arraytx.appbridge (the pattern polar_tx's app uses).
 *
 * Deliberately inert: every feature is a Python function behind webhost.Api
 * plus a render in app.js.  If a change seems to need Kotlin, the logic
 * wanted to be in Python, where the test suite is.
 *
 * All Python runs on ONE background thread: arraytx is numpy/scipy code with
 * no locking, and the first call pays the import of numpy + scipy (seconds on
 * a phone).  Jobs themselves run on arraytx's own thread-backend queue, so a
 * call returns at once and the page polls /jobs as it does on the desktop.
 */
class MainActivity : Activity() {

    private val executor = Executors.newSingleThreadExecutor()
    private lateinit var web: WebView
    private var bridge: PyObject? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (!Python.isStarted()) {
            // matplotlib builds a font cache on first import and dies on a
            // read-only config dir; set BEFORE Python.start().  ARRAYTX_HOME is
            // where the bridge loads / saves YAML on the phone.
            val mpl = filesDir.resolve("mpl").apply { mkdirs() }
            val cache = filesDir.resolve("cache").apply { mkdirs() }
            val home = filesDir.resolve("arraytx").apply { mkdirs() }
            Os.setenv("MPLCONFIGDIR", mpl.path, true)
            Os.setenv("XDG_CACHE_HOME", cache.path, true)
            Os.setenv("ARRAYTX_HOME", home.path, true)
            Python.start(AndroidPlatform(this))
        }
        web = WebView(this)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true          // the page keeps its history in localStorage
        // the page's Open / Save use prompt(); a WebView ignores it without a
        // chrome client, so answer with the default text the page offers
        web.webChromeClient = object : WebChromeClient() {
            override fun onJsPrompt(view: WebView?, url: String?, message: String?,
                                    defaultValue: String?, result: JsPromptResult?): Boolean {
                result?.confirm(defaultValue ?: "")
                return true
            }
        }
        web.addJavascriptInterface(HostBridge(), "host")
        setContentView(web)
        web.loadUrl("file:///android_asset/www/index.html")
    }

    inner class HostBridge {
        /** Async RPC: returns immediately, the reply lands via window.onHostReply. */
        @JavascriptInterface
        fun call(id: String, route: String, argsJson: String) {
            executor.execute {
                val reply = try {
                    val py = bridge ?: Python.getInstance()
                        .getModule("arraytx.appbridge").also { bridge = it }
                    py.callAttr("call", route, argsJson).toString()
                } catch (e: Exception) {
                    JSONObject().put("ok", false).put("error", e.toString()).toString()
                }
                runOnUiThread {
                    web.evaluateJavascript(
                        "window.onHostReply(${JSONObject.quote(id)},${JSONObject.quote(reply)})", null)
                }
            }
        }
    }
}
