package com.betfi.xii

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.time.Instant
import java.time.OffsetDateTime
import java.time.ZoneId

/**
 * Grand BetFi's one view model. Every engine number arrives from
 * bridge.py as JSON (the UI derives NOTHING about the model); the
 * only logic here is the shell's own: display filters/sorts (the
 * Flet board's apply_toggles + sort modes, ported), the auto-pull
 * gate (armed by a user pull, 240 s interval, ticks follow the
 * sport in front of the user), and destination state.
 *
 * THREADING LAW: every bridge call blocks on the embedded Python
 * interpreter, so every launch site below runs on
 * EngineBridge.PythonDispatcher — the one serialized Python
 * queue — never on the main thread.
 */
class AppViewModel(app: Application) : AndroidViewModel(app) {

    private val ctx get() = getApplication<Application>()

    // ---------------- Board ----------------
    val board = MutableStateFlow<BoardPayload?>(null)
    val boardBusy = MutableStateFlow(false)
    val boardStatus = MutableStateFlow("")
    val sportView = MutableStateFlow("all")
    val showMode = MutableStateFlow("all")
    val sortMode = MutableStateFlow("verdict")
    val searchText = MutableStateFlow("")
    val cardLimit = MutableStateFlow(CARD_PAGE)
    val chosenSport = MutableStateFlow("soccer")
    val expandedIdx = MutableStateFlow<Int?>(null)
    val depthCache =
        MutableStateFlow<Map<Int, List<DepthSection>>>(emptyMap())
    val depthBusyIdx = MutableStateFlow<Int?>(null)
    val bankrollText = MutableStateFlow("")

    // ---------------- Auto-pull ----------------
    val autoArmed = MutableStateFlow(false)

    @Volatile
    private var lastPullAtMs: Long = 0L

    // ---------------- Finds / Slip / Lab ----------------
    val finds = MutableStateFlow<FindsPayload?>(null)
    val slip = MutableStateFlow<SlipPayload?>(null)
    val slipConfirm = MutableStateFlow(false)
    val slipStatus = MutableStateFlow("")
    val markedCount = MutableStateFlow(0)
    val lab = MutableStateFlow<LabInfo?>(null)
    val parity = MutableStateFlow<ParityResult?>(null)
    val parityState = MutableStateFlow("idle")
    val spikeOutcome = MutableStateFlow<SpikeOutcome?>(null)
    val spikeRunning = MutableStateFlow(false)

    data class SpikeOutcome(
        val pingLine: String, val count: Int, val firstLine: String,
        val match: Boolean, val mismatches: Int,
        val firstMismatch: String?
    )

    // ---------------- Stocks ----------------
    val stocksBusy = MutableStateFlow(false)
    val stocksNote = MutableStateFlow("")
    val stocksSeg = MutableStateFlow("tape")
    val stockViews =
        MutableStateFlow<List<Pair<String, JSONObject>>>(emptyList())
    val stocksSym = MutableStateFlow<String?>(null)
    val stocksExpiry = MutableStateFlow<String?>(null)
    val optionsPayload = MutableStateFlow<JSONObject?>(null)
    val holdingsRows = MutableStateFlow<List<JSONObject>>(emptyList())
    val holdingNote = MutableStateFlow("")

    // ---------------- 3D ----------------
    val panelTime = MutableStateFlow("live")
    val historyBegins = MutableStateFlow<String?>(null)

    fun bankroll(): Double? =
        bankrollText.value.trim().toDoubleOrNull()
            ?.takeIf { it > 0 }

    // ---------------- Board actions ----------------

