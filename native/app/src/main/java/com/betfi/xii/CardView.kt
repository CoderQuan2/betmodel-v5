package com.betfi.xii

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * One market card — a real composable (the native app has no
 * drawn-PNG workaround). Information order is the Flet F1 law:
 * bet identity first (the FanDuel market name -> the selection in
 * plain words -> the matchup), then the model's read (metal tier,
 * grade, model probability vs the pulled price, the edge in
 * points), then the verdict rung. Tap expands the card: the BET
 * NOW box mounts at the top of the expansion (its Flet law —
 * expanded cards only) and the five depth sections render from
 * the bridge-computed payload.
 */

@Composable
fun MarketCard(
    card: CardEntry,
    expanded: Boolean,
    depth: List<DepthSection>?,
    depthBusy: Boolean,
    onToggle: () -> Unit,
    onOpenUrl: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val golden = card.term == "GOLDEN BET"
    val accent = when {
        card.state == "UNPRICED" && !golden -> Tokens.Faint
        else -> Tokens.verdictColor(card.term)
    }
    val shape = RoundedCornerShape(12.dp)
    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(shape)
            .background(if (golden) Tokens.GoldDeep else Tokens.CardBg)
            .border(
                width = if (golden) 1.5.dp else 1.dp,
                color = if (golden) Tokens.Gold else Tokens.Border,
                shape = shape
            )
    ) {
        Row(modifier = Modifier.fillMaxWidth()) {
            // the accent bar (the drawn card's left rule)
            Box(
                modifier = Modifier
                    .width(5.dp)
                    .fillMaxHeight()
                    .padding(vertical = 10.dp)
                    .background(accent, RoundedCornerShape(3.dp))
            )
            Column(
                modifier = Modifier
                    .weight(1f)
                    .clickable(onClick = onToggle)
                    .padding(horizontal = 10.dp, vertical = 9.dp)
            ) {
                if (expanded && card.betNow) {
                    BetNowBox(card = card, onOpenUrl = onOpenUrl)
                    Spacer(Modifier.height(8.dp))
                }
                CardFace(card)
                if (expanded) {
                    Spacer(Modifier.height(6.dp))
                    DepthSections(depth = depth, busy = depthBusy)
                }
            }
        }
    }
}

@Composable
private fun CardFace(card: CardEntry) {
    val termColor = Tokens.verdictColor(card.term)
    Column {
        card.rank?.let { rank ->
            Text(
                "#$rank",
                style = MaterialTheme.typography.labelMedium,
                color = Tokens.Ice
            )
        }
        Text(
            card.rowHeadline,
            style = MaterialTheme.typography.titleMedium,
            color = Tokens.Ink,
            fontWeight = FontWeight.Bold
        )
        Text(
            card.rowEvent,
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Faint,
            modifier = Modifier.padding(top = 1.dp)
        )
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(top = 5.dp)
        ) {
            if (card.term.isNotEmpty()) {
                Text(
                    card.term,
                    style = MaterialTheme.typography.labelMedium,
                    color = termColor
                )
            }
            if (card.metal != null) {
                Text(
                    "  ·  ${card.metal}",
                    style = MaterialTheme.typography.labelMedium,
                    color = Tokens.metalColor(card.metal)
                )
            }
            if (card.grade != null) {
                Text(
                    "  ·  GRADE ${card.grade}",
                    style = MaterialTheme.typography.labelMedium,
                    color = Tokens.gradeColor(card.grade)
                )
            }
            if (card.state != null && card.state != "PRICED") {
                Text(
                    "  ·  ${card.state}",
                    style = MaterialTheme.typography.labelMedium,
                    color = Tokens.Faint
                )
            }
        }
        Row(modifier = Modifier.padding(top = 5.dp)) {
            StatColumn("MODEL", card.rowModel)
            Spacer(Modifier.width(18.dp))
            StatColumn("FANDUEL", card.rowOdds)
            Spacer(Modifier.width(18.dp))
            StatColumn(
                "EDGE (PTS)", card.rowEdge,
                valueColor = when {
                    card.edgePts == null -> Tokens.Dim
                    card.edgePts > 0 -> Tokens.EdgePos
                    card.edgePts < 0 -> Tokens.EdgeNeg
                    else -> Tokens.Dim
                }
            )
            Spacer(Modifier.width(18.dp))
            StatColumn("FIND IT", card.name.fdPath)
        }
    }
}

