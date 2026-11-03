plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.arraytx.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.arraytx.app"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"             // tracks the arraytx version it bundles
        ndk {
            // arm64 for phones, x86_64 for the emulator; each ABI carries its
            // own CPython + numpy/scipy/matplotlib (tens of MB each)
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    sourceSets {
        getByName("main") {
            // The page is one file set for every host: the desktop and the
            // browser get it from arraytx.webhost (src/arraytx/webui/www), and
            // this APK takes the very same files as its assets, loaded from
            // file:///android_asset/www/.
            assets.setSrcDirs(listOf("../../src/arraytx/webui"))
        }
    }
}

chaquopy {
    defaultConfig {
        // 3.10: the newest Python for which Chaquopy's repository has a scipy
        // wheel (chaquo/chaquopy#1237); arraytx declares requires-python >= 3.10
        // and its CI runs 3.10.
        version = "3.10"
        pip {
            // Android binary wheels from Chaquopy's index; pyyaml is pure
            // Python and comes from PyPI in the same resolve.
            install("numpy")
            install("scipy")
            install("matplotlib")
            install("pyyaml")
            // arraytx itself as an sdist (interpreted build).  An sdist, not
            // install("../.."): a directory install makes the whole repository
            // an input of the pip task and this Gradle project lives inside
            // that repository, which Gradle 8's validation rejects.
            // From the repo root: python -m build --sdist --outdir android/app/pysrc .
            val pysrc = file("pysrc")
            val sdists = pysrc.listFiles { f -> f.name.matches(Regex("arraytx-.*\\.tar\\.gz")) }?.toList() ?: emptyList()
            require(sdists.size == 1) {
                "expected exactly one arraytx sdist in android/app/pysrc/ (found ${sdists.size}); " +
                    "from the repo root run: python -m build --sdist --outdir android/app/pysrc ."
            }
            install(sdists[0].absolutePath)
        }
    }
}
