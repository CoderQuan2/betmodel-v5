# Scare Bets (com.betfi.xii) — release R8/ProGuard rules.
# The release build type enables minify + resource shrinking, so
# everything reflection- or JNI-reached needs an explicit keep:
# Chaquopy reaches the Python bridge and its own runtime classes
# by name from native code, and any name R8 renames is a runtime
# crash on device that no compile step would catch.

# --- Chaquopy runtime -------------------------------------------------
# Chaquopy's own documented keep: its Java classes are loaded and
# called from the embedded CPython runtime and JNI, never from
# statically reachable Kotlin code.
-keep class com.chaquo.python.** { *; }

# --- The Python bridge door -------------------------------------------
# EngineBridge is the shell's only door to Python; Chaquopy's
# PyObject callAttr resolution and the app's own startup path
# (BetFiApp, registered in the manifest) must survive renaming.
-keep class com.betfi.xii.EngineBridge { *; }
-keep class com.betfi.xii.BetFiApp { *; }
# MainActivity is manifest-registered (android:name), and the
# manifest name is rewritten by the build — keep the class as the
# standard Android rule for activities.
-keep class com.betfi.xii.MainActivity { *; }
# Parity + the payload models are plain data holders read by the
# UI; keeping them costs little and removes a whole class of
# reflective-serialization surprises if a future lane adds any.
-keep class com.betfi.xii.Parity { *; }

# --- Standard Chaquopy / Android dontwarn lines -----------------------
# Chaquopy's documented companion warnings: its optional platform
# hooks reference classes that are not on every classpath.
-dontwarn com.chaquo.python.**
# org.json ships with the Android framework (boot classpath); any
# bundled-stub reference warning is spurious on device.
-dontwarn org.json.**
# Kotlin coroutines' internal Main dispatcher probing references
# Android classes conditionally; the standard dontwarn for it.
-dontwarn kotlinx.coroutines.**
