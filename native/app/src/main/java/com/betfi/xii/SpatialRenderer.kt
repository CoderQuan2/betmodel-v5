package com.betfi.xii

import android.content.Context
import android.opengl.GLES20
import android.opengl.GLSurfaceView
import android.opengl.Matrix
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import javax.microedition.khronos.egl.EGLConfig
import javax.microedition.khronos.opengles.GL10
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * TRUE SPATIAL 3D — a real OpenGL ES 2.0 renderer for the bridge's
 * spatial_json payload (bridge.py, spatial_json). No WebView, no
 * canvas: the Edge Terrain is a true triangle surface mesh and
 * the slate is a GL_POINTS cloud, drawn by the GPU.
 *
 * AXIS MAPPING (the contract, stated in bridge.py as well):
 *   x = implied probability from the quoted price (0..1)
 *   y = edge, as a probability fraction (model p - implied p)
 *   z = time, in hours (terrain: hours since the window's first
 *       point; slate cloud: hours from the pull stamp to the
 *       market's own start time)
 *
 * World mapping (display only — the payload's numbers are never
 * altered): x in [x_min, x_max] -> [-1, 1]; y divided by the
 * largest |edge| in the scene (floored at 0.05) -> [-0.85, 0.85];
 * z divided by the largest z across grid and cloud -> [-1, 1].
 * Terrain cells that are null in the payload stay HOLES — any
 * triangle touching a null cell is skipped, never interpolated.
 *
 * Camera: perspective (45 deg), orbit by drag (azimuth /
 * elevation held here), distance zoom by pinch or the screen's
 * +/- buttons. No sliders anywhere. Auto-frame: the scene is
 * normalized to the [-1, 1] cube and the default camera
 * (azimuth 45, elevation 30, distance 3.4) frames that cube.
 */
class SpatialRenderer : GLSurfaceView.Renderer {

    @Volatile
    private var pendingPayload: JSONObject? = null

    @Volatile
    private var dirty = true

    @Volatile
    var azimuthDeg: Float = 45f
        private set

    @Volatile
    var elevationDeg: Float = 30f
        private set

    @Volatile
    var distance: Float = 3.4f
        private set

    /** Queue a new spatial payload; the GL thread rebuilds the
     *  scene from it on the next frame. */
    fun loadPayload(payload: JSONObject) {
        pendingPayload = payload
        dirty = true
    }

    fun rotateBy(dAzimuth: Float, dElevation: Float) {
        azimuthDeg += dAzimuth
        elevationDeg = (elevationDeg + dElevation).coerceIn(-80f, 80f)
        dirty = true
    }

    fun zoomBy(factor: Float) {
        distance = (distance * factor).coerceIn(1.6f, 8.0f)
        dirty = true
    }

    fun resetCamera() {
        azimuthDeg = 45f
        elevationDeg = 30f
        distance = 3.4f
        dirty = true
    }

    // ---- GL state -------------------------------------------------

    private var program = 0
    private var aPosLoc = -1
    private var aColorLoc = -1
    private var uMvpLoc = -1
    private var uPointSizeLoc = -1

    private var triPos: FloatBuffer? = null
    private var triColor: FloatBuffer? = null
    private var triCount = 0

    private var linePos: FloatBuffer? = null
    private var lineColor: FloatBuffer? = null
    private var lineCount = 0

    private var pointPos: FloatBuffer? = null
    private var pointColor: FloatBuffer? = null
    private var pointCount = 0

    private val projection = FloatArray(16)
    private val view = FloatArray(16)
    private val model = FloatArray(16)
    private val mvp = FloatArray(16)

    override fun onSurfaceCreated(gl: GL10?, config: EGLConfig?) {
        GLES20.glClearColor(0.043f, 0.059f, 0.078f, 1.0f) // #0B0F14
        GLES20.glEnable(GLES20.GL_DEPTH_TEST)
        program = buildProgram()
        aPosLoc = GLES20.glGetAttribLocation(program, "aPos")
        aColorLoc = GLES20.glGetAttribLocation(program, "aColor")
        uMvpLoc = GLES20.glGetUniformLocation(program, "uMvp")
        uPointSizeLoc = GLES20.glGetUniformLocation(program, "uPointSize")
        dirty = true
    }

    override fun onSurfaceChanged(gl: GL10?, width: Int, height: Int) {
        GLES20.glViewport(0, 0, width, height)
        val aspect = if (height == 0) 1f else width.toFloat() / height
        Matrix.perspectiveM(projection, 0, 45f, aspect, 0.1f, 20f)
        dirty = true
    }

    override fun onDrawFrame(gl: GL10?) {
        if (dirty) {
            pendingPayload?.let { rebuild(it) }
            dirty = false
        }
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT or GLES20.GL_DEPTH_BUFFER_BIT)
        if (program == 0) return

        // Orbit camera around the scene centre.
        val az = Math.toRadians(azimuthDeg.toDouble())
        val el = Math.toRadians(elevationDeg.toDouble())
        val eyeX = (distance * cos(el) * sin(az)).toFloat()
        val eyeY = (distance * sin(el)).toFloat()
        val eyeZ = (distance * cos(el) * cos(az)).toFloat()
        Matrix.setLookAtM(view, 0, eyeX, eyeY, eyeZ, 0f, 0f, 0f, 0f, 1f, 0f)
        Matrix.setIdentityM(model, 0)
        val vm = FloatArray(16)
        Matrix.multiplyMM(vm, 0, view, 0, model, 0)
        Matrix.multiplyMM(mvp, 0, projection, 0, vm, 0)

        GLES20.glUseProgram(program)
        GLES20.glUniformMatrix4fv(uMvpLoc, 1, false, mvp, 0)

        triPos?.let { draw(it, triColor, triCount, GLES20.GL_TRIANGLES, 1f) }
        linePos?.let { draw(it, lineColor, lineCount, GLES20.GL_LINES, 1f) }
        pointPos?.let {
            // Slate cloud points at ~12px (task spec).
            draw(it, pointColor, pointCount, GLES20.GL_POINTS, 12f)
        }
    }

    private fun draw(
        pos: FloatBuffer, color: FloatBuffer?, count: Int,
        mode: Int, pointSize: Float
    ) {
        if (count <= 0 || color == null) return
        GLES20.glUniform1f(uPointSizeLoc, pointSize)
        pos.position(0)
        color.position(0)
        GLES20.glEnableVertexAttribArray(aPosLoc)
        GLES20.glVertexAttribPointer(
            aPosLoc, 3, GLES20.GL_FLOAT, false, 0, pos
        )
        GLES20.glEnableVertexAttribArray(aColorLoc)
        GLES20.glVertexAttribPointer(
            aColorLoc, 4, GLES20.GL_FLOAT, false, 0, color
        )
        GLES20.glDrawArrays(mode, 0, count)
        GLES20.glDisableVertexAttribArray(aPosLoc)
        GLES20.glDisableVertexAttribArray(aColorLoc)
    }

    // ---- scene construction (GL thread, from the payload) ---------

    private fun rebuild(payload: JSONObject) {
        val terrain = payload.optJSONObject("terrain")
        val grid = terrain?.optJSONObject("grid")
        val cloudArr = payload.optJSONArray("slate_cloud")

        // Normalizers across grid + cloud.
        var maxZ = grid?.optDouble("z_max_hours", 0.0) ?: 0.0
        var maxAbsY = 0.05
        val cloud = ArrayList<FloatArray>()
        val cloudKind = ArrayList<Int>() // 0 plain, 1 bet_now, 2 golden
        if (cloudArr != null) {
            for (i in 0 until cloudArr.length()) {
                val pt = cloudArr.optJSONObject(i) ?: continue
                val xyz = pt.optJSONArray("xyz") ?: continue
                if (xyz.length() < 3) continue
                val x = xyz.optDouble(0, 0.0)
                val y = xyz.optDouble(1, 0.0)
                val z = xyz.optDouble(2, 0.0)
                cloud.add(
                    floatArrayOf(x.toFloat(), y.toFloat(), z.toFloat())
                )
                cloudKind.add(
                    when {
                        pt.optBoolean("golden") -> 2
                        pt.optBoolean("bet_now") -> 1
                        else -> 0
                    }
                )
                if (z > maxZ) maxZ = z
                if (abs(y) > maxAbsY) maxAbsY = abs(y)
            }
        }

        var nx = 0
        var nz = 0
        var heights: Array<Array<Double?>>? = null
        var xMin = 0.0
        var xMax = 1.0
        if (grid != null) {
            nx = grid.optInt("nx", 0)
            nz = grid.optInt("nz", 0)
            xMin = grid.optDouble("x_min", 0.0)
            xMax = grid.optDouble("x_max", 1.0)
            val hArr = grid.optJSONArray("heights")
            if (hArr != null && nx > 0 && nz > 0) {
                val built: Array<Array<Double?>> = Array(nz) { z ->
                    val row = hArr.optJSONArray(z)
                    Array(nx) { x ->
                        if (row == null || row.isNull(x)) {
                            null
                        } else {
                            val v = row.optDouble(x, Double.NaN)
                            if (v.isNaN()) null else v
                        }
                    }
                }
                heights = built
                for (z in 0 until nz) {
                    for (x in 0 until nx) {
                        val hv = built[z][x]
                        if (hv != null && abs(hv) > maxAbsY) {
                            maxAbsY = abs(hv)
                        }
                    }
                }
            }
        }
        if (maxZ <= 0.0) maxZ = 1.0

        fun wx(xProb: Double): Float =
            (((xProb - xMin) / max(1e-9, xMax - xMin)) * 2.0 - 1.0).toFloat()

        fun wy(edge: Double): Float =
            (edge / maxAbsY * 0.85).toFloat().coerceIn(-1f, 1f)

        fun wz(zHours: Double): Float =
            ((zHours / maxZ) * 2.0 - 1.0).toFloat()

        fun wzCell(zi: Int): Float =
            if (nz <= 1) 0f else ((zi.toDouble() / (nz - 1)) * 2.0 - 1.0).toFloat()

        fun wxCell(xi: Int): Float =
            if (nx <= 1) 0f else ((xi.toDouble() / (nx - 1)) * 2.0 - 1.0).toFloat()

        // (a) Edge Terrain — triangle mesh, holes at null cells.
        val tp = ArrayList<Float>()
        val tc = ArrayList<Float>()
        val h: Array<Array<Double?>>? = heights
        if (h != null) {
            fun vertex(zi: Int, xi: Int) {
                val height = h[zi][xi] ?: return
                tp.add(wxCell(xi)); tp.add(wy(height)); tp.add(wzCell(zi))
                val c = heightColor(height, maxAbsY)
                tc.add(c[0]); tc.add(c[1]); tc.add(c[2]); tc.add(1f)
            }
            for (z in 0 until nz - 1) {
                for (x in 0 until nx - 1) {
                    // Skip any triangle touching a null cell.
                    if (h[z][x] == null || h[z][x + 1] == null ||
                        h[z + 1][x] == null || h[z + 1][x + 1] == null
                    ) {
                        continue
                    }
                    vertex(z, x); vertex(z, x + 1); vertex(z + 1, x)
                    vertex(z, x + 1); vertex(z + 1, x + 1); vertex(z + 1, x)
                }
            }
        }
        triPos = floatBuffer(tp)
        triColor = floatBuffer(tc)
        triCount = tp.size / 3

        // (c) Axis lines + ground grid at y = 0.
        val lp = ArrayList<Float>()
        val lc = ArrayList<Float>()
        fun line(
            x1: Float, y1: Float, z1: Float,
            x2: Float, y2: Float, z2: Float,
            r: Float, g: Float, b: Float, a: Float
        ) {
            lp.add(x1); lp.add(y1); lp.add(z1)
            lp.add(x2); lp.add(y2); lp.add(z2)
            lc.add(r); lc.add(g); lc.add(b); lc.add(a)
            lc.add(r); lc.add(g); lc.add(b); lc.add(a)
        }
        // Axes ( brighter ): x ice, y green, z slate.
        line(-1f, 0f, -1f, 1f, 0f, -1f, 0.22f, 0.74f, 0.97f, 1f)
        line(-1f, -1f, -1f, -1f, 1f, -1f, 0.1f, 0.85f, 0.55f, 1f)
        line(-1f, 0f, -1f, -1f, 0f, 1f, 0.6f, 0.68f, 0.78f, 1f)
        // Ground grid.
        var gx = -1f
        while (gx <= 1.001f) {
            line(gx, 0f, -1f, gx, 0f, 1f, 0.25f, 0.3f, 0.38f, 0.6f)
            gx += 0.25f
        }
        var gz = -1f
        while (gz <= 1.001f) {
            line(-1f, 0f, gz, 1f, 0f, gz, 0.25f, 0.3f, 0.38f, 0.6f)
            gz += 0.25f
        }
        linePos = floatBuffer(lp)
        lineColor = floatBuffer(lc)
        lineCount = lp.size / 3

        // (b) Slate point cloud.
        val pp = ArrayList<Float>()
        val pc = ArrayList<Float>()
        for (i in cloud.indices) {
            val p = cloud[i]
            pp.add(wx(p[0].toDouble()))
            pp.add(wy(p[1].toDouble()))
            pp.add(wz(p[2].toDouble()))
            val c = when (cloudKind[i]) {
                // GOLD #FFD700 — golden points only.
                2 -> floatArrayOf(1.0f, 0.843f, 0.0f)
                // Ice #38BDF8 — bet_now points.
                1 -> floatArrayOf(0.22f, 0.74f, 0.97f)
                else -> floatArrayOf(0.78f, 0.83f, 0.88f)
            }
            pc.add(c[0]); pc.add(c[1]); pc.add(c[2]); pc.add(1f)
        }
        pointPos = floatBuffer(pp)
        pointColor = floatBuffer(pc)
        pointCount = pp.size / 3
    }

    /** Vertex colour by height: positive edge -> green/teal,
     *  negative -> muted red/slate, near zero -> panel gray,
     *  intensity scaled by |edge| against the scene's max. */
    private fun heightColor(height: Double, maxAbsY: Double): FloatArray {
        val t = min(1.0, abs(height) / maxAbsY).toFloat()
        val gray = floatArrayOf(0.23f, 0.28f, 0.34f)
        val target = if (height >= 0) {
            floatArrayOf(0.08f, 0.85f, 0.58f)
        } else {
            floatArrayOf(0.62f, 0.30f, 0.30f)
        }
        return floatArrayOf(
            gray[0] + (target[0] - gray[0]) * t,
            gray[1] + (target[1] - gray[1]) * t,
            gray[2] + (target[2] - gray[2]) * t
        )
    }

    private fun floatBuffer(values: List<Float>): FloatBuffer {
        val buf = ByteBuffer
            .allocateDirect(values.size * 4)
            .order(ByteOrder.nativeOrder())
            .asFloatBuffer()
        for (v in values) buf.put(v)
        buf.position(0)
        return buf
    }

    private fun buildProgram(): Int {
        val vertexSrc = """
            attribute vec3 aPos;
            attribute vec4 aColor;
            uniform mat4 uMvp;
            uniform float uPointSize;
            varying vec4 vColor;
            void main() {
                vColor = aColor;
                gl_Position = uMvp * vec4(aPos, 1.0);
                gl_PointSize = uPointSize;
            }
        """.trimIndent()
        val fragmentSrc = """
            precision mediump float;
            varying vec4 vColor;
            void main() {
                gl_FragColor = vColor;
            }
        """.trimIndent()
        val vs = compileShader(GLES20.GL_VERTEX_SHADER, vertexSrc)
        val fs = compileShader(GLES20.GL_FRAGMENT_SHADER, fragmentSrc)
        val prog = GLES20.glCreateProgram()
        GLES20.glAttachShader(prog, vs)
        GLES20.glAttachShader(prog, fs)
        GLES20.glLinkProgram(prog)
        return prog
    }

    private fun compileShader(type: Int, src: String): Int {
        val shader = GLES20.glCreateShader(type)
        GLES20.glShaderSource(shader, src)
        GLES20.glCompileShader(shader)
        return shader
    }
}

