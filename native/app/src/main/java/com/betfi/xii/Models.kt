package com.betfi.xii

import org.json.JSONArray
import org.json.JSONObject

/**
 * Typed views over the bridge's JSON payloads. The bridge computes
 * every number and every display string (the one-engine law + the
 * shell-parity rule: the UI adds no model math of its own); these
 * classes only carry what bridge.py already decided. org.json is
 * null-hostile, so every read goes through the opt* helpers below.
 */

fun JSONObject.s(key: String): String? =
    if (isNull(key)) null else optString(key).ifEmpty { null }

fun JSONObject.d(key: String): Double? =
    if (isNull(key)) null else optDouble(key)

fun JSONObject.i(key: String): Int? =
    if (isNull(key)) null else optInt(key)

fun JSONObject.b(key: String): Boolean = optBoolean(key, false)

fun JSONObject.o(key: String): JSONObject? =
    if (isNull(key)) null else optJSONObject(key)

fun JSONObject.a(key: String): JSONArray =
    if (isNull(key)) JSONArray() else optJSONArray(key) ?: JSONArray()

data class BetName(
    val headline: String,
    val market: String,
    val selection: String,
    val matchup: String,
    val slipLabel: String,
    val fdPath: String
) {
    companion object {
        fun from(o: JSONObject?): BetName = BetName(
            headline = o?.s("headline") ?: "",
            market = o?.s("market") ?: "",
            selection = o?.s("selection") ?: "",
            matchup = o?.s("matchup") ?: "",
            slipLabel = o?.s("slip_label") ?: "",
            fdPath = o?.s("fd_path") ?: ""
        )
    }
}

data class CardEntry(
    val idx: Int,
    val key: String,
    val market: JSONObject,
    val verdict: JSONObject,
    val edgePts: Double?,
    val term: String,
    val verdictReason: String?,
    val metal: String?,
    val grade: String?,
    val state: String?,
    val name: BetName,
    val rowHeadline: String,
    val rowEvent: String,
    val rowModel: String,
    val rowOdds: String,
    val rowEdge: String,
    val betNow: Boolean,
    val linkState: String,
    val betUrl: String?,
    val sport: String?,
    val marketTime: String?,
    val price: Int?,
    val p: Double?,
    val rank: Int? = null
) {
    companion object {
        fun from(o: JSONObject): CardEntry {
            val market = o.o("market") ?: JSONObject()
            val verdict = o.o("verdict") ?: JSONObject()
            val row = o.o("row") ?: JSONObject()
            return CardEntry(
                idx = o.i("idx") ?: -1,
                key = o.s("key") ?: "",
                market = market,
                verdict = verdict,
                edgePts = o.d("edge_pts"),
                term = o.s("term") ?: "",
                verdictReason = o.s("verdict_reason"),
                metal = o.s("metal"),
                grade = o.s("grade"),
                state = o.s("state"),
                name = BetName.from(o.o("name")),
                rowHeadline = row.s("headline") ?: "",
                rowEvent = row.s("event") ?: "",
                rowModel = row.s("model") ?: "—",
                rowOdds = row.s("odds") ?: "—",
                rowEdge = row.s("edge") ?: "—",
                betNow = o.b("bet_now"),
                linkState = o.s("link_state") ?: "predates-link-ids",
                betUrl = o.s("bet_url"),
                sport = market.s("sport"),
                marketTime = market.s("market_time"),
                price = market.i("price"),
                p = verdict.d("p"),
                rank = o.i("rank")
            )
        }

        fun list(arr: JSONArray): List<CardEntry> =
            (0 until arr.length()).map { from(arr.getJSONObject(it)) }
    }
}

data class Receipt(
    val markets: Int, val priced: Int, val unpriced: Int,
    val betNow: Int, val golden: Int, val flagged: Int
) {
    companion object {
        fun from(o: JSONObject?): Receipt? = o?.let {
            Receipt(
                markets = it.i("markets") ?: 0,
                priced = it.i("priced") ?: 0,
                unpriced = it.i("unpriced") ?: 0,
                betNow = it.i("bet_now") ?: 0,
                golden = it.i("golden") ?: 0,
                flagged = it.i("flagged") ?: 0
            )
        }
    }
}

data class BoardPayload(
    val scope: String,
    val pulledAt: String?,
    val source: String?,
    val verified: Boolean,
    val stamp: String?,
    val sports: JSONObject,
    val receipt: Receipt?,
    val recorderStatus: String?,
    val cards: List<CardEntry>
) {
    companion object {
        fun from(o: JSONObject): BoardPayload = BoardPayload(
            scope = o.s("scope") ?: "standing",
            pulledAt = o.s("pulled_at"),
            source = o.s("source"),
            verified = o.b("verified"),
            stamp = o.s("stamp"),
            sports = o.o("sports") ?: JSONObject(),
            receipt = Receipt.from(o.o("receipt")),
            recorderStatus = o.o("recorder")?.s("status"),
            cards = CardEntry.list(o.a("cards"))
        )
    }
}

data class DepthSection(val title: String, val gloss: String,
                        val lines: List<String>) {
    companion object {
        fun list(arr: JSONArray): List<DepthSection> =
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                val lines = o.a("lines")
                DepthSection(
                    title = o.s("title") ?: "",
                    gloss = o.s("gloss") ?: "",
                    lines = (0 until lines.length()).map {
                        lines.optString(it)
                    }
                )
            }
    }
}