    fun loadInitial() {
        if (board.value != null) return
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val payload = BoardPayload.from(
                    EngineBridge.currentBoard(ctx))
                board.value = payload
                if (payload.receipt != null) {
                    boardStatus.value = standingLine(payload)
                }
                refreshDerived()
            } catch (e: Exception) {
                boardStatus.value = "Engine error — " +
                    "${e.javaClass.simpleName}: ${e.message}"
            }
        }
    }

    private fun standingLine(p: BoardPayload): String {
        val r = p.receipt ?: return ""
        return "Standing pull ${p.pulledAt ?: "—"} · " +
            "${r.markets} markets · ${r.priced} priced · " +
            "${r.golden} golden"
    }

    fun pullFull() = pull("[]", manual = true)

    fun pullScoped(sport: String) =
        pull("[\"$sport\"]", manual = true)

    private fun pull(sportsJson: String, manual: Boolean) {
        if (boardBusy.value) return
        boardBusy.value = true
        boardStatus.value = "Pulling the FanDuel menu…"
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val payload = BoardPayload.from(
                    EngineBridge.buildAndRun(ctx, sportsJson))
                board.value = payload
                depthCache.value = emptyMap()
                expandedIdx.value = null
                cardLimit.value = CARD_PAGE
                lastPullAtMs = System.currentTimeMillis()
                if (manual) autoArmed.value = true
                boardStatus.value = receiptLine(payload)
                refreshDerived()
            } catch (e: Exception) {
                boardStatus.value = "Pull failed on this device: " +
                    "${e.javaClass.simpleName}: ${e.message}"
            } finally {
                boardBusy.value = false
            }
        }
    }

    /** The Flet pull receipt: per-sport market counts, failed
     * scopes named UNVERIFIED — never silently dropped. */
    private fun receiptLine(p: BoardPayload): String {
        val r = p.receipt ?: return standingLine(p)
        val per = StringBuilder()
        val failed = mutableListOf<String>()
        val keys = p.sports.keys()
        while (keys.hasNext()) {
            val sport = keys.next()
            val entry = p.sports.optJSONObject(sport) ?: continue
            if (entry.has("error")) failed.add(sport)
            else {
                if (per.isNotEmpty()) per.append(", ")
                per.append("$sport: " +
                    "${entry.optInt("slate_markets", 0)} markets")
            }
        }
        var line = "Pulled ${r.markets} primary markets"
        if (per.isNotEmpty()) line += " ($per)"
        if (failed.isNotEmpty()) {
            line += " · UNVERIFIED scopes: ${failed.joinToString(", ")}"
        }
        if (p.recorderStatus != null) {
            line += " · history: ${p.recorderStatus}"
        }
        return line
    }

    /** The auto-pull tick (the Flet gate, ported): due only when
     * the session was armed by a user pull, no pull is running,
     * and a full interval passed since the last pull landed. A
     * tick loads ONE sport alone — the sport the board is showing
     * (a routed sport loads its host page), else the chooser's. */
    fun autoTick() {
        if (!autoArmed.value || boardBusy.value) return
        if (System.currentTimeMillis() - lastPullAtMs
            < AUTO_PULL_INTERVAL_MS) return
        val view = sportView.value
        val sport = if (view != "all") {
            ROUTED_SPORT_HOST[view] ?: view
        } else {
            chosenSport.value
        }
        pull("[\"$sport\"]", manual = false)
    }

    fun toggleExpand(idx: Int) {
        if (expandedIdx.value == idx) {
            expandedIdx.value = null
            return
        }
        expandedIdx.value = idx
        if (depthCache.value.containsKey(idx)) return
        depthBusyIdx.value = idx
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.depth(ctx, idx, bankroll())
                depthCache.value = depthCache.value +
                    (idx to DepthSection.list(out.a("sections")))
            } catch (e: Exception) {
                depthCache.value = depthCache.value + (idx to listOf(
                    DepthSection("PRICE ANATOMY", "",
                        listOf("Depth failed on this device: " +
                            "${e.javaClass.simpleName}: " +
                            "${e.message}"))))
            } finally {
                depthBusyIdx.value = null
            }
        }
    }

    /** Finds + Slip + Lab read the same standing pull; refresh
     * them after every landed pull (never a re-price — the bridge
     * serves the cached pass). */
    private fun refreshDerived() {
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                finds.value = FindsPayload.from(
                    EngineBridge.finds(ctx))
            } catch (e: Exception) { /* surfaced on the Board */ }
        }
        refreshSlip()
        refreshLab()
    }

    fun refreshSlip() {
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                slip.value = SlipPayload.from(
                    EngineBridge.protectedSlip(ctx, bankroll()))
                markedCount.value =
                    EngineBridge.markedSlips(ctx).length()
                slipConfirm.value = false
            } catch (e: Exception) {
                slipStatus.value = "Slip failed: " +
                    "${e.javaClass.simpleName}: ${e.message}"
            }
        }
    }

    fun markPlaced() {
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.markPlaced(ctx, bankroll())
                if (out.has("error")) {
                    slipStatus.value = "Nothing to mark — the " +
                        "slip is empty."
                } else {
                    slipStatus.value = "Marked as placed — " +
                        "written to the Pilot Book as PLACED " +
                        "(user-marked). The app placed nothing."
                    markedCount.value = out.optInt("count",
                        markedCount.value)
                }
                slipConfirm.value = false
            } catch (e: Exception) {
                slipStatus.value = "Mark failed: " +
                    "${e.javaClass.simpleName}: ${e.message}"
            }
        }
    }

    fun refreshLab() {
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.lab(ctx)
                lab.value = LabInfo.from(out)
                historyBegins.value =
                    out.o("recorder")?.s("history_begins")
            } catch (e: Exception) { /* Lab shows its empty state */ }
        }
    }

    /** The Phase 1 parity spike (kept working; the Lab hosts it):
     * run the embedded engine over the bundled sample and compare
     * against the desktop reference, field by field. */
    fun runSpike() {
        if (spikeRunning.value) return
        spikeRunning.value = true
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val ping = EngineBridge.ping(ctx)
                val slateJson = ctx.assets.open("sample_slate.json")
                    .bufferedReader().use { it.readText() }
                val verdictsJson =
                    EngineBridge.runSlateJson(ctx, slateJson)
                val got = org.json.JSONArray(verdictsJson)
                val ref = org.json.JSONArray(
                    ctx.assets.open("reference_verdicts.json")
                        .bufferedReader().use { it.readText() })
                val result = Parity.compare(got, ref)
                val first = got.getJSONObject(0)
                val firstLine = listOf(
                    first.optString("desc"),
                    first.optString("state"),
                    "grade ${first.optString("grade")}",
                    first.optString("verdict"),
                    "P ${first.optDouble("p")}",
                    "bet_now ${first.optBoolean("bet_now")}"
                ).joinToString(" · ")
                spikeOutcome.value = SpikeOutcome(
                    pingLine = "betmodel v" +
                        ping.optString("engine_version") +
                        " · data: " + ping.optString("data_dir"),
                    count = got.length(),
                    firstLine = firstLine,
                    match = result.match,
                    mismatches = result.mismatches,
                    firstMismatch = result.firstMismatch
                )
            } catch (e: Exception) {
                spikeOutcome.value = SpikeOutcome(
                    pingLine = "engine error",
                    count = 0,
                    firstLine = "${e.javaClass.simpleName}: " +
                        "${e.message}",
                    match = false, mismatches = -1,
                    firstMismatch = null
                )
            } finally {
                spikeRunning.value = false
            }
        }
    }

    /** The Lab screen's parity entry point (same Phase 1 spike
     *  as runSpike, reported in the Lab's ParityResult shape:
     *  a summary line plus the diff list, allMatch when empty). */
    fun runParity() {
        if (parityState.value == "running") return
        parityState.value = "running"
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                EngineBridge.ping(ctx)
                val slateJson = ctx.assets.open("sample_slate.json")
                    .bufferedReader().use { it.readText() }
                val verdictsJson =
                    EngineBridge.runSlateJson(ctx, slateJson)
                val got = org.json.JSONArray(verdictsJson)
                val ref = org.json.JSONArray(
                    ctx.assets.open("reference_verdicts.json")
                        .bufferedReader().use { it.readText() })
                val result = Parity.compare(got, ref)
                val diffs = mutableListOf<String>()
                if (!result.match) {
                    result.firstMismatch?.let { diffs.add(it) }
                    if (result.gotCount != result.refCount) {
                        diffs.add(
                            "count mismatch: device " +
                                "${result.gotCount} vs reference " +
                                "${result.refCount}")
                    }
                }
                parity.value = ParityResult(
                    summary = if (result.match) {
                        "PARITY: MATCH — ${result.gotCount} " +
                            "verdicts, 0 mismatched fields"
                    } else {
                        "PARITY: DIFF — ${result.gotCount} device " +
                            "vs ${result.refCount} reference " +
                            "verdicts · mismatched fields: " +
                            "${result.mismatches}"
                    },
                    diffs = diffs
                )
            } catch (e: Exception) {
                parity.value = ParityResult(
                    summary = "PARITY: ERROR",
                    diffs = listOf(
                        "${e.javaClass.simpleName}: ${e.message}")
                )
            } finally {
                parityState.value = "done"
            }
        }
    }

    // ---------------- Stocks actions ----------------

    fun pullStocks() {
        if (stocksBusy.value) return
        stocksBusy.value = true
        stocksNote.value = "Pulling stocks — Nasdaq API…"
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.stocksPull(ctx)
                stocksNote.value = out.s("note") ?: ""
                applyTape(out.a("tape"))
                loadOptions()
                loadHoldings()
            } catch (e: Exception) {
                stocksNote.value = "Stocks pull failed on this " +
                    "device: ${e.javaClass.simpleName}: ${e.message}"
            } finally {
                stocksBusy.value = false
            }
        }
    }

    fun loadTape() {
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.stocksTape(ctx)
                stocksNote.value = out.s("note") ?: stocksNote.value
                applyTape(out.a("names"))
            } catch (e: Exception) { /* empty state covers it */ }
        }
    }

    private fun applyTape(arr: org.json.JSONArray) {
        val rows = mutableListOf<Pair<String, JSONObject>>()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val sym = o.s("symbol") ?: continue
            val view = o.o("view") ?: continue
            rows.add(sym to view)
        }
        stockViews.value = rows
        if (stocksSym.value == null && rows.isNotEmpty()) {
            stocksSym.value = rows.first().first
        }
    }

    fun loadOptions() {
        val sym = stocksSym.value ?: return
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                optionsPayload.value = EngineBridge.stocksOptions(
                    ctx, sym, stocksExpiry.value)
                val exp = optionsPayload.value?.s("expiry")
                if (exp != null) stocksExpiry.value = exp
            } catch (e: Exception) {
                optionsPayload.value = JSONObject(
                    mapOf("error" to "engine_error",
                        "symbol" to sym))
            }
        }
    }

    fun chooseStockSymbol(sym: String) {
        stocksSym.value = sym
        stocksExpiry.value = null
        loadOptions()
    }

    fun chooseStockExpiry(expiry: String) {
        stocksExpiry.value = expiry
        loadOptions()
    }

    fun loadHoldings() {
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.holdings(ctx)
                val arr = out.a("holdings")
                holdingsRows.value =
                    (0 until arr.length()).map {
                        arr.getJSONObject(it)
                    }
            } catch (e: Exception) { /* rows stay empty */ }
        }
    }

    fun saveHolding(sym: String, sharesText: String,
                    costText: String) {
        val shares = sharesText.trim().toDoubleOrNull()
        val cost = costText.trim().toDoubleOrNull()
        viewModelScope.launch(EngineBridge.PythonDispatcher) {
            try {
                val out = EngineBridge.setHolding(
                    ctx, sym, shares, cost)
                holdingNote.value = out.s("note") ?: ""
                loadHoldings()
            } catch (e: Exception) {
                holdingNote.value = "Save failed: " +
                    "${e.javaClass.simpleName}: ${e.message}"
            }
        }
    }


    companion object {
        const val CARD_PAGE = 40
        const val AUTO_PULL_INTERVAL_MS = 240_000L
        val ROUTED_SPORT_HOST = mapOf("ncaaf" to "nfl")
    }
}

