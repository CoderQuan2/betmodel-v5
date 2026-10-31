package com.betfi.xii

import org.json.JSONArray
import org.json.JSONObject
import kotlin.math.abs
import kotlin.math.max

/**
 * The canonical parity comparison (defined in native/PARITY.md):
 *
 *  - Key:        sport|market|desc, taken from the verdict itself.
 *  - Ordering:   both sides sorted by key before comparing.
 *  - Counts:     must be equal.
 *  - Discrete fields (string / boolean / null): exactly equal.
 *  - Numeric fields: |a-b| <= 1e-9 * max(1, |a|, |b|) — JSON doubles
 *    round-trip exactly through Python's json and org.json, so this
 *    tolerance is a guard band, not an expectation of drift. The
 *    desktop proof of this same path is exact (zero tolerance).
 */
object Parity {

    data class Result(
        val match: Boolean,
        val gotCount: Int,
        val refCount: Int,
        val mismatches: Int,
        val firstMismatch: String?
    )

    fun keyOf(v: JSONObject): String =
        "${v.optString("sport")}|${v.optString("market")}|${v.optString("desc")}"

    fun compare(got: JSONArray, ref: JSONArray): Result {
        val g = byKey(got)
        val r = byKey(ref)
        if (g.size != r.size) {
            return Result(
                false, g.size, r.size, -1,
                "count mismatch: device ${g.size} vs reference ${r.size}"
            )
        }
        var mismatches = 0
        var first: String? = null
        for ((key, gv) in g) {
            val rv = r[key]
            if (rv == null) {
                mismatches++
                if (first == null) first = "$key: missing from reference"
                continue
            }
            val fields = sortedSetOf<String>()
            gv.keys().forEach { fields.add(it) }
            rv.keys().forEach { fields.add(it) }
            for (f in fields) {
                val a = if (gv.has(f)) gv.get(f) else JSONObject.NULL
                val b = if (rv.has(f)) rv.get(f) else JSONObject.NULL
                if (!fieldEqual(a, b)) {
                    mismatches++
                    if (first == null) first = "$key :: $f: device=$a reference=$b"
                }
            }
        }
        return Result(mismatches == 0, g.size, r.size, mismatches, first)
    }

    private fun byKey(arr: JSONArray): Map<String, JSONObject> {
        val out = sortedMapOf<String, JSONObject>()
        for (i in 0 until arr.length()) {
            val v = arr.getJSONObject(i)
            out[keyOf(v)] = v
        }
        return out
    }

    private fun fieldEqual(a: Any, b: Any): Boolean {
        if (a === JSONObject.NULL || b === JSONObject.NULL) return a === b
        if (a is Number && b is Number) {
            val x = a.toDouble()
            val y = b.toDouble()
            return abs(x - y) <= 1e-9 * max(1.0, max(abs(x), abs(y)))
        }
        return a == b
    }
}
