package com.betfi.xii

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

// BetFi Xii identity: the same deep-slate board + ice accent the
// shipping app's shell uses. Jules' design/flair lane (BRIEF-001)
// explores beyond this baseline under brief; this scaffold only has
// to carry the identity honestly.
private val Ice = Color(0xFF38BDF8)
private val Board = Color(0xFF0B0F14)
private val Panel = Color(0xFF131A22)

private data class Destination(val route: String, val label: String)

private val Destinations = listOf(
    Destination("board", "Board"),
    Destination("finds", "Finds"),
    Destination("slip", "Slip"),
    Destination("lab", "Lab"),
    Destination("graphs", "3D"),
    Destination("stocks", "Stocks")
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Ice,
                    background = Board,
                    surface = Panel
                )
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    MainShell()
                }
            }
        }
    }
}

@Composable
private fun MainShell() {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val current = entry?.destination?.route ?: "board"

    // Adaptive layout is mandatory on >=600dp (One UI 9 manual — the
    // Fold7 case): rail beside the content when wide, bar below when
    // folded shut.
    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        if (maxWidth >= 600.dp) {
            Row(modifier = Modifier.fillMaxSize()) {
                NavigationRail {
                    Destinations.forEach { d ->
                        NavigationRailItem(
                            selected = current == d.route,
                            onClick = { nav.go(d.route) },
                            icon = {},
                            label = { Text(d.label) }
                        )
                    }
                }
                DestinationsNav(nav, Modifier.fillMaxSize())
            }
        } else {
            Column(modifier = Modifier.fillMaxSize()) {
                DestinationsNav(nav, Modifier.weight(1f).fillMaxWidth())
                NavigationBar {
                    Destinations.forEach { d ->
                        NavigationBarItem(
                            selected = current == d.route,
                            onClick = { nav.go(d.route) },
                            icon = {},
                            label = { Text(d.label) }
                        )
                    }
                }
            }
        }
    }
}

private fun NavHostController.go(route: String) {
    navigate(route) {
        popUpTo(graph.startDestinationId) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

@Composable
private fun DestinationsNav(nav: NavHostController, modifier: Modifier) {
    NavHost(navController = nav, startDestination = "board", modifier = modifier) {
        composable("board") { BoardScreen() }
        composable("finds") {
            PlaceholderScreen("Finds", "Destination parity lands in Phase 3.")
        }
        composable("slip") {
            PlaceholderScreen("Slip", "Destination parity lands in Phase 3.")
        }
        composable("lab") {
            PlaceholderScreen("Lab", "Destination parity lands in Phase 3.")
        }
        composable("graphs") {
            PlaceholderScreen("3D", "Destination parity lands in Phase 3.")
        }
        composable("stocks") {
            PlaceholderScreen("Stocks", "Destination parity lands in Phase 3.")
        }
    }
}

@Composable
private fun PlaceholderScreen(title: String, note: String) {
    Column(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Text("BetFi Xii", style = MaterialTheme.typography.titleMedium, color = Ice)
        Text(
            title,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(top = 8.dp)
        )
        Text(note, modifier = Modifier.padding(top = 8.dp))
    }
}

// ------------------------------------------------------------------
// Board — Phase 1 is the parity spike: run the embedded engine over
// the bundled sample slate and compare against the desktop reference
// verdicts, field by field (see Parity.kt / PARITY.md).
// ------------------------------------------------------------------

private data class SpikeOutcome(
    val ping: String,
    val count: Int,
    val firstLine: String,
    val result: Parity.Result
)

@Composable
private fun BoardScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var running by remember { mutableStateOf(false) }
    var outcome by remember { mutableStateOf<SpikeOutcome?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState())
    ) {
        Text("BetFi Xii", style = MaterialTheme.typography.titleMedium, color = Ice)
        Text(
            "Board",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(top = 8.dp)
        )
        Text(
            "Native shell · embedded engine · parity spike",
            modifier = Modifier.padding(top = 4.dp)
        )
        Button(
            enabled = !running,
            onClick = {
                running = true
                error = null
                scope.launch {
                    try {
                        outcome = withContext(Dispatchers.IO) { runSpike(context) }
                    } catch (e: Exception) {
                        error = "${e.javaClass.simpleName}: ${e.message}"
                    } finally {
                        running = false
                    }
                }
            },
            modifier = Modifier.padding(top = 20.dp)
        ) {
            Text(if (running) "Running…" else "Run parity spike")
        }

        error?.let {
            Text(
                "Engine error — $it",
                color = Color(0xFFEF4444),
                modifier = Modifier.padding(top = 16.dp)
            )
        }
        outcome?.let { o ->
            Text("Engine: ${o.ping}", modifier = Modifier.padding(top = 16.dp))
            Text("Verdicts: ${o.count}", modifier = Modifier.padding(top = 4.dp))
            Text(
                "First verdict: ${o.firstLine}",
                modifier = Modifier.padding(top = 4.dp)
            )
            Text(
                if (o.result.match) "PARITY: MATCH" else "PARITY: DIFF",
                fontWeight = FontWeight.Bold,
                color = if (o.result.match) Color(0xFF10B981) else Color(0xFFEF4444),
                modifier = Modifier.padding(top = 12.dp)
            )
            Text(
                "Compared ${o.result.gotCount} device verdicts against " +
                    "${o.result.refCount} reference verdicts · " +
                    "mismatched fields: ${o.result.mismatches}",
                modifier = Modifier.padding(top = 4.dp)
            )
            o.result.firstMismatch?.let {
                Text("First mismatch: $it", modifier = Modifier.padding(top = 4.dp))
            }
        }
    }
}

private fun readAsset(context: Context, name: String): String =
    context.assets.open(name).bufferedReader().use { it.readText() }

private fun runSpike(context: Context): SpikeOutcome {
    val ping = EngineBridge.ping(context)
    val slateJson = readAsset(context, "sample_slate.json")
    val verdictsJson = EngineBridge.runSlateJson(context, slateJson)
    val got = JSONArray(verdictsJson)
    val ref = JSONArray(readAsset(context, "reference_verdicts.json"))
    val result = Parity.compare(got, ref)
    val first: JSONObject = got.getJSONObject(0)
    val firstLine = listOf(
        first.optString("desc"),
        first.optString("state"),
        "grade ${first.optString("grade")}",
        first.optString("verdict"),
        "P ${first.optDouble("p")}",
        "bet_now ${first.optBoolean("bet_now")}"
    ).joinToString(" · ")
    return SpikeOutcome(
        ping = "betmodel v${ping.optString("engine_version")} · data: " +
            ping.optString("data_dir"),
        count = got.length(),
        firstLine = firstLine,
        result = result
    )
}
