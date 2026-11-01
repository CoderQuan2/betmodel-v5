package com.betfi.xii

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject

/**
 * Stocks — the build-53 destination at full parity: TAPE (the
 * six names, live-pulled quotes shaped by the engine's
 * stock_quote_view), MATRIX (spot, realized vol, and the examined
 * lanes' verdicts — the model-probability columns stay stamped,
 * not numbered, because both matrix lanes failed their exams),
 * OPTIONS (per-expiry grids from option_grid_view: computed IV +
 * implied P(above strike), suppressed SHORT-DATED under 5 DTE),
 * HOLDINGS (the user's own on-device marks, valued from pulled
 * spot only). WATCH on every action; SELL stays WATCH with its
 * reason. Every number here is the bridge's; the UI formats, it
 * never computes a model figure.
 */
@Composable
fun StocksScreen(vm: AppViewModel) {
    val busy by vm.stocksBusy.collectAsState()
    val note by vm.stocksNote.collectAsState()
    val seg by vm.stocksSeg.collectAsState()
    val views by vm.stockViews.collectAsState()
    val sym by vm.stocksSym.collectAsState()
    val expiry by vm.stocksExpiry.collectAsState()
    val options by vm.optionsPayload.collectAsState()
    val holdings by vm.holdingsRows.collectAsState()
    val holdingNote by vm.holdingNote.collectAsState()

    LaunchedEffect(Unit) {
        vm.loadTape()
        vm.loadHoldings()
    }

    Column(modifier = Modifier.fillMaxSize().padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "Stocks",
                    style = MaterialTheme.typography.headlineMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    "Stocks & options — WATCH only. Five " +
                        "pre-registered model lanes were examined " +
                        "on 960 days of history and live chains; " +
                        "none passed, so nothing here is a trade " +
                        "signal.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Tokens.Dim
                )
                if (note.isNotEmpty()) {
                    Text(
                        note,
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.InkDim,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                }
            }
            Button(
                enabled = !busy,
                onClick = { vm.pullStocks() },
                colors = ButtonDefaults.buttonColors(
                    containerColor = Tokens.Ice,
                    contentColor = Tokens.PageBg)
            ) {
                Text(if (busy) "Pulling…" else "Pull stocks")
            }
        }
        Spacer(Modifier.height(8.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            listOf("tape" to "TAPE", "matrix" to "MATRIX",
                "options" to "OPTIONS", "holdings" to "HOLDINGS")
                .forEach { (value, label) ->
                    FilterChip(
                        selected = seg == value,
                        onClick = { vm.stocksSeg.value = value },
                        label = { Text(label) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = Tokens.Raised,
                            selectedLabelColor = Tokens.Ice,
                            containerColor = Tokens.CardBg,
                            labelColor = Tokens.Dim)
                    )
                }
        }
        Spacer(Modifier.height(10.dp))

        when (seg) {
            "tape" -> TapeView(views)
            "matrix" -> MatrixView(views)
            "options" -> OptionsView(
                vm = vm, views = views, sym = sym,
                expiry = expiry, payload = options)
            "holdings" -> HoldingsView(
                vm = vm, rows = holdings, note = holdingNote)
        }
    }
}

private fun money(v: Double?): String =
    v?.let { String.format("$%,.2f", it) } ?: "—"

private fun pct1(v: Double?): String =
    v?.let { String.format("%.1f%%", it) } ?: "—"

/** Realized-vol line from the view's rv block (engine numbers). */
private fun rvLine(view: JSONObject): String? {
    val rv = view.o("rv") ?: return null
    val cc20 = rv.d("cc20_pct") ?: return null
    return "Realized vol (annualized, pulled history): " +
        "cc20 ${pct1(cc20)} · cc60 ${pct1(rv.d("cc60_pct"))} · " +
        "EWMA(λ=0.94) ${pct1(rv.d("ewma94_pct"))}"
}

@Composable
private fun TapeView(views: List<Pair<String, JSONObject>>) {
    if (views.isEmpty()) {
        Text(
            "No stock pull yet — pull stocks and the tape fills " +
                "from the Nasdaq feed. Nothing is drawn from nothing.",
            style = MaterialTheme.typography.bodyMedium,
            color = Tokens.Dim
        )
        return
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(views, key = { it.first }) { (sym, view) ->
            TapeRow(sym, view)
        }
    }
}

