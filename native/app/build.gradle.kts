plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

android {
    namespace = "com.betfi.xii"
    // VERIFY at first Actions build: 36 (Android 16) is the newest SDK
    // this pin set is known to resolve against. Raise compile/target
    // to 37 (Android 17, One UI 9) as soon as the runner image carries
    // the platform — the One UI 9 manual makes the newest API the
    // standing target.
    compileSdk = 36

    defaultConfig {
        // Deliberately distinct from the Flet app's package so the
        // native build can sit beside it on the Pilot's phone during
        // the parity phases — it replaces nothing until Phase 4.
        applicationId = "com.betfi.xii"
        minSdk = 26
        targetSdk = 36 // VERIFY with compileSdk
        versionCode = 1
        versionName = "0.1.0-native.1"
        // Chaquopy ships a Python runtime per ABI; keep the APK to
        // the Pilot's device class plus the emulator ABI.
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    buildFeatures {
        compose = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// Chaquopy 17 KTS DSL (top-level block; the old android.python block
// is Groovy-only in 17.x). VERIFY the block shape at first Actions
// build — it is the single most likely first-build failure.
// The engine is pure Python stdlib (proven from its import list), so
// there are NO pip installs: nothing for Chaquopy to fetch.
chaquopy {
    defaultConfig {
        // Matches the desktop parity proof's interpreter series
        // (VM Python 3.12.3; Chaquopy 17.2 ships runtime 3.12.15).
        version = "3.12"
    }
}

dependencies {
    // VERIFY at first Actions build (Compose BOM 2026.09.00 ->
    // Material 3 1.4.0, per developer.android.com).
    val composeBom = platform("androidx.compose:compose-bom:2026.09.00")
    implementation(composeBom)
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    // VERIFY at first Actions build
    implementation("androidx.activity:activity-compose:1.11.0")
    // VERIFY at first Actions build
    implementation("androidx.navigation:navigation-compose:2.9.5")
}