// ---------------- Board display logic (Flet ports) --------------

val SHOW_MODES = listOf(
    "all" to "All markets",
    "priced" to "Priced only",
    "golden" to "Golden bets",
    "silver" to "Silver bets",
    "steel" to "Steel bets",
    "quick" to "Quick bets (≤2h)",
    "nodnb" to "No do-not-bets"
)

val SORT_MODES = listOf(
    "verdict" to "Bets first — verdict ladder",
    "edge" to "Top gain — edge (pts)",
    "no-bet-first" to "Do not bets first",
    "grade" to "Grade — A to F",
    "probability" to "Highest probability",
    "time" to "Kickoff time",
    "resolve" to "Resolve date",
    "pull" to "Pull order"
)

private val GRADE_ORDER = listOf(
    "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D",
    "D-", "F"
)

fun verdictRankOf(term: String): Int {
    val ladder = listOf("GOLDEN BET", "BET HERE", "RISK BET (BET)",
        "RISK BET (DO NOT BET)", "DO NOT BET")
    val mapped = when (term) {
        "Bet" -> "BET HERE"
        "No Bet" -> "DO NOT BET"
        else -> term
    }
    val i = ladder.indexOf(mapped)
    return if (i >= 0) i else ladder.size
}

fun gradeRankOf(grade: String?): Int {
    val i = GRADE_ORDER.indexOf(grade)
    return if (i >= 0) i else GRADE_ORDER.size
}