@Composable
private fun StatColumn(
    label: String, value: String,
    valueColor: Color = Tokens.Ink
) {
    Column {
        Text(
            label,
            style = MaterialTheme.typography.labelMedium,
            color = Tokens.Faint
        )
        Text(
            value,
            style = NumStyle.copy(
                fontSize = MaterialTheme.typography.bodyMedium.fontSize,
                fontWeight = FontWeight.Bold
            ),
            color = valueColor
        )
    }
}

/**
 * The BET NOW box (build 52/54's indicator, native): an ice glow
 * layer breathing on the standing 1.6 s pulse (alpha .45<->1.0)
 * behind the front box. Armed (the pull carried both FanDuel
 * ids) the tap opens the exact QuickSlip link; unarmed it still
 * flashes and says so — and opens nothing. Ice accent, never
 * gold: gold is GOLDEN-only by design law.
 */
@Composable
fun BetNowBox(card: CardEntry, onOpenUrl: (String) -> Unit) {
    val transition = rememberInfiniteTransition(label = "betnow")
    val pulse by transition.animateFloat(
        initialValue = 0.45f,
        targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 800),
            repeatMode = RepeatMode.Reverse
        ),
        label = "betnow-alpha"
    )
    val armed = card.betUrl != null
    val shape = RoundedCornerShape(10.dp)
    Box(modifier = Modifier.fillMaxWidth()) {
        Box(
            modifier = Modifier
                .matchParentSize()
                .padding(1.dp)
                .background(
                    Tokens.Ice.copy(alpha = 0.35f * pulse),
                    shape
                )
        )
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .clip(shape)
                .background(Tokens.CyanDeep)
                .border(1.5.dp, Tokens.Ice, shape)
                .clickable(enabled = armed) {
                    card.betUrl?.let(onOpenUrl)
                }
                .padding(10.dp)
        ) {
            Text(
                "● BET NOW — model projects this bet to beat " +
                    "its price",
                style = MaterialTheme.typography.labelMedium,
                color = Tokens.Ice
            )
            Text(
                if (armed) {
                    "OPEN THIS BET ON FANDUEL ↗ — " +
                        card.name.slipLabel
                } else {
                    "OPEN ON FANDUEL — pull the menu again to " +
                        "arm the exact one-tap link"
                },
                style = MaterialTheme.typography.bodySmall,
                color = if (armed) Tokens.Bone else Tokens.Dim,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(top = 3.dp)
            )
        }
    }
}

@Composable
private fun DepthSections(depth: List<DepthSection>?,
                          busy: Boolean) {
    Column {
        if (depth == null) {
            Text(
                if (busy) "Proving the projection…"
                else "Depth unavailable for this card.",
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.Dim
            )
            return
        }
        depth.forEach { section ->
            Spacer(Modifier.height(8.dp))
            Text(
                section.title,
                style = MaterialTheme.typography.labelMedium,
                color = Tokens.Ice
            )
            if (section.gloss.isNotEmpty()) {
                Text(
                    section.gloss,
                    style = MaterialTheme.typography.bodySmall,
                    color = Tokens.Faint
                )
            }
            section.lines.forEach { line ->
                Text(
                    line,
                    style = MaterialTheme.typography.bodySmall,
                    color = Tokens.InkDim,
                    modifier = Modifier.padding(top = 2.dp)
                )
            }
        }
    }
}
