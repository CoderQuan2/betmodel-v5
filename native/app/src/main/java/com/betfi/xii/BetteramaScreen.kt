package com.betfi.xii

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Betterama — a named destination whose definition is being
 * locked by Praxis. This screen carries the stamp and nothing
 * else: no invented features, no fake data, no placeholder
 * cards. It fills in when the definition lands.
 */
@Composable
fun BetteramaScreen() {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text(
            "Betterama",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Text(
            "Betterama — new. Definition being locked.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(top = 12.dp)
        )
        Text(
            "Praxis will supply its definition as a follow-up.",
            style = MaterialTheme.typography.bodyMedium,
            color = Tokens.Dim,
            modifier = Modifier.padding(top = 8.dp)
        )
    }
}
