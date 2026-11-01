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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * The Lab — the app's own instrument room: engine identity (from
 * the engine's own ping), data health including recorder health
 * (the bridge's verbatim health line), slate statistics, and the
 * parity spike — the bundled 25-market sample compared against
 * the desktop reference verdicts field-for-field, kept working
 * from Phase 1. LAB framings only; nothing user-facing elsewhere
 * speaks Lab.
 */
@Composable
fun LabScreen(vm: AppViewModel) {
    val lab by vm.lab.collectAsState()
    val spike by vm.spikeOutcome.collectAsState()
    val spikeRunning by vm.spikeRunning.collectAsState()

    LaunchedEffect(Unit) { vm.refreshLab() }

    Column(
        modifier = Modifier.fillMaxSize().padding(14.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text(
            "Lab",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Text(
            "Engine, data health and the parity check — the " +
                "app's own instrument room.",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim,
            modifier = Modifier.padding(top = 2.dp)
        )
        Spacer(Modifier.height(10.dp))

        val l = lab
        LabBlock("Engine") {
            if (l == null) {
                Line("Starting the engine…")
            } else {
                val e = l.engine
                Line("Version: " + (e.s("engine_version") ?: "—"))
                Line("File: " + (e.s("engine_file") ?: "—"))
                Line("Data dir: " + (e.s("data_dir") ?: "—"))
                Line("Marked slips on device: " +
                    cnt(l.markedSlips))
            }
        }
        Spacer(Modifier.height(10.dp))

        LabBlock("Recorder (instrument history)") {
            val r = l?.recorder
            if (r == null) {
                Line("…")
            } else {
                // the bridge's health line, verbatim — the same
                // sentence the Flet Lab prints
                Line(r.s("health_line") ?: "")
                Line(
                    "Records on file: " +
                        "${cnt(r.i("records_on_file"))} · recorded " +
                        "markets: " +
                        "${cnt(r.i("recorded_markets_on_file"))} · " +
                        "recorded this session: " +
                        "${cnt(r.i("recorded_session"))}"
                )
                r.s("last_error")?.let {
                    Line("Last recorder error: $it", Tokens.Bad)
                }
            }
        }
        Spacer(Modifier.height(10.dp))

        LabBlock("Latest pull") {
            val s = l?.latestPull
            if (s == null) {
                Line("No pull in memory this session.")
            } else {
                Line("Stamp: " + (s.s("stamp") ?: "—"))
                Line("Pulled at: " + (s.s("pulled_at") ?: "—"))
                Line(
                    "Markets: ${cnt(s.i("markets"))} · priced: " +
                        "${cnt(s.i("priced"))} · golden: " +
                        "${cnt(s.i("golden"))} · flagged: " +
                        "${cnt(s.i("flagged"))}"
                )
                val tags = s.o("cal_tags")
                if (tags != null && tags.length() > 0) {
                    val parts = mutableListOf<String>()
                    val it = tags.keys()
                    while (it.hasNext()) {
                        val k = it.next()
                        parts.add("$k ×${tags.optInt(k)}")
                    }
                    Line("Model stamps on file: " +
                        parts.joinToString(", "))
                }
                val stances = s.o("stances")
                if (stances != null && stances.length() > 0) {
                    val parts = mutableListOf<String>()
                    val it = stances.keys()
                    while (it.hasNext()) {
                        val k = it.next()
                        parts.add("$k ×${stances.optInt(k)}")
                    }
                    Line("Stances stamped: " +
                        parts.joinToString(", "))
                }
            }
        }
        Spacer(Modifier.height(14.dp))

        SectionHeader("Parity spike", Tokens.Ice)
        Text(
            "Runs the bundled 25-market parity sample through " +
                "the engine embedded in the app and compares " +
                "every verdict against the desktop reference — " +
                "the Phase-1 proof, kept on the Lab bench.",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim
        )
        Spacer(Modifier.height(6.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                enabled = !spikeRunning,
                onClick = { vm.runSpike() },
                colors = ButtonDefaults.buttonColors(
                    containerColor = Tokens.Ice,
                    contentColor = Tokens.PageBg)
            ) {
                Text(if (spikeRunning) "Running…" else "Run parity spike")
            }
        }
        spike?.let { p ->
            Spacer(Modifier.height(8.dp))
            Column(
                modifier = Modifier.fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Tokens.Raised)
                    .border(1.dp, Tokens.Border,
                        RoundedCornerShape(10.dp))
                    .padding(10.dp)
            ) {
                Text(
                    if (p.match) "PARITY: MATCH" else "PARITY: DIFF",
                    style = NumStyle.copy(
                        fontWeight = FontWeight.Bold),
                    color = if (p.match) Tokens.Ice else Tokens.Warn
                )
                Line(p.pingLine)
                Line("Verdicts: ${p.count}")
                Line("First verdict: ${p.firstLine}")
                Line("Mismatched fields: ${p.mismatches}")
                p.firstMismatch?.let {
                    Line("First mismatch: $it")
                }
            }
        }
    }
}

@Composable
private fun LabBlock(title: String,
                     content: @Composable () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(Tokens.CardBg)
            .border(1.dp, Tokens.Border, RoundedCornerShape(12.dp))
            .padding(12.dp)
    ) {
        Text(
            title.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            color = Tokens.Ice
        )
        Spacer(Modifier.height(4.dp))
        content()
    }
}

@Composable
private fun Line(text: String, color: Color = Tokens.InkDim) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = color
    )
}

/** Int-or-dash for the Lab's count lines. */
private fun cnt(v: Int?): String = v?.toString() ?: "—"
