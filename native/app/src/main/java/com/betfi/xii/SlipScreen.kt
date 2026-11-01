package com.betfi.xii

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * The Protected Slip — GOLDEN BET / BET HERE markets from the
 * CURRENT pull only, auto-built and sized by the engine's Kelly
 * organ (quarter-Kelly, 5% hard cap). Protection is arithmetic
 * printed in the open: total stake, and max loss = the total
 * stake. The app NEVER places anything: the user places the slip
 * on FanDuel themselves, then marks it here — the mark, and only
 * the mark, is written, after a two-step confirm.
 */
@Composable
fun SlipScreen(vm: AppViewModel) {
    val slip by vm.slip.collectAsState()
    val confirm by vm.slipConfirm.collectAsState()
    val status by vm.slipStatus.collectAsState()
    val bankroll by vm.bankrollText.collectAsState()
    val marked by vm.markedCount.collectAsState()

    Column(
        modifier = Modifier.fillMaxSize().padding(14.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            "Slip",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            value = bankroll,
            onValueChange = {
                vm.bankrollText.value = it
                vm.slipConfirm.value = false
            },
            label = { Text("Bankroll ($) — stakes print in " +
                "dollars when set") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth()
        )
        OutlinedButton(
            onClick = { vm.refreshSlip() },
            modifier = Modifier.padding(top = 6.dp)
        ) {
            Text("Rebuild the slip")
        }
        Spacer(Modifier.height(10.dp))

        val s = slip
        val panelShape = RoundedCornerShape(14.dp)
        Column(
            modifier = Modifier.fillMaxWidth()
                .clip(panelShape)
                .background(
                    if (s?.anyGolden == true) Tokens.GoldDeep
                    else Tokens.CardBg)
                .border(
                    width = if (s?.anyGolden == true) 1.5.dp
                    else 1.dp,
                    color = if (s?.anyGolden == true) Tokens.Gold
                    else Tokens.Border,
                    shape = panelShape)
                .padding(12.dp)
        ) {
            Text(
                "PROTECTED SLIP — PLACEMENT-READY",
                style = MaterialTheme.typography.labelMedium,
                color = Tokens.Ice
            )
            Text(
                "Auto-built from this pull's GOLDEN BET / BET " +
                    "HERE markets, sized by the engine's Kelly " +
                    "organ. You place it on FanDuel yourself — " +
                    "the app never places a bet and never touches " +
                    "a sportsbook account.",
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.Dim,
                modifier = Modifier.padding(top = 4.dp)
            )
            if (s == null || s.legs.isEmpty()) {
                Text(
                    "No GOLDEN BET or BET HERE markets on this " +
                        "pull — the slip stays empty rather than " +
                        "promote a market the engine did not bless.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Tokens.Dim,
                    modifier = Modifier.padding(top = 8.dp)
                )
            } else {
                // the pinned summary: legs, combined odds +
                // combined model probability, max loss
                val summary = StringBuilder()
                summary.append("${s.legs.size} legs · combined odds ")
                summary.append(
                    String.format("%.2f", s.combinedDecimal ?: 0.0))
                s.combinedAmerican?.let {
                    summary.append(String.format(" (%+d)", it))
                }
                summary.append(" · model ")
                summary.append(
                    String.format("%.1f%%",
                        (s.combinedModelP ?: 0.0) * 100))
                summary.append(" · max loss ")
                summary.append(
                    String.format("%.1fu", s.totalUnits))
                s.totalDollars?.let {
                    summary.append(
                        String.format(" / $%,.0f", it))
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    summary.toString(),
                    style = NumStyle.copy(
                        fontWeight = FontWeight.Bold),
                    color = Tokens.Ink
                )
                Spacer(Modifier.height(8.dp))
                s.legs.forEach { leg ->
                    Row(modifier = Modifier.padding(vertical = 3.dp)) {
                        Text(
                            leg.term,
                            style = MaterialTheme.typography
                                .labelMedium,
                            color = Tokens.verdictColor(leg.term)
                        )
                        Column(modifier = Modifier.padding(
                            start = 8.dp)) {
                            Text(
                                leg.selection,
                                style = MaterialTheme.typography
                                    .bodyMedium,
                                color = Tokens.Ink,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                "${leg.market} · " +
                                    String.format("%+d", leg.price) +
                                    " · Kelly stake " +
                                    leg.stakeText,
                                style = NumStyle.copy(
                                    fontSize = MaterialTheme
                                        .typography.bodySmall
                                        .fontSize),
                                color = Tokens.Dim
                            )
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                val totalTxt = StringBuilder("Total stake ")
                totalTxt.append(
                    String.format("%.1fu", s.totalUnits))
                s.totalDollars?.let {
                    totalTxt.append(
                        String.format(" ($%,.0f)", it))
                }
                Text(
                    totalTxt.toString(),
                    style = NumStyle.copy(
                        fontWeight = FontWeight.Bold,
                        fontSize = MaterialTheme.typography
                            .titleMedium.fontSize),
                    color = Tokens.Ink
                )
                val lossTxt = StringBuilder()
                lossTxt.append(
                    "Max loss = the total stake above (")
                lossTxt.append(
                    String.format("%.1fu", s.totalUnits))
                s.totalDollars?.let {
                    lossTxt.append(
                        String.format(" / $%,.0f", it))
                }
                lossTxt.append(") — every leg can lose, and the " +
                    "slip loses no more than what is staked. " +
                    "There is no scenario worse than that printed " +
                    "here.")
                Text(
                    lossTxt.toString(),
                    style = MaterialTheme.typography.bodySmall,
                    color = Tokens.Warn,
                    modifier = Modifier.padding(top = 4.dp)
                )
                if (s.warnings.isNotEmpty()) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "WARNINGS — READ BEFORE PLACING",
                        style = MaterialTheme.typography.labelMedium,
                        color = Tokens.Warn
                    )
                    s.warnings.forEach { w ->
                        Text(
                            "⚠ $w",
                            style = MaterialTheme.typography
                                .bodySmall,
                            color = Tokens.Warn,
                            modifier = Modifier.padding(top = 2.dp)
                        )
                    }
                }
                // correlation: how the legs hold together
                if (s.clusters.isNotEmpty() ||
                    s.singles.isNotEmpty()) {
                    Spacer(Modifier.height(10.dp))
                    SectionHeader(
                        "Protected Slip — how the legs hold " +
                            "together", Tokens.Ice)
                    Text(
                        "Legs that share a game, a team or a " +
                            "league rise and fall together — " +
                            "correlation the flat slip list hides. " +
                            "Spread legs are the diversification.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.Dim
                    )
                    s.clusters.forEach { c ->
                        Column(modifier = Modifier.padding(top = 6.dp)) {
                            Text(
                                c.title,
                                style = MaterialTheme.typography
                                    .bodyMedium,
                                color = Tokens.Ink,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                c.legs.joinToString(" · "),
                                style = MaterialTheme.typography
                                    .bodySmall,
                                color = Tokens.Dim
                            )
                            Text(
                                c.note,
                                style = MaterialTheme.typography
                                    .bodySmall,
                                color = Tokens.Warn
                            )
                        }
                    }
                    if (s.singles.isNotEmpty()) {
                        Text(
                            "Standing alone — real diversification: " +
                                s.singles.joinToString(", "),
                            style = MaterialTheme.typography
                                .bodySmall,
                            color = Tokens.Dim,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                    if (s.clusters.isEmpty()) {
                        Text(
                            "No two legs share a game, a team or " +
                                "a league — this slip is spread as " +
                                "wide as this pull allows.",
                            style = MaterialTheme.typography
                                .bodySmall,
                            color = Tokens.Dim,
                            modifier = Modifier.padding(top = 4.dp)
                        )
                    }
                }
                // mark-placed: two steps, the mark is the only
                // thing ever written
                Spacer(Modifier.height(12.dp))
                if (!confirm) {
                    Button(
                        onClick = { vm.slipConfirm.value = true },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Tokens.Ice,
                            contentColor = Tokens.PageBg)
                    ) {
                        Text("Mark placed on FanDuel")
                    }
                    Text(
                        "Tapping asks you to confirm the legs + " +
                            "total first. Nothing is written until " +
                            "you confirm — and what is written is " +
                            "YOUR mark, as PLACED (user-marked).",
                        style = MaterialTheme.typography.bodySmall,
                        color = Tokens.Faint,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                } else {
                    Text(
                        "Confirm: you placed exactly these legs " +
                            "on FanDuel at the prices above?",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Tokens.Ink,
                        fontWeight = FontWeight.Bold
                    )
                    Row(
                        modifier = Modifier.padding(top = 6.dp),
                        horizontalArrangement = Arrangement
                            .spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = { vm.markPlaced() },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = Tokens.Ice,
                                contentColor = Tokens.PageBg)
                        ) {
                            Text("Yes — mark it placed")
                        }
                        OutlinedButton(
                            onClick = { vm.slipConfirm.value = false }
                        ) {
                            Text("Not yet")
                        }
                    }
                }
            }
        }
        if (status.isNotEmpty()) {
            Text(
                status,
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.InkDim,
                modifier = Modifier.padding(top = 8.dp)
            )
        }
        Text(
            "PLACED (user-marked): $marked slip(s) you marked " +
                "placed from the Protected Slip. Your marks, on " +
                "this device; the app placed none of them.",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Faint,
            modifier = Modifier.padding(top = 6.dp)
        )
    }
}
