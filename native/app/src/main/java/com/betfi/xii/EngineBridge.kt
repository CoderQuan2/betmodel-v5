package com.betfi.xii

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import org.json.JSONObject

/**
 * The shell's only door to the embedded engine. All Python contact
 * goes through the `bridge` module (src/main/python/bridge.py), which
 * is the only adapter allowed to touch betmodel5.py. The engine file
 * itself is byte-identical to the shipping engine (one-engine law).
 *
 * Every function here blocks: call from a background thread.
 */
object EngineBridge {

    @Volatile
    private var initialized = false

    @Synchronized
    private fun ensureStarted(context: Context) {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(context.applicationContext))
        }
        if (!initialized) {
            // Seed + repoint the engine's data paths onto writable
            // app storage before the first run (bridge.init).
            bridgeModule().callAttr(
                "init",
                context.applicationContext.filesDir.absolutePath
            )
            initialized = true
        }
    }

    private fun bridgeModule(): PyObject =
        Python.getInstance().getModule("bridge")

    /** Engine identity: version, imported file, active data dir. */
    fun ping(context: Context): JSONObject {
        ensureStarted(context)
        return JSONObject(bridgeModule().callAttr("ping").toString())
    }

    /** slate JSON text -> verdicts JSON text (one verdict per market). */
    fun runSlateJson(context: Context, slateJson: String): String {
        ensureStarted(context)
        return bridgeModule().callAttr("run_slate_json", slateJson).toString()
    }
}