/** ISO stamp -> epoch ms, tolerant of offsets and naive stamps. */
fun parseStampMs(raw: String?): Long? {
    if (raw.isNullOrEmpty()) return null
    val s = raw.trim()
    return try {
        OffsetDateTime.parse(s).toInstant().toEpochMilli()
    } catch (e: Exception) {
        try {
            Instant.parse(s).toEpochMilli()
        } catch (e2: Exception) {
            try {
                java.time.LocalDateTime.parse(s)
                    .atZone(ZoneId.systemDefault())
                    .toInstant().toEpochMilli()
            } catch (e3: Exception) {
                null
            }
        }
    }
}

/** Quick bet (main.py is_quick): resolves within −1h…+2h of the
 * pull's own clock. */
fun isQuick(card: CardEntry, anchorMs: Long?): Boolean {
    val dt = parseStampMs(card.marketTime) ?: return false
    val anchor = anchorMs ?: return false
    val deltaS = (dt - anchor) / 1000
    return deltaS in -3600..7200
}

fun searchHit(card: CardEntry, query: String): Boolean {
    if (query.isBlank()) return true
    val q = query.lowercase()
    val hay = listOf(
        card.name.selection, card.name.market, card.name.matchup,
        card.name.headline, card.sport ?: "",
        card.market.optString("desc"),
        card.verdict.optString("desc")
    ).joinToString(" ").lowercase()
    return q in hay
}

