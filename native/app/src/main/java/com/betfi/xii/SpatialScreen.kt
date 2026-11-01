package com.betfi.xii

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * The TRUE SPATIAL 3D destination (route "graphs", label "3D"):
 * a real OpenGL ES 2.0 scene (SpatialRenderer.kt) fed by the
 * bridge's spatial_json(window). This replaces any WebView /
 * canvas instrument entirely — no WebView is used here.
 *
 * AXIS MAPPING (also in SpatialRenderer.kt and bridge.py):
 *   x = implied probability (0..1)
 *   y = edge (model p - implied p)
 *   z = time in hours
 *
 * Self-contained on purpose: it owns its payload state and calls
 * the bridge on Dispatchers.IO through EngineBridge, so it can
 * be wired into any shell (the seven-destination NavHost routes
 * "graphs" here) without depending on a particular view model.
 */
@Composable
fun TrueSpatialScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var window by remember { mutableStateOf("season") }
    var payload by remember { mutableStateOf<JSONObject?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var glView by remember { mutableStateOf<SpatialGLView?>(null) }

    fun load(win: String) {
        if (busy) return
        busy = true
        scope.launch {
            try {
                error = null
                val p = withContext(Dispatchers.IO) {
                    EngineBridge.spatial(context, win)
                }
                payload = p
                glView?.let {
                    it.renderer.loadPayload(p)
                    it.requestRender()
                }
            } catch (e: Exception) {
                error = "${e.javaClass.simpleName}: ${e.message}"
            } finally {
                busy = false
            }
        }
    }

    LaunchedEffect(Unit) { load(window) }

    val terrain = payload?.optJSONObject("terrain")
    val grid = terrain?.optJSONObject("grid")
    val cloud = payload?.optJSONArray("slate_cloud")
    val cloudSize = cloud?.length() ?: 0
    val historyBegins: String? = payload?.let {
        if (it.isNull("history_begins")) null
        else it.optString("history_begins").ifEmpty { null }
    }
    val zUnknown = payload?.optInt("slate_cloud_z_unknown", 0) ?: 0
    val sceneEmpty = payload != null && grid == null && cloudSize == 0

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF0B0F14))
            .padding(16.dp)
    ) {
        Text(
            "Scare Bets",
            style = MaterialTheme.typography.titleMedium,
            color = Color(0xFF38BDF8)
        )
        Text(
            "3D — Edge Terrain",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(top = 8.dp)
        )

        // TIME control — segmented, no slider.
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            listOf(
                "live" to "Live",
                "month" to "1 Month",
                "season" to "Season"
            ).forEach { (value, label) ->
                if (window == value) {
                    Button(onClick = { /* already selected */ }) {
                        Text(label)
                    }
                } else {
                    OutlinedButton(onClick = {
                        window = value
                        load(value)
                    }) { Text(label) }
                }
            }
            OutlinedButton(
                onClick = { load(window) },
                enabled = !busy,
                modifier = Modifier.padding(start = 4.dp)
            ) { Text(if (busy) "Loading…" else "Refresh") }
        }

        // Header counts — the payload's own numbers.
        payload?.let { p ->
            val pathsReturned = terrain?.optInt("paths_returned", 0) ?: 0
            val pathsTotal = terrain?.optInt("paths_total", 0) ?: 0
            val cellsFilled = grid?.optInt("cells_filled", 0) ?: 0
            val cellsTotal = grid?.optInt("cells_total", 0) ?: 0
            Text(
                "History begins: ${historyBegins ?: "—"} · " +
                    "paths $pathsReturned/$pathsTotal · " +
                    "cells $cellsFilled/$cellsTotal · " +
                    "slate cloud: $cloudSize points" +
                    (if (zUnknown > 0) {
                        " · slate_cloud_z_unknown: $zUnknown"
                    } else {
                        ""
                    }),
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 8.dp)
            )
        }

        // Axis legend — the mapping, on screen.
        Text(
            "Axes: x = implied probability (0..1) · " +
                "y = edge (model p − implied p) · z = time (hours). " +
                "Gold points = GOLDEN BET · ice points = BET NOW · " +
                "drag to orbit, pinch or +/− to zoom.",
            style = MaterialTheme.typography.bodySmall,
            color = Color(0xFF9AA7B4),
            modifier = Modifier.padding(top = 4.dp)
        )

        error?.let {
            Text(
                "Spatial error — $it",
                color = Color(0xFFEF4444),
                modifier = Modifier.padding(top = 8.dp)
            )
        }

        if (sceneEmpty) {
            // Honest empty state: no fake surface is drawn.
            Text(
                if (historyBegins != null) {
                    "No terrain or slate points in this window " +
                        "yet. On-device history begins " +
                        historyBegins +
                        " — the first pull this build records " +
                        "starts it; nothing before that is invented."
                } else {
                    "No terrain or slate points in this window " +
                        "yet. On-device history begins with the " +
                        "first pull this build records; nothing " +
                        "before that is invented."
                },
                modifier = Modifier.padding(top = 16.dp)
            )
        } else {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(420.dp)
                    .padding(top = 12.dp)
            ) {
                AndroidView(
                    factory = { ctx ->
                        SpatialGLView(ctx).also { view ->
                            glView = view
                            payload?.let { p ->
                                view.renderer.loadPayload(p)
                                view.requestRender()
                            }
                        }
                    },
                    update = { view ->
                        glView = view
                        payload?.let { p ->
                            view.renderer.loadPayload(p)
                            view.requestRender()
                        }
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }
            // Zoom buttons — no slider.
            Row(
                modifier = Modifier.padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(onClick = {
                    glView?.let {
                        it.renderer.zoomBy(0.8f)
                        it.requestRender()
                    }
                }) { Text("+") }
                OutlinedButton(onClick = {
                    glView?.let {
                        it.renderer.zoomBy(1.25f)
                        it.requestRender()
                    }
                }) { Text("−") }
                OutlinedButton(onClick = {
                    glView?.let {
                        it.renderer.resetCamera()
                        it.requestRender()
                    }
                }) { Text("Reset view") }
            }
        }
    }
}
