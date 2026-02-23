[app]
title           = ToyotaScan
package.name    = toyotascan
package.domain  = org.prius

source.dir      = .
source.include_exts = py,png,jpg,kv,atlas

version         = 1.0.0

requirements    = python3,kivy==2.3.0,pyjnius

orientation     = portrait

android.permissions = BLUETOOTH, BLUETOOTH_ADMIN, BLUETOOTH_CONNECT, BLUETOOTH_SCAN, ACCESS_FINE_LOCATION
android.api         = 33
android.minapi      = 26
android.ndk         = 25b
android.ndk_api     = 26
android.sdk         = 33
android.build_tools_version = 33.0.2
android.archs       = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True

android.release_artifact = apk

[buildozer]
log_level = 2
