package com.betfi.xii

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/** The scoped-pull chooser's sports (the engine's
 * FANDUEL_EVENT_TYPES keys, mirrored as data). */
val MENU_SPORTS = listOf(
    "nfl", "nba", "mlb", "nhl", "soccer", "tennis", "mma", "golf",
    "boxing", "cricket", "darts", "motorsport", "rugby-union",
    "rugby-league", "lacrosse", "snooker", "table-tennis"
)

@Composable
fun BoardScreen(vm: AppViewModel, onOpenUrl: (String) -> Unit) {
    val board by vm.board.collectAsState()
    val busy by vm.boardBusy.collectAsState()
    val status by vm.boardStatus.collectAsState()
    val sportView by vm.sportView.collectAsState()
    val showMode by vm.showMode.collectAsState()
    val sortMode by vm.sortMode.collectAsState()
    val search by vm.searchText.collectAsState()
    val limit by vm.cardLimit.collectAsState()
    val chosen by vm.chosenSport.collectAsState()
    val expanded by vm.expandedIdx.collectAsState()
    val depthCache by vm.depthCache.collectAsState()
    val depthBusy by vm.depthBusyIdx.collectAsState()
    val armed by vm.autoArmed.collectAsState()

    val anchorMs = remember(board) { parseStampMs(board?.pulledAt) }
    val visible = remember(board, sportView, showMode, sortMode,
        search) {
        val cards = board?.cards ?: emptyList()
        applySort(
            applyShow(cards, sportView, showMode, search, anchorMs),
            sortMode)
    }
    val sportsOnSlate = remember(board) {
        (board?.cards?.mapNotNull { it.sport }?.distinct()
            ?: emptyList()).sorted()
    }

    Column(modifier = Modifier.fillMaxSize().padding(14.dp)) {
        // Scare Bets branding: the Pilot's official logo
        // (res/drawable/scare_bets_logo.jpg) beside the brand
        // name in the Board header.
        Row(
            verticalAlignment = androidx.compose.ui.Alignment
                .CenterVertically,
            modifier = Modifier.padding(bottom = 8.dp)
        ) {
            androidx.compose.foundation.Image(
                painter = androidx.compose.ui.res.painterResource(
                    R.drawable.scare_bets_logo
                ),
                contentDescription = "Scare Bets logo",
                contentScale = androidx.compose.ui.layout
                    .ContentScale.Crop,
                modifier = Modifier
                    .size(44.dp)
                    .clip(
                        androidx.compose.foundation.shape
                            .RoundedCornerShape(10.dp)
                    )
            )
            Spacer(Modifier.width(10.dp))
            Text(
                "Scare Bets",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = Tokens.Ice
            )
        }
        Text(
            "Board",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold
        )
        Text(
            board?.stamp ?: "No pull yet",
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Dim
        )
        if (status.isNotEmpty()) {
            Text(
                status,
                style = MaterialTheme.typography.bodySmall,
                color = Tokens.InkDim,
                modifier = Modifier.padding(top = 2.dp)
            )
        }
        Spacer(Modifier.height(8.dp))

        // ---- pull controls: full + scoped (the chooser names
        // its target; a manual pull arms the auto-pull loop) ----
        Row(verticalAlignment = androidx.compose.ui.Alignment
            .CenterVertically) {
            Button(
                enabled = !busy,
                onClick = { vm.pullFull() },
                colors = ButtonDefaults.buttonColors(
                    containerColor = Tokens.Ice,
                    contentColor = Tokens.PageBg)
            ) {
                Text(if (busy) "Pulling…" else "Pull all")
            }
            Spacer(Modifier.width(8.dp))
            SportChooser(
                chosen = chosen,
                onChoose = { vm.chosenSport.value = it })
            Spacer(Modifier.width(8.dp))
            OutlinedButton(
                enabled = !busy,
                onClick = { vm.pullScoped(chosen) }
            ) {
                Text("Pull ${chosen}")
            }
        }
        Text(
            if (armed) {
                "Auto-pull armed — every 4 minutes the board " +
                    "refreshes the sport in front of you."
            } else {
                "Auto-pull arms after your first pull."
            },
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Faint,
            modifier = Modifier.padding(top = 4.dp)
        )
        Spacer(Modifier.height(6.dp))

        // ---- sport view chips ----
        ChipRow(
            options = listOf("all" to "All sports") +
                sportsOnSlate.map { it to sportLabel(it) },
            selected = sportView,
            onSelect = { vm.sportView.value = it }
        )
        // ---- Show + sort ----
        ChipRow(
            options = SHOW_MODES,
            selected = showMode,
            onSelect = { vm.showMode.value = it }
        )
        Row(verticalAlignment = androidx.compose.ui.Alignment
            .CenterVertically) {
            SortChooser(
                chosen = sortMode,
                onChoose = { vm.sortMode.value = it })
            Spacer(Modifier.width(10.dp))
            OutlinedTextField(
                value = search,
                onValueChange = { vm.searchText.value = it },
                label = { Text("Search cards") },
                singleLine = true,
                modifier = Modifier.weight(1f)
            )
        }
        Spacer(Modifier.height(8.dp))

        Text(
            "Showing ${minOf(limit, visible.size)} of " +
                "${visible.size} markets" +
                (board?.receipt?.let {
                    " · ${it.priced} priced · ${it.golden} golden"
                } ?: ""),
            style = MaterialTheme.typography.bodySmall,
            color = Tokens.Faint
        )
        Spacer(Modifier.height(6.dp))

        if (board == null) {
            Text(
                "Nothing pulled yet. Pull the menu and the board " +
                    "fills with the engine's verdicts — nothing " +
                    "is drawn from nothing.",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Dim
            )
            return@Column
        }
        if (visible.isEmpty()) {
            Text(
                "No markets match this view. The pull is intact " +
                    "— the filters are what is empty.",
                style = MaterialTheme.typography.bodyMedium,
                color = Tokens.Dim
            )
            return@Column
        }

        val page = visible.take(limit)
        BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
            if (maxWidth >= 600.dp) {
                // Wide (the Fold open): list + detail two-pane.
                val selected = page.firstOrNull {
                    it.idx == expanded
                } ?: visible.firstOrNull { it.idx == expanded }
                Row(modifier = Modifier.fillMaxSize()) {
                    LazyColumn(
                        modifier = Modifier.weight(1f)
                            .fillMaxSize(),
                        verticalArrangement = Arrangement
                            .spacedBy(8.dp)
                    ) {
                        items(page, key = { it.key + it.idx }) { c ->
                            MarketCard(
                                card = c,
                                expanded = false,
                                depth = null, depthBusy = false,
                                onToggle = { vm.toggleExpand(c.idx) },
                                onOpenUrl = onOpenUrl
                            )
                        }
                        item { ShowMore(visible.size, limit, vm) }
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(
                        modifier = Modifier.weight(1f)
                            .fillMaxSize()
                            .verticalScroll(rememberScrollState())
                    ) {
                        if (selected != null) {
                            MarketCard(
                                card = selected,
                                expanded = true,
                                depth = depthCache[selected.idx],
                                depthBusy = depthBusy ==
                                    selected.idx,
                                onToggle = {
                                    vm.toggleExpand(selected.idx)
                                },
                                onOpenUrl = onOpenUrl
                            )
                        } else {
                            Text(
                                "Tap a card to read its depth — " +
                                    "the five sections, proved " +
                                    "from the engine's own numbers.",
                                style = MaterialTheme.typography
                                    .bodyMedium,
                                color = Tokens.Dim
                            )
                        }
                    }
                }
            } else {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(page, key = { it.key + it.idx }) { c ->
                        MarketCard(
                            card = c,
                            expanded = expanded == c.idx,
                            depth = depthCache[c.idx],
                            depthBusy = depthBusy == c.idx,
                            onToggle = { vm.toggleExpand(c.idx) },
                            onOpenUrl = onOpenUrl
                        )
                    }
                    item { ShowMore(visible.size, limit, vm) }
                }
            }
        }
    }
}