/**
 * GLSurfaceView hosting [SpatialRenderer], with drag-orbit and
 * pinch-zoom wired to the renderer's camera state. Kept beside
 * the renderer so the Compose screen is a thin AndroidView wrap.
 */
class SpatialGLView(context: Context) : GLSurfaceView(context) {

    val renderer = SpatialRenderer()

    private var lastX = 0f
    private var lastY = 0f

    private val scaleDetector = ScaleGestureDetector(
        context,
        object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScale(detector: ScaleGestureDetector): Boolean {
                // Pinch out (factor > 1) zooms in: distance shrinks.
                renderer.zoomBy(1f / detector.scaleFactor)
                requestRender()
                return true
            }
        }
    )

    init {
        setEGLContextClientVersion(2)
        setRenderer(renderer)
        renderMode = RENDERMODE_WHEN_DIRTY
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaleDetector.onTouchEvent(event)
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                lastX = event.x
                lastY = event.y
            }
            MotionEvent.ACTION_MOVE -> {
                if (!scaleDetector.isInProgress &&
                    event.pointerCount == 1
                ) {
                    val dx = event.x - lastX
                    val dy = event.y - lastY
                    // Drag orbits: horizontal -> azimuth,
                    // vertical -> elevation.
                    renderer.rotateBy(dx * 0.4f, dy * 0.4f)
                    lastX = event.x
                    lastY = event.y
                    requestRender()
                }
            }
        }
        parent?.requestDisallowInterceptTouchEvent(true)
        return true
    }
}