@Composable
private fun TapeRow(sym: String, view: JSONObject) {
    val shape = RoundedCornerShape(12.dp)
    Column(
        modifier = Modifier.fillMaxWidth().clip(shape)
            .background(Tokens.CardBg)
            .border(1.dp, Tokens.Border, shape)
            .padding(12.dp)
    ) {
        Text(
            "$sym · ${view.s("company_name") ?: ""}" +
                if (view.b("stale")) " · STALE" else "",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Faint
        )
        Row(modifier = Modifier.padding(top = 2.dp)) {
            Text(
                money(view.d("last")),
                style = NumStyle.copy(
                    fontSize = MaterialTheme.typography
                        .titleLarge.fontSize,
                    fontWeight = FontWeight.Bold),
                color = Tokens.Ink
            )
            val pct = view.d("pct_change")
            if (pct != null) {
                Text(
                    String.format("  %+.2f%% today", pct),
                    style = NumStyle.copy(
                        fontWeight = FontWeight.Bold),
                    color = when {
                        pct > 0 -> Tokens.EdgePos
                        pct < 0 -> Tokens.EdgeNeg
                        else -> Tokens.Dim
                    },
                    modifier = Modifier.padding(top = 6.dp)
                )
            }
        }
        Text(
            "Spot (regular close): " +
                money(view.d("spot_reference")) + " — " +
                (view.s("spot_reference_basis") ?: ""),
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim
        )
        Text(
            "${view.s("market_status") ?: ""} · source: " +
                "${view.s("source") ?: ""} · pulled " +
                "${view.s("pulled_at") ?: ""}",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Faint
        )
        rvLine(view)?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.InkDim,
                modifier = Modifier.padding(top = 3.dp)
            )
        }
        val lanes = view.a("lanes")
        for (i in 0 until lanes.length()) {
            Text(
                lanes.optString(i),
                style = MaterialTheme.typography.labelMedium,
                color = Tokens.Faint,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
        Text(
            "ACTION: ${view.s("action") ?: "WATCH"} — " +
                (view.s("action_reason") ?: ""),
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Ice,
            modifier = Modifier.padding(top = 4.dp)
        )
    }
}