@Composable
private fun ShowMore(total: Int, limit: Int, vm: AppViewModel) {
    if (total > limit) {
        OutlinedButton(
            onClick = {
                vm.cardLimit.value = limit + AppViewModel.CARD_PAGE
            },
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Show more (${total - limit} more)")
        }
    }
}

@Composable
private fun ChipRow(options: List<Pair<String, String>>,
                    selected: String,
                    onSelect: (String) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        options.forEach { (value, label) ->
            FilterChip(
                selected = selected == value,
                onClick = { onSelect(value) },
                label = { Text(label) },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = Tokens.Raised,
                    selectedLabelColor = Tokens.Ice,
                    containerColor = Tokens.CardBg,
                    labelColor = Tokens.Dim
                )
            )
        }
    }
}

@Composable
private fun SportChooser(chosen: String,
                         onChoose: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    BoxWithConstraints {
        OutlinedButton(onClick = { open = true }) {
            Text(sportLabel(chosen) + " ▾")
        }
        DropdownMenu(expanded = open,
            onDismissRequest = { open = false }) {
            MENU_SPORTS.forEach { sport ->
                DropdownMenuItem(
                    text = { Text(sportLabel(sport)) },
                    onClick = { onChoose(sport); open = false }
                )
            }
        }
    }
}

@Composable
private fun SortChooser(chosen: String,
                        onChoose: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val label = SORT_MODES.firstOrNull { it.first == chosen }
        ?.second ?: chosen
    BoxWithConstraints {
        OutlinedButton(onClick = { open = true }) {
            Text("Sort: $label ▾")
        }
        DropdownMenu(expanded = open,
            onDismissRequest = { open = false }) {
            SORT_MODES.forEach { (value, text) ->
                DropdownMenuItem(
                    text = { Text(text) },
                    onClick = { onChoose(value); open = false }
                )
            }
        }
    }
}

/** Sport key -> its name (the shell's SPORT_LABELS short forms). */
fun sportLabel(sport: String): String = when (sport) {
    "nfl" -> "American football"
    "ncaaf" -> "College football"
    "nba" -> "Basketball"
    "nhl" -> "Hockey"
    "mlb" -> "Baseball"
    "soccer" -> "Soccer"
    "tennis" -> "Tennis"
    "mma" -> "MMA"
    "golf" -> "Golf"
    "boxing" -> "Boxing"
    "cricket" -> "Cricket"
    "darts" -> "Darts"
    "motorsport" -> "Motorsport"
    "rugby-union" -> "Rugby union"
    "rugby-league" -> "Rugby league"
    "lacrosse" -> "Lacrosse"
    "snooker" -> "Snooker"
    "table-tennis" -> "Table tennis"
    else -> sport.uppercase()
}
