package com.betfi.xii

import android.app.Application
import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.asCoroutineDispatcher
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Application entry that hands the app context to EngineBridge
 * before any screen runs, so the bridge's no-Context entry points
 * can start Python on first use. Registered as
 * android:name=".BetFiApp" in the manifest. (The Context-taking
 * entry points also attach, so this is a belt to their braces.)
 */
class BetFiApp : Application() {
    override fun onCreate() {
        super.onCreate()
        EngineBridge.attach(applicationContext)
    }
}

/**
 * The shell's only door to the embedded engine. All Python contact
 * goes through the `bridge` module (src/main/python/bridge.py), which
 * is the only adapter allowed to touch betmodel5.py. The engine file
 * itself is byte-identical to the shipping engine (one-engine law).
 *
 * Every function here blocks: call from a background thread —
 * [PythonDispatcher] (a dedicated single thread, so Python calls
 * never interleave) or Dispatchers.IO.
 *
 * CONCURRENCY NOTE (2026-10-31): two Kotlin variants were authored
 * against this bridge in parallel — one Context-first (matching the
 * Phase 0/1 scaffold's ping/runSlateJson style), one Context-free
 * (context attached once via BetFiApp). This file deliberately
 * serves BOTH call shapes as overloads/aliases over one private
 * implementation, so either shell compiles against it. The bridge
 * functions behind them are identical.
 *
 * Bridge function map (bridge.py — read here, never edited):
 *   ping / runSlateJson    -> ping / run_slate_json   (scaffold, exact)
 *   currentBoard           -> current_board_json
 *   buildAndRun            -> build_and_run
 *   depth                  -> depth_json_text    (text wrapper)
 *   finds                  -> finds_json
 *   slip / protectedSlip   -> slip_json_text     (text wrapper)
 *   markPlaced             -> mark_placed_text   (text wrapper)
 *   markedSlips            -> marked_slips_json
 *   lab                    -> lab_json
 *   slate / slateJsonBlocking -> slate_json
 *   history / historyJsonBlocking -> history_json
 *   spatial                -> spatial_json
 *   stocksPull             -> stocks_pull_json
 *   stocksTape             -> stocks_tape_json
 *   stocksOptions          -> stocks_options_json
 *   holdings / stocksHoldings -> holdings_json
 *   setHolding             -> set_holding_text_json (text wrapper)
 *
 * Bankroll / holding arguments: the shells carry these as USER
 * TEXT in every version of this app, and bridge.py's text wrappers
 * parse them with main.py's own rule (blank or invalid -> None).
 * The Double? overloads therefore convert back to text
 * (null -> "") and go through the same wrappers — one parse rule,
 * no second Kotlin-side parser with its own edge cases.
 */
object EngineBridge {

    /** Dedicated single-thread dispatcher for Python calls: the
     *  bridge keeps standing state (the slate, verdicts, stocks),
     *  so calls must serialize. */
    val PythonDispatcher: CoroutineDispatcher =
        Executors.newSingleThreadExecutor { r ->
            Thread(r, "grand-betfi-python").apply { isDaemon = true }
        }.asCoroutineDispatcher()

    @Volatile
    private var initialized = false

    @Volatile
    private var appContext: Context? = null

    /** Store the application context (BetFiApp, and every
     *  Context-taking entry point below). */
    fun attach(context: Context) {
        appContext = context.applicationContext
    }

    @Synchronized
    private fun ensureStarted(context: Context) {
        attach(context)
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

    @Synchronized
    private fun ensureStarted() {
        val ctx = appContext
            ?: throw IllegalStateException(
                "EngineBridge not attached — BetFiApp.onCreate " +
                    "did not run, and no Context entry point was " +
                    "called first"
            )
        ensureStarted(ctx)
    }

    private fun bridgeModule(): PyObject =
        Python.getInstance().getModule("bridge")

    private fun callText(name: String, vararg args: Any?): String {
        ensureStarted()
        return bridgeModule().callAttr(name, *args).toString()
    }

    private fun callTextCtx(
        context: Context, name: String, vararg args: Any?
    ): String {
        ensureStarted(context)
        return bridgeModule().callAttr(name, *args).toString()
    }

    private fun textOf(v: Double?): String = v?.toString() ?: ""

    // ---- engine identity / parity path (scaffold, kept exact) ----

    /** Engine identity: version, imported file, active data dir. */
    fun ping(context: Context): JSONObject {
        ensureStarted(context)
        return JSONObject(bridgeModule().callAttr("ping").toString())
    }

    /** Engine identity via the attached application context. */
    fun ping(): JSONObject = JSONObject(callText("ping"))

    /** slate JSON text -> verdicts JSON text (one verdict per market). */
    fun runSlateJson(context: Context, slateJson: String): String {
        ensureStarted(context)
        return bridgeModule().callAttr("run_slate_json", slateJson).toString()
    }

    // ---- board ----------------------------------------------------

    /** Board payload for the standing slate, without pulling
     *  (bridge.current_board_json). */
    fun currentBoard(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "current_board_json"))