data class FindsPayload(
    val hasSlate: Boolean,
    val golden: List<CardEntry>,
    val finds: List<CardEntry>,
    val overflow: Int,
    val flagged: List<CardEntry>,
    val counter: List<String>
) {
    companion object {
        fun from(o: JSONObject): FindsPayload {
            val counter = o.a("counter")
            return FindsPayload(
                hasSlate = o.b("has_slate"),
                golden = CardEntry.list(o.a("golden")),
                finds = CardEntry.list(o.a("finds")),
                overflow = o.i("overflow") ?: 0,
                flagged = CardEntry.list(o.a("flagged")),
                counter = (0 until counter.length()).map {
                    counter.optString(it)
                }
            )
        }
    }
}

data class SlipLeg(
    val name: String, val term: String, val selection: String,
    val market: String, val matchup: String, val price: Int,
    val stakeUnits: Double, val stakeDollars: Double?,
    val stakeText: String
) {
    companion object {
        fun from(o: JSONObject): SlipLeg = SlipLeg(
            name = o.s("name") ?: "",
            term = o.s("term") ?: "",
            selection = o.s("selection") ?: "",
            market = o.s("market") ?: "",
            matchup = o.s("matchup") ?: "",
            price = o.i("price") ?: 0,
            stakeUnits = o.d("stake_units") ?: 0.0,
            stakeDollars = o.d("stake_dollars"),
            stakeText = o.s("stake_text") ?: ""
        )
    }
}

data class SlipCluster(val kind: String, val title: String,
                       val legs: List<String>, val note: String)

data class SlipPayload(
    val candidates: Int,
    val legs: List<SlipLeg>,
    val anyGolden: Boolean,
    val warnings: List<String>,
    val totalUnits: Double,
    val totalDollars: Double?,
    val combinedDecimal: Double?,
    val combinedAmerican: Int?,
    val combinedModelP: Double?,
    val clusters: List<SlipCluster>,
    val singles: List<String>,
    val pull: String?
) {
    companion object {
        fun from(o: JSONObject): SlipPayload {
            val warnings = o.a("warnings")
            val corr = o.o("correlation")
            val clusters = corr?.a("clusters") ?: JSONArray()
            val singles = corr?.a("singles") ?: JSONArray()
            return SlipPayload(
                candidates = o.i("candidates") ?: 0,
                legs = (0 until o.a("legs").length()).map {
                    SlipLeg.from(o.a("legs").getJSONObject(it))
                },
                anyGolden = o.b("any_golden"),
                warnings = (0 until warnings.length()).map {
                    warnings.optString(it)
                },
                totalUnits = o.d("total_units") ?: 0.0,
                totalDollars = o.d("total_dollars"),
                combinedDecimal = o.d("combined_decimal"),
                combinedAmerican = o.i("combined_american"),
                combinedModelP = o.d("combined_model_p"),
                clusters = (0 until clusters.length()).map { i ->
                    val c = clusters.getJSONObject(i)
                    val legs = c.a("legs")
                    SlipCluster(
                        kind = c.s("kind") ?: "",
                        title = c.s("title") ?: "",
                        legs = (0 until legs.length()).map {
                            legs.optString(it)
                        },
                        note = c.s("note") ?: ""
                    )
                },
                singles = (0 until singles.length()).map {
                    singles.optString(it)
                },
                pull = o.s("pull")
            )
        }
    }
}

// ------------------------------------------------------------------
// Lab + parity shapes (appended during the Scare Bets v1.0.0
// unification pass — LabScreen was written against these types).
// Every field is read from bridge.lab_json's ACTUAL keys:
//   {engine: {engine_version, engine_file, data_dir,
//             init: {ok, data_dir, error}},
//    recorder: {recorded_session, last_stamp, last_error,
//               history_begins, health_line, records_on_file,
//               recorded_markets_on_file},
//    marked_slips: <int>,
//    slate: {pulled_at, stamp, markets, priced, golden, flagged,
//            cal_tags, stances} | null}
// ------------------------------------------------------------------

data class LabInfo(
    val engine: JSONObject,
    val pingError: String?,
    val recorder: JSONObject,
    val latestPull: JSONObject?,
    val markedSlips: Int
) {
    companion object {
        fun from(o: JSONObject): LabInfo {
            val engine = o.o("engine") ?: JSONObject()
            val init = engine.o("init")
            val pingError: String? = when {
                init == null -> null
                !init.isNull("error") ->
                    init.optString("error").ifEmpty { null }
                init.has("ok") && !init.optBoolean("ok") ->
                    "engine init did not complete"
                else -> null
            }
            return LabInfo(
                engine = engine,
                pingError = pingError,
                recorder = o.o("recorder") ?: JSONObject(),
                latestPull = o.o("slate"),
                markedSlips = o.i("marked_slips") ?: 0
            )
        }
    }
}

/** The Lab parity spike's result: one summary line (starting
 *  "PARITY: MATCH" / "PARITY: DIFF") plus the diff lines. */
data class ParityResult(
    val summary: String,
    val diffs: List<String>
) {
    fun allMatch(): Boolean = diffs.isEmpty()
}
