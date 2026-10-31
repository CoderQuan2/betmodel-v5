// BetFi Xii — native (Jetpack Compose + Chaquopy) build.
// Plugin versions are declared here only; modules apply them bare.
//
// VERIFY at first Actions build: this VM has no JDK, so none of these
// pins has been compiled against. They were chosen as a coherent set
// from the vendors' own compatibility notes (Chaquopy 17.2 changelog:
// supports AGP 9.0-9.4; AGP 9.x has Kotlin built in — do NOT apply
// org.jetbrains.kotlin.android). If the first build rejects a pin,
// fix the pin here and record the working set in BUILD-LOG.md.
plugins {
    // VERIFY at first Actions build
    id("com.android.application") version "9.4.1" apply false
    // VERIFY at first Actions build (must match the Kotlin release)
    id("org.jetbrains.kotlin.plugin.compose") version "2.4.20" apply false
    // Chaquopy 17.2.0 (2026-10-26) per chaquo.com changelog.
    id("com.chaquo.python") version "17.2.0" apply false
}