    fun currentBoard(): JSONObject =
        JSONObject(callText("current_board_json"))

    /** Pull + price + record. [sportsJsonArray] is a JSON array
     *  string: "[]" = full pull, "[\"nfl\"]" = scoped pull of one
     *  sport (bridge.build_and_run). Returns the board payload. */
    fun buildAndRun(context: Context, sportsJsonArray: String): JSONObject =
        JSONObject(callTextCtx(context, "build_and_run", sportsJsonArray))

    fun buildAndRun(sportsJsonArray: String): JSONObject =
        JSONObject(callText("build_and_run", sportsJsonArray))

    // ---- card depth -----------------------------------------------

    /** The five depth sections for one card, bankroll as a parsed
     *  Double? (bridge.depth_json_text via its text form). */
    fun depth(context: Context, idx: Int, bankroll: Double?): JSONObject =
        JSONObject(
            callTextCtx(context, "depth_json_text", idx, textOf(bankroll))
        )

    /** The five depth sections for one card, bankroll as user
     *  text (bridge.depth_json_text). */
    fun depth(idx: Int, bankrollText: String): JSONObject =
        JSONObject(callText("depth_json_text", idx, bankrollText))

    // ---- finds ------------------------------------------------------

    /** GOLDEN panel + ranked finds + flagged + counter lines
     *  (bridge.finds_json). */
    fun finds(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "finds_json"))

    fun finds(): JSONObject = JSONObject(callText("finds_json"))

    // ---- protected slip ---------------------------------------------

    /** The Protected Slip for a parsed bankroll
     *  (bridge.slip_json_text via its text form). */
    fun protectedSlip(context: Context, bankroll: Double?): JSONObject =
        JSONObject(callTextCtx(context, "slip_json_text", textOf(bankroll)))

    /** The Protected Slip for a bankroll text
     *  (bridge.slip_json_text). */
    fun slip(bankrollText: String): JSONObject =
        JSONObject(callText("slip_json_text", bankrollText))

    /** Alias of [slip] under the bridge's own name for the slip. */
    fun protectedSlip(bankrollText: String): JSONObject = slip(bankrollText)

    /** Write the user's own placement mark — call ONLY after the
     *  confirm step (bridge.mark_placed_text via its text form). */
    fun markPlaced(context: Context, bankroll: Double?): JSONObject =
        JSONObject(callTextCtx(context, "mark_placed_text", textOf(bankroll)))

    /** Write the user's own placement mark from bankroll text
     *  (bridge.mark_placed_text). */
    fun markPlaced(bankrollText: String): JSONObject =
        JSONObject(callText("mark_placed_text", bankrollText))

    /** All marked slips on this device (bridge.marked_slips_json
     *  returns a JSON array). */
    fun markedSlips(context: Context): JSONArray =
        JSONArray(callTextCtx(context, "marked_slips_json"))

    fun markedSlips(): JSONArray = JSONArray(callText("marked_slips_json"))

    // ---- lab / slate / history --------------------------------------

    /** Lab payload: engine + recorder + standing slate summary +
     *  marked-slip count (bridge.lab_json). */
    fun lab(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "lab_json"))

    fun lab(): JSONObject = JSONObject(callText("lab_json"))

    /** Per-event summaries of the standing pull
     *  (bridge.slate_json). */
    fun slate(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "slate_json"))

    fun slate(): JSONObject = JSONObject(callText("slate_json"))

    /** Raw slate_json text (the instrument server's route body). */
    fun slateJsonBlocking(context: Context): String =
        callTextCtx(context, "slate_json")

    /** Raw history_json text (the instrument server's route body).
     *  A null eventId calls the two-argument bridge form so the
     *  Python default (None) applies — no null is marshalled. */
    fun historyJsonBlocking(
        context: Context, window: String, graph: String, eventId: String?
    ): String {
        ensureStarted(context)
        return if (eventId == null) {
            bridgeModule().callAttr("history_json", window, graph).toString()
        } else {
            bridgeModule().callAttr(
                "history_json", window, graph, eventId
            ).toString()
        }
    }

    /** One (window, graph) history payload (bridge.history_json). */
    fun history(window: String, graph: String, eventId: String?): JSONObject =
        JSONObject(historyText(window, graph, eventId))

    private fun historyText(
        window: String, graph: String, eventId: String?
    ): String {
        ensureStarted()
        return if (eventId == null) {
            bridgeModule().callAttr("history_json", window, graph).toString()
        } else {
            bridgeModule().callAttr(
                "history_json", window, graph, eventId
            ).toString()
        }
    }

    // ---- spatial (true 3D) --------------------------------------------

    /** True-3D spatial payload for a window ("live" | "month" |
     *  "season") (bridge.spatial_json). Axis mapping is stated in
     *  bridge.py and in SpatialRenderer.kt. */
    fun spatial(window: String): JSONObject =
        JSONObject(callText("spatial_json", window))

    fun spatial(context: Context, window: String): JSONObject =
        JSONObject(callTextCtx(context, "spatial_json", window))

    // ---- stocks ---------------------------------------------------------

    /** Pull every stock in the universe (bridge.stocks_pull_json).
     *  Returns {note, fresh, failed, tape}. */
    fun stocksPull(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "stocks_pull_json"))

    fun stocksPull(): JSONObject = JSONObject(callText("stocks_pull_json"))

    /** TAPE + MATRIX views (bridge.stocks_tape_json):
     *  {note, names: [{symbol, view}]}. */
    fun stocksTape(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "stocks_tape_json"))

    fun stocksTape(): JSONObject = JSONObject(callText("stocks_tape_json"))

    /** Options grid for one name/expiry (bridge.stocks_options_json).
     *  A null expiry calls the one-argument form so the bridge
     *  picks its default expiry. */
    fun stocksOptions(
        context: Context, sym: String, expiry: String?
    ): JSONObject = JSONObject(optionsTextCtx(context, sym, expiry))

    fun stocksOptions(sym: String, expiry: String?): JSONObject =
        JSONObject(optionsText(sym, expiry))

    private fun optionsTextCtx(
        context: Context, sym: String, expiry: String?
    ): String {
        ensureStarted(context)
        return if (expiry == null) {
            bridgeModule().callAttr("stocks_options_json", sym).toString()
        } else {
            bridgeModule().callAttr(
                "stocks_options_json", sym, expiry
            ).toString()
        }
    }

    private fun optionsText(sym: String, expiry: String?): String {
        ensureStarted()
        return if (expiry == null) {
            bridgeModule().callAttr("stocks_options_json", sym).toString()
        } else {
            bridgeModule().callAttr(
                "stocks_options_json", sym, expiry
            ).toString()
        }
    }

    /** Holdings rows for the whole universe
     *  (bridge.holdings_json): {holdings: [...]}. */
    fun holdings(context: Context): JSONObject =
        JSONObject(callTextCtx(context, "holdings_json"))

    fun stocksHoldings(): JSONObject =
        JSONObject(callText("holdings_json"))

    /** Alias of [stocksHoldings] under the bridge's surface name. */
    fun holdings(): JSONObject = stocksHoldings()

    /** Save/clear one holding from parsed values
     *  (bridge.set_holding_text_json via its text form: a null
     *  value marshals as blank text, which the bridge's own parse
     *  rule reads as None — both blank clears, one blank is the
     *  bridge's half-entry rejection). */
    fun setHolding(
        context: Context, sym: String, shares: Double?, cost: Double?
    ): JSONObject = JSONObject(
        callTextCtx(
            context, "set_holding_text_json",
            sym, textOf(shares), textOf(cost)
        )
    )

    /** Save/clear one holding from the user's field texts
     *  (bridge.set_holding_text_json). */
    fun setHolding(
        sym: String, sharesText: String, costText: String
    ): JSONObject = JSONObject(
        callText("set_holding_text_json", sym, sharesText, costText)
    )
}