@Composable
private fun MatrixView(views: List<Pair<String, JSONObject>>) {
    Column(modifier = Modifier.fillMaxSize()) {
        Text(
            "One row per name: the market's spot, realized vol " +
                "from the pulled history, and the examined lanes' " +
                "verdicts. The model-probability columns of the " +
                "v13.0 design stay stamped, not numbered — both " +
                "matrix lanes failed their exams.",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim
        )
        Spacer(Modifier.height(8.dp))
        if (views.isEmpty()) {
            Text(
                "No stock pull yet — the matrix prices each " +
                    "name's realized vol and prints its lane " +
                    "truth. Pull stocks first — nothing is drawn " +
                    "from nothing.",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Dim
            )
            return
        }
        LazyColumn(
            verticalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxSize()
        ) {
            items(views, key = { it.first }) { (sym, view) ->
                val shape = RoundedCornerShape(12.dp)
                Column(
                    modifier = Modifier.fillMaxWidth().clip(shape)
                        .background(Tokens.CardBg)
                        .border(1.dp, Tokens.Border, shape)
                        .padding(12.dp)
                ) {
                    Text(
                        "$sym · ${view.s("company_name") ?: ""}",
                        style = MaterialTheme.typography
                            .titleMedium,
                        color = Tokens.Ink,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        "Spot (regular close): " +
                            money(view.d("spot_reference")) +
                            " — " +
                            (view.s("spot_reference_basis") ?: ""),
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.InkDim,
                        modifier = Modifier.padding(top = 2.dp)
                    )
                    rvLine(view)?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography
                                .bodySmall,
                            color = Tokens.InkDim,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                    val lanes = view.a("lanes")
                    for (i in 0 until lanes.length()) {
                        Text(
                            lanes.optString(i),
                            style = MaterialTheme.typography
                                .labelMedium,
                            color = Tokens.Faint,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                    Text(
                        "ACTION: ${view.s("action") ?: "WATCH"}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.Ice,
                        modifier = Modifier.padding(top = 3.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun OptionsView(
    vm: AppViewModel, views: List<Pair<String, JSONObject>>,
    sym: String?, expiry: String?, payload: JSONObject?
) {
    if (views.isEmpty()) {
        Text(
            "Pull stocks first — the grids price from the pulled " +
                "chains.",
            style = MaterialTheme.typography.bodyMedium,
            color = Tokens.Dim
        )
        return
    }
    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.horizontalScroll(
                rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            views.forEach { (name, _) ->
                FilterChip(
                    selected = sym == name,
                    onClick = { vm.chooseStockSymbol(name) },
                    label = { Text(name) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = Tokens.Raised,
                        selectedLabelColor = Tokens.Ice,
                        containerColor = Tokens.CardBg,
                        labelColor = Tokens.Dim)
                )
            }
        }
        val p = payload
        if (p == null) {
            Text(
                "Pricing the grid…",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Dim,
                modifier = Modifier.padding(top = 10.dp)
            )
            return
        }
        val err = p.s("error")
        if (err != null) {
            Text(
                "Options unavailable for ${p.s("symbol") ?: sym}: " +
                    err + " — the chain did not come back on this " +
                    "pull; nothing is filled in.",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Warn,
                modifier = Modifier.padding(top = 10.dp)
            )
            return
        }
        val expiries = p.a("expiries")
        val activeExpiry = expiry ?: p.s("expiry")
        Row(
            modifier = Modifier.padding(top = 6.dp)
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            for (i in 0 until expiries.length()) {
                val e = expiries.getJSONObject(i)
                val ex = e.s("expiry") ?: continue
                FilterChip(
                    selected = activeExpiry == ex,
                    onClick = { vm.chooseStockExpiry(ex) },
                    label = { Text("$ex · ${e.i("dte") ?: "?"}d") },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = Tokens.Raised,
                        selectedLabelColor = Tokens.Ice,
                        containerColor = Tokens.CardBg,
                        labelColor = Tokens.Dim)
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "${p.s("symbol")} options — expires " +
                "${p.s("expiry")} (${p.i("dte")} days) · spot " +
                money(p.d("spot")) + " (" +
                "${p.s("spot_basis") ?: ""})",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim
        )
        val chain = p.o("chain")
        if (chain != null) {
            Text(
                "Chain: ${chain.s("source") ?: ""} · pulled " +
                    "${chain.s("pulled_at") ?: ""} · " +
                    "${chain.s("delay_class") ?: ""}",
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.Faint
            )
        }
        Text(
            "MODEL: ${p.s("model_stamp") ?: ""}",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Ice,
            modifier = Modifier.padding(top = 2.dp)
        )
        val grid = p.o("grid")
        if (grid == null) {
            Text(
                "No grid for this expiry.",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Dim,
                modifier = Modifier.padding(top = 8.dp)
            )
            return
        }
        if (grid.b("short_dated")) {
            Text(
                "⚠ SHORT-DATED — IMPLIED UNRELIABLE: under 5 " +
                    "days to expiry the implied column carries " +
                    "more noise than information; the " +
                    "probabilities are suppressed, not shown.",
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.Warn,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(top = 4.dp)
            )
        }
        val em = grid.d("expected_move_pct")
        val sm = grid.d("straddle_move_pct")
        if (em != null || sm != null) {
            Text(
                "Expected move ${pct1(em)} · straddle move " +
                    pct1(sm),
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.InkDim,
                modifier = Modifier.padding(top = 3.dp)
            )
        }
        Spacer(Modifier.height(6.dp))
        GridHead()
        val rows = grid.a("rows")
        LazyColumn(modifier = Modifier.weight(1f)) {
            items(rows.length()) { i ->
                val r = rows.getJSONObject(i)
                GridRow(r)
            }
        }
        val notes = grid.a("notes")
        for (i in 0 until notes.length()) {
            Text(
                notes.optString(i),
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.Faint,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
        val laneStamps = p.o("lane_stamps")
        if (laneStamps != null) {
            val keys = laneStamps.keys()
            while (keys.hasNext()) {
                val k = keys.next()
                Text(
                    "$k: ${laneStamps.optString(k)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = Tokens.Faint,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
        }
    }
}

@Composable
private fun GridHead() {
    val weights = listOf(0.9f, 0.9f, 0.9f, 0.7f, 0.9f, 0.8f)
    val cells = listOf("STRIKE", "CALL BID", "CALL ASK", "IV",
        "P(ABOVE)", "ACTION")
    Row(
        modifier = Modifier.fillMaxWidth()
            .background(Tokens.Raised)
            .padding(horizontal = 8.dp, vertical = 5.dp)
    ) {
        cells.forEachIndexed { i, cell ->
            Text(
                cell,
                style = MaterialTheme.typography.labelMedium,
                color = Tokens.Ice,
                modifier = Modifier.weight(weights[i])
            )
        }
    }
}

@Composable
private fun GridRow(r: JSONObject) {
    val weights = listOf(0.9f, 0.9f, 0.9f, 0.7f, 0.9f, 0.8f)
    val cells = listOf(
        r.d("strike")?.let { String.format("%,.0f", it) } ?: "—",
        r.d("call_bid")?.let { String.format("%.2f", it) } ?: "—",
        r.d("call_ask")?.let { String.format("%.2f", it) } ?: "—",
        r.d("iv")?.let { String.format("%.0f%%", it * 100) } ?: "—",
        r.d("p_above")?.let {
            String.format("%.0f%%", it * 100)
        } ?: "—",
        r.s("action") ?: "WATCH"
    )
    Row(
        modifier = Modifier.fillMaxWidth()
            .background(Tokens.CardBg)
            .padding(horizontal = 8.dp, vertical = 5.dp)
    ) {
        cells.forEachIndexed { i, cell ->
            Text(
                cell,
                style = NumStyle.copy(
                    fontSize = MaterialTheme.typography
                        .bodySmall.fontSize),
                color = if (i == 5) Tokens.Ice else Tokens.InkDim,
                modifier = Modifier.weight(weights[i])
            )
        }
    }
}

@Composable
private fun HoldingsView(
    vm: AppViewModel, rows: List<JSONObject>, note: String
) {
    var fields by remember {
        mutableStateOf<Map<String, Pair<String, String>>>(emptyMap())
    }
    var totalValue = 0.0
    var totalCost = 0.0
    var anyPriced = false
    rows.forEach { row ->
        val v = row.d("value")
        val shares = row.d("shares") ?: 0.0
        val cost = row.d("avg_cost") ?: 0.0
        if (v != null) {
            totalValue += v
            totalCost += shares * cost
            anyPriced = true
        }
    }
    Column(
        modifier = Modifier.fillMaxSize()
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            "Your holdings — stored on this device only (name, " +
                "shares, cost). Value and P/L are computed from " +
                "the pulled spot, nothing else.",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim
        )
        if (note.isNotEmpty()) {
            Text(
                note,
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.InkDim,
                modifier = Modifier.padding(top = 3.dp)
            )
        }
        Spacer(Modifier.height(8.dp))
        rows.forEach { row ->
            val sym = row.s("symbol") ?: return@forEach
            val shares = row.d("shares") ?: 0.0
            val cost = row.d("avg_cost") ?: 0.0
            val pair = fields[sym] ?: (
                (if (shares > 0) trimNum(shares) else "") to
                    (if (cost > 0) trimNum(cost) else ""))
            Column(
                modifier = Modifier.fillMaxWidth()
                    .padding(vertical = 4.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(Tokens.CardBg)
                    .border(1.dp, Tokens.Border,
                        RoundedCornerShape(10.dp))
                    .padding(10.dp)
            ) {
                Row {
                    Text(
                        sym,
                        style = MaterialTheme.typography.titleMedium,
                        color = Tokens.Ink,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f)
                    )
                    Text(
                        money(row.d("spot")),
                        style = NumStyle.copy(
                            fontWeight = FontWeight.Bold),
                        color = Tokens.Ink
                    )
                }
                val value = row.d("value")
                if (value != null) {
                    val pl = row.d("pl")
                    Text(
                        String.format(
                            "%s shares @ %s · value %s · P/L %s",
                            trimNum(shares), money(cost),
                            money(value),
                            pl?.let {
                                String.format("%s (%.1f%%)",
                                    money(it),
                                    row.d("pl_pct") ?: 0.0)
                            } ?: "—"),
                        style = NumStyle.copy(
                            fontSize = MaterialTheme.typography
                                .bodySmall.fontSize),
                        color = when {
                            pl == null -> Tokens.Dim
                            pl >= 0 -> Tokens.EdgePos
                            else -> Tokens.EdgeNeg
                        }
                    )
                } else if (shares > 0) {
                    Text(
                        "held — pull the tape to value it from spot.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.Faint
                    )
                }
                Text(
                    "SELL: ${row.s("sell") ?: "WATCH"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = Tokens.Ice,
                    modifier = Modifier.padding(top = 2.dp)
                )
                Row(
                    modifier = Modifier.padding(top = 6.dp),
                    horizontalArrangement = Arrangement
                        .spacedBy(6.dp)
                ) {
                    OutlinedTextField(
                        value = pair.first,
                        onValueChange = {
                            fields = fields + (sym to (it to pair.second))
                        },
                        label = { Text("Shares") },
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedTextField(
                        value = pair.second,
                        onValueChange = {
                            fields = fields + (sym to (pair.first to it))
                        },
                        label = { Text("Cost $") },
                        singleLine = true,
                        modifier = Modifier.weight(1f)
                    )
                    OutlinedButton(
                        onClick = {
                            vm.saveHolding(sym, pair.first, pair.second)
                        },
                        modifier = Modifier.padding(top = 8.dp)
                    ) {
                        Text("Save")
                    }
                }
            }
        }
        if (anyPriced) {
            Spacer(Modifier.height(6.dp))
            val pl = totalValue - totalCost
            Text(
                String.format(
                    "Total value %s · cost basis %s · P/L %s " +
                        "(from pulled spot only)",
                    money(totalValue), money(totalCost), money(pl)),
                style = NumStyle.copy(fontWeight = FontWeight.Bold),
                color = Tokens.Ink
            )
        }
    }
}

/** 12.0 -> "12", 12.50 -> "12.5" (field prefill only). */
private fun trimNum(v: Double): String =
    if (v == v.toLong().toDouble()) v.toLong().toString()
    else v.toString()
