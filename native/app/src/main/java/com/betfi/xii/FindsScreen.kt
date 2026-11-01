package com.betfi.xii

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Finds — the distilled feed: golden bets first, then the ranked
 * finds, then the price conflicts, then the checked-no-edge
 * counter. Same pull, same prices as the Board; the feed only
 * re-ranks. The GOLDEN panel is honestly empty when nothing
 * qualifies — the gate is the engine's verdict (a priced,
 * A-band, pessimistic-edge, recorded lane), never copy.
 */
@Composable
fun FindsScreen(vm: AppViewModel, onOpenUrl: (String) -> Unit) {
    val finds by vm.finds.collectAsState()
    val expanded by vm.expandedIdx.collectAsState()
    val depthCache by vm.depthCache.collectAsState()
    val depthBusy by vm.depthBusyIdx.collectAsState()
    var counterOpen by remember { mutableStateOf(false) }

    Column(modifier = Modifier.fillMaxSize().padding(14.dp)) {
        Text(
            "Finds",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Text(
            "Finds — golden bets first, then the ranked finds. " +
                "Same pull, same prices as All cards; the feed " +
                "only re-ranks.",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim,
            modifier = Modifier.padding(top = 2.dp)
        )
        Spacer(Modifier.height(10.dp))

        val f = finds
        if (f == null || !f.hasSlate) {
            Text(
                "Nothing to distill — the feed distills the " +
                    "current pull. Pull the menu on the Board first.",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Dim
            )
            return@Column
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                SectionHeader("GOLDEN BETS", Tokens.Gold)
            }
            if (f.golden.isEmpty()) {
                item {
                    Column {
                        Text(
                            "☆ No golden bets on this pull",
                            style = MaterialTheme.typography
                                .titleMedium,
                            color = Tokens.Dim
                        )
                        Text(
                            "Nothing golden on this pull. The " +
                                "standard don't drop just 'cause " +
                                "the panel empty.",
                            style = MaterialTheme.typography
                                .bodySmall,
                            color = Tokens.Dim,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }
            }
            items(f.golden, key = { "g" + it.idx }) { c ->
                MarketCard(
                    card = c,
                    expanded = expanded == c.idx,
                    depth = depthCache[c.idx],
                    depthBusy = depthBusy == c.idx,
                    onToggle = { vm.toggleExpand(c.idx) },
                    onOpenUrl = onOpenUrl
                )
            }
            item {
                SectionHeader(
                    "FINDS — verdict ladder, then edge " +
                        "(${f.finds.size + f.overflow})",
                    Tokens.Ice
                )
            }
            if (f.finds.isEmpty()) {
                item {
                    Text(
                        "No priced, verdict-bearing market on " +
                            "this pull. The feed stays empty " +
                            "rather than promote a market the " +
                            "engine did not price.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Tokens.Dim
                    )
                }
            }
            items(f.finds, key = { "f" + it.idx }) { c ->
                MarketCard(
                    card = c,
                    expanded = expanded == c.idx,
                    depth = depthCache[c.idx],
                    depthBusy = depthBusy == c.idx,
                    onToggle = { vm.toggleExpand(c.idx) },
                    onOpenUrl = onOpenUrl
                )
            }
            if (f.overflow > 0) {
                item {
                    Text(
                        "+${f.overflow} more finds past the " +
                            "page cap — All cards on the Board " +
                            "holds the full list.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.Faint
                    )
                }
            }
            if (f.flagged.isNotEmpty()) {
                item {
                    SectionHeader(
                        "PRICE CONFLICT — two prices for the " +
                            "same event disagree inside this " +
                            "pull (${f.flagged.size})",
                        Tokens.Warn
                    )
                }
                items(f.flagged, key = { "x" + it.idx }) { c ->
                    MarketCard(
                        card = c,
                        expanded = expanded == c.idx,
                        depth = depthCache[c.idx],
                        depthBusy = depthBusy == c.idx,
                        onToggle = { vm.toggleExpand(c.idx) },
                        onOpenUrl = onOpenUrl
                    )
                }
            }
            item {
                TextButton(onClick = { counterOpen = !counterOpen }) {
                    Text(
                        "Checked — no edge (${f.counter.size}) " +
                            if (counterOpen) "▾" else "▸",
                        color = Tokens.Faint
                    )
                }
            }
            if (counterOpen) {
                items(f.counter) { line ->
                    Text(
                        line,
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.Faint
                    )
                }
            }
        }
    }
}

@Composable
fun SectionHeader(text: String, color: Color) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        color = color,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(top = 6.dp, bottom = 2.dp)
    )
}
