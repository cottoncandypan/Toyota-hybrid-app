[app]
title           = ToyotaScan
package.name    = toyotascan
package.domain  = org.prius

source.dir      = .
source.include_exts = py,png,jpg,kv,atlas

version         = 1.0.0

requirements    = python3,kivy==2.3.0,pyjnius

orientation     = portrait

# Android specifics
android.permissions = BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_CONNECT,BLUETOOTH_SCAN,ACCESS_FINE_LOCATION
android.api         = 33
android.minapi      = 26
android.ndk         = 25b
android.build_tools = 34.0.0
android.archs       = arm64-v8a,armeabi-v7a

android.release_artifact = apk

[buildozer]
log_level = 2
