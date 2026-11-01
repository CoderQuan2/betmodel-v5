import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

// Release signing (Scare Bets v1.0.0 production config): read the
// OPTIONAL keystore.properties at the native/ project root
// (storeFile / storePassword / keyAlias / keyPassword). If the
// file exists, a "release" signing config is created from it and
// applied to the release build type. If it is absent, the release
// build stays UNSIGNED — no credentials are invented, here or in
// CI (see .github/workflows/build-native.yml). keystore.properties
// and keystore files are gitignored (native/.gitignore); a
// storeFile path in the properties is read relative to the
// native/ project root.
val keystorePropertiesFile = rootProject.file("keystore.properties")
val keystoreProperties = Properties()
if (keystorePropertiesFile.exists()) {
    keystorePropertiesFile.inputStream().use {
        keystoreProperties.load(it)
    }
}

android {
    namespace = "com.betfi.xii"
    // compileSdk 37 (Android 17, One UI 9) — REQUIRED by the Compose
    // BOM 2026.09.00 pin: androidx.compose.ui 1.12.1 refuses to build
    // against API 36 (AAR-metadata check). Proven by the local
    // toolchain build (2026-10-31, ~/workspace/toolchain): the
    // scaffold compiled clean at 37, debug + release; at 36 it fails
    // after dependency resolution. The Actions workflow installs
    // platforms;android-37.0 explicitly (see build-native.yml).
    compileSdk = 37

    defaultConfig {
        // Deliberately distinct from the Flet app's package so the
        // native build can sit beside it on the Pilot's phone during
        // the parity phases — it replaces nothing until Phase 4.
        // (Display brand is "Scare Bets" since the 2026-10-31
        // rebrand; the applicationId deliberately does NOT rename.)
        applicationId = "com.betfi.xii"
        minSdk = 26
        targetSdk = 37 // raised with compileSdk (local-build proven)
        versionCode = 1
        versionName = "1.0.0"
        // Chaquopy ships a Python runtime per ABI; keep the APK to
        // the Pilot's device class plus the emulator ABI.
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    signingConfigs {
        if (keystorePropertiesFile.exists()) {
            create("release") {
                storeFile = rootProject.file(
                    keystoreProperties.getProperty("storeFile")
                )
                storePassword =
                    keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword =
                    keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildFeatures {
        compose = true
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            if (keystorePropertiesFile.exists()) {
                signingConfig = signingConfigs.getByName("release")
            }
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
    // VERIFY at first Actions build (explicit foundation: LazyColumn,
    // LazyRow and the animation core the BET NOW flash uses ride here)
    implementation("androidx.compose.foundation:foundation")
    debugImplementation("androidx.compose.ui:ui-tooling")
    // VERIFY at first Actions build
    implementation("androidx.activity:activity-compose:1.11.0")
    // VERIFY at first Actions build
    implementation("androidx.navigation:navigation-compose:2.9.5")
    // VERIFY at first Actions build (the shell's viewModel() delegate
    // for AppViewModel, an AndroidViewModel)
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    // VERIFY at first Actions build (viewModelScope, used by
    // AppViewModel; also carries kotlinx-coroutines-android, whose
    // asCoroutineDispatcher EngineBridge.PythonDispatcher uses)
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.9.4")
}
