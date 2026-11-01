package com.betfi.xii

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.delay

/**
 * Scare Bets (native) — the shell. Seven destinations at Flet
 * parity plus the native true-spatial scene:
 *
 *   Board · Finds · Slip · 3D (true spatial, GL) · Graphs (the
 *   instrument shelf, WebView) · Lab · Stocks
 *
 * Display brand is "Scare Bets" (Pilot rebrand, 2026-10-31); the
 * applicationId stays com.betfi.xii so the app sits beside the
 * Flet build on the Pilot's phone — the Flet app remains the
 * shipping app until native parity + the Pilot's device verdict.
 *
 * Adaptive layout is mandatory on >=600dp (One UI 9 manual — the
 * Fold7 case): rail beside the content when wide, bar below when
 * folded shut. All engine contact goes through AppViewModel ->
 * EngineBridge -> bridge.py; this file only routes.
 */
private data class Destination(val route: String, val label: String)

private val Destinations = listOf(
    Destination("board", "Board"),
    Destination("finds", "Finds"),
    Destination("slip", "Slip"),
    Destination("lab", "Lab"),
    Destination("graphs", "3D"),
    Destination("stocks", "Stocks"),
    Destination("betterama", "Betterama")
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            GrandBetFiTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = Tokens.PageBg
                ) {
                    MainShell()
                }
            }
        }
    }
}

@Composable
private fun MainShell() {
    val vm: AppViewModel = viewModel()
    val context = LocalContext.current
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val current = entry?.destination?.route ?: "board"

    // Standing state loads once: the last pull, restored from
    // the device's state files by the bridge.
    LaunchedEffect(Unit) {
        vm.loadInitial()
    }
    // The auto-pull ticker: the gate itself (armed by a user
    // pull, 240 s interval, follows the shown sport) lives in
    // the view model — the Flet app's cadence, ported.
    LaunchedEffect(Unit) {
        while (true) {
            delay(20_000)
            vm.autoTick()
        }
    }

    val openUrl: (String) -> Unit = { url ->
        try {
            context.startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (e: Exception) {
            // No handler for the link: the card stays honest —
            // the box was the indicator; nothing else to do.
        }
    }

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
                DestinationsNav(nav, vm, openUrl,
                    Modifier.fillMaxSize())
            }
        } else {
            Column(modifier = Modifier.fillMaxSize()) {
                DestinationsNav(nav, vm, openUrl,
                    Modifier.weight(1f).fillMaxWidth())
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
private fun DestinationsNav(
    nav: NavHostController, vm: AppViewModel,
    openUrl: (String) -> Unit, modifier: Modifier
) {
    NavHost(
        navController = nav, startDestination = "board",
        modifier = modifier
    ) {
        composable("board") { BoardScreen(vm, openUrl) }
        composable("finds") { FindsScreen(vm, openUrl) }
        composable("slip") { SlipScreen(vm) }
        composable("graphs") { TrueSpatialScreen() }
        composable("lab") { LabScreen(vm) }
        composable("stocks") { StocksScreen(vm) }
        composable("betterama") { BetteramaScreen() }
    }
}