/** The board's view filters (main.py apply_toggles): display
 * only, never a re-price. */
fun applyShow(cards: List<CardEntry>, sportView: String,
              show: String, search: String,
              anchorMs: Long?): List<CardEntry> {
    return cards.filter { c ->
        when (show) {
            "priced" -> c.state == "PRICED"
            "golden" -> c.term == "GOLDEN BET"
            "silver" -> c.metal == "SILVER"
            "steel" -> c.metal == "STEEL"
            "nodnb" -> c.term != "DO NOT BET"
            "quick" -> isQuick(c, anchorMs)
            else -> true
        } && (sportView == "all" || c.sport == sportView)
            && searchHit(c, search)
    }
}

fun applySort(cards: List<CardEntry>, mode: String): List<CardEntry> {
    return when (mode) {
        "edge" -> cards.sortedWith(
            compareByDescending { it.edgePts ?: -1e9 })
        "no-bet-first" -> cards.sortedWith(
            compareBy<CardEntry> {
                if (it.term == "DO NOT BET") 0 else 1
            }.thenBy { verdictRankOf(it.term) }
                .thenByDescending { it.edgePts ?: -1e9 })
        "grade" -> cards.sortedWith(
            compareBy<CardEntry> { gradeRankOf(it.grade) }
                .thenByDescending { it.edgePts ?: -1e9 })
        "probability" -> cards.sortedWith(
            compareByDescending { it.p ?: -1.0 })
        "time" -> cards.sortedWith(
            compareBy<CardEntry> { it.marketTime ?: "9999" }
                .thenBy { it.name.matchup })
        "resolve" -> cards.sortedWith(
            compareBy<CardEntry> {
                parseStampMs(it.marketTime) ?: Long.MAX_VALUE
            }.thenBy { it.name.matchup })
        "pull" -> cards.sortedBy { it.idx }
        else -> cards.sortedWith( // "verdict": ladder, then edge
            compareBy<CardEntry> { verdictRankOf(it.term) }
                .thenByDescending { it.edgePts ?: -1e9 })
    }
}
