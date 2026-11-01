package com.betfi.xii

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * Grand BetFi design system — the Flet shell's ICE palette carried
 * over as tokens (main.py, the v10 palette + the v12 ICE design
 * system, "an X-ray of a bet"): deep-navy board, bone linework,
 * one ice-cyan glow wherever the model sees something real.
 *
 * DESIGN LAW (from the shell, binding here): GOLD is reserved to
 * GOLDEN surfaces — nowhere else. The ice accent marks priced /
 * live / BET NOW elements; unpriced and empty states get no glow.
 */
object Tokens {
    val PageBg = Color(0xFF0B0F14)
    val CardBg = Color(0xFF0B1329)
    val Raised = Color(0xFF111C38)
    val PanelRaised = Color(0xFF101E3D)
    val Border = Color(0xFF1E293B)
    val Hairline = Color(0xFF1E3A5F)
    val ChipBorder = Color(0xFF334155)

    val Ink = Color(0xFFE2E8F0)
    val Bone = Color(0xFFEAF8FF)
    val BoneDim = Color(0xFFCDE8F8)
    val Dim = Color(0xFF94A3B8)
    val InkDim = Color(0xFF8FA8C8)
    val Faint = Color(0xFF64748B)

    val Ice = Color(0xFF38BDF8)       // the X-ray cyan (ACCENT)
    val IceHi = Color(0xFF7DE0FF)
    val CyanDeep = Color(0xFF0E3C60)  // BET NOW box base
    val Gold = Color(0xFFFFD700)      // GOLDEN only — nowhere else
    val GoldDeep = Color(0xFF2A1F06)

    val Warn = Color(0xFFF59E0B)
    val Bad = Color(0xFFEF4444)
    val EdgePos = Color(0xFF10B981)
    val EdgeNeg = Color(0xFFEF4444)

    /** Verdict-rung colours (main.py VERDICT_COLORS). */
    fun verdictColor(term: String?): Color = when (term) {
        "GOLDEN BET" -> Color(0xFFFFD700)
        "BET HERE" -> Color(0xFF10B981)
        "RISK BET (BET)" -> Color(0xFFFBBF24)
        "RISK BET (DO NOT BET)" -> Color(0xFFF97316)
        "DO NOT BET" -> Color(0xFFEF4444)
        else -> Dim
    }

    /** Grade colours (main.py GRADE_COLORS). */
    fun gradeColor(grade: String?): Color = when (grade) {
        "A+" -> Color(0xFF10B981)
        "A" -> Color(0xFF10B981)
        "A-" -> Color(0xFF34D399)
        "B+" -> Color(0xFF60A5FA)
        "B" -> Color(0xFF3B82F6)
        "B-" -> Color(0xFF93C5FD)
        "C+" -> Color(0xFFFBBF24)
        "C" -> Color(0xFFF59E0B)
        "C-" -> Color(0xFFD97706)
        "D+" -> Color(0xFFF87171)
        "D" -> Color(0xFFEF4444)
        "D-" -> Color(0xFFDC2626)
        "F" -> Color(0xFF991B1B)
        else -> Faint
    }

    /** Metal tier accent: GOLDEN gold, SILVER slate, STEEL grey. */
    fun metalColor(metal: String?): Color = when (metal) {
        "GOLDEN" -> Gold
        "SILVER" -> Color(0xFFC0C8D4)
        "STEEL" -> Color(0xFF8A94A6)
        else -> Faint
    }
}

private val GrandColors = darkColorScheme(
    primary = Tokens.Ice,
    onPrimary = Tokens.PageBg,
    secondary = Tokens.IceHi,
    background = Tokens.PageBg,
    onBackground = Tokens.Ink,
    surface = Tokens.CardBg,
    onSurface = Tokens.Ink,
    surfaceVariant = Tokens.Raised,
    onSurfaceVariant = Tokens.Dim,
    outline = Tokens.Border,
    error = Tokens.Bad
)

private val GrandType = Typography(
    headlineMedium = TextStyle(
        fontFamily = FontFamily.Default, fontWeight = FontWeight.Bold,
        fontSize = 26.sp, lineHeight = 32.sp
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.Default, fontWeight = FontWeight.Bold,
        fontSize = 15.sp, lineHeight = 20.sp
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default, fontSize = 13.sp,
        lineHeight = 18.sp
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.Default, fontSize = 11.5.sp,
        lineHeight = 16.sp
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.Default, fontWeight = FontWeight.Bold,
        fontSize = 11.sp, lineHeight = 14.sp, letterSpacing = 0.6.sp
    )
)

/** Numbers everywhere use the monospace face (the shell's NUM_FONT). */
val NumStyle = TextStyle(fontFamily = FontFamily.Monospace)

@Composable
fun GrandBetFiTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = GrandColors,
        typography = GrandType,
        content = content
    )
}
