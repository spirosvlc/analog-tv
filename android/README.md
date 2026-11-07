# Analog TV — Android TV and touchscreen client

A fullscreen, CRT-styled client for the Analog TV server. Build an APK in
Android Studio and install it on a supported Android TV, set-top box or touch
screen device. Java package: `gr.analogtv.client`.

## Building

1. Open this `android` folder in Android Studio.
2. Let Android Studio sync the Gradle plugin and Android SDK.
3. Choose **Build → Build APK(s)** to create a debug APK, or generate a signed
   release APK using your own keystore.
4. Install the APK and connect to Analog TV. The default host port is `8155`.

This repository contains **source code**, not a prebuilt or signed APK. The
version in this release is **2.1.0** (versionCode 5).

## On-device behavior

- Immersive fullscreen WebView player, including YouTube iframe support.
- Native animated offline TV snow while connecting, with a green status box.
- Detects connectivity changes; retries after HA reboots or network loss.
- Keeps screen on while playing and checks server after sleep/resume.
- Searches your local `/24` for an Analog TV server on port 8155 or 8080.
- Remembers selected server IP in Android app preferences.
- No top-right connection indicator is displayed.
- Server control menu via long press `0` (short `0` remains OK) or Menu key.
- Menu: server IP, discovery, reload, clear cache, restart, version, reachability.
- Touch: tap left 30% for previous channel; right 70% for next channel;
  long-press anywhere to open service controls.

Android client playback requires access only to the **public viewer endpoints**
of the Analog TV server. Google sign-in is required only for the separate
web-based Admin. Avoid opening `/admin` inside the Android wrapper if you have
not configured HTTPS and Google OAuth.
