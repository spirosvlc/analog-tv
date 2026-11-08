# Analog TV 2.1.2

Analog TV turns local media and IPTV streams into a continuous TV lineup with
a green phosphor program guide, a dedicated weather channel and retro alerts.
Watch in a browser or with the **Analog TV** app for Android phones and Android TV.

## Release files

| File | Use |
| --- | --- |
| `analog-tv-home-assistant-v2.1.2.zip` | Install or update the Home Assistant add-on. Includes the server source. |
| `Analog-TV-v2.1.2.apk` | Sideload the same app on Android phones and Android TV running Android 6.0 or later. |
| `Analog-TV-Android-v2.1.2-source.zip` | Open the app project in Android Studio and build it yourself. |

## Install or update on Home Assistant OS

1. If upgrading, stop the Analog TV add-on and back up
   `/addon_configs/local_analog_tv`, including `analog_tv.db`. Keep that
   folder and your media paths in place.
2. Extract the add-on ZIP and copy the included `analog_tv` folder to
   `/addons/analog_tv`. Refresh the Home Assistant add-on store and install
   or update **Analog TV** to **2.1.2**.
3. Start the add-on. Open `http://HOME_ASSISTANT_IP:8155/` on your LAN and
   replace `HOME_ASSISTANT_IP` with your Home Assistant host's IP address.
   Viewers can open the player, guide, IPTV channels and weather without
   signing in.

### Create the local Admin account

1. In the add-on's **Configuration** tab, set `allow_admin_setup` to
   `true`. Save and restart the add-on.
2. Open `http://HOME_ASSISTANT_IP:8155/admin`. Choose a username and a
   password of at least 16 characters. Confirm the password and select
   **Create Admin account**.
3. Sign in at the same address. Once the account is saved, the setup form
   closes. Set `allow_admin_setup` back to `false` and restart the add-on.

The add-on stores the username and a salted scrypt password hash in its
existing SQLite database. This setup requires no proxy, Google Admin
account, `auth.env` or terminal command. If you upgraded from Google Admin
or file-based login, create a fresh local account through the form.

Enable first-run setup only when you are ready to create the account. Keep
port 8155 on a trusted LAN. Direct HTTP leaves the password and session
cookie unencrypted in transit. Admin writes and logout require a CSRF token,
login attempts are rate limited, and sessions expire after eight hours or end
on logout, replacement login or restart.

### Configure channels and integrations

Use **Broadcast Control** to configure local media, IPTV playlists, weather
and alerts. For an M3U playlist import, choose the starting channel number.
Set a weather location before using the forecast channel.

YouTube remains an optional integration with its own Google authorization.
The add-on stores its OAuth client secret and tokens in
`/addon_configs/local_analog_tv/analog_tv.db`. Keep the database and add-on
backups private when publishing the source to GitHub.

## Android phones and Android TV

1. Sideload `Analog-TV-v2.1.2.apk` on your phone or TV. Look for **Analog TV**
   and its green logo in the launcher.
2. Select a discovered server or enter your player address, for example
   `http://192.168.1.45:8155`.
3. On TV, use the directional buttons or channel buttons to tune, and press
   **OK** to open the guide. Hold **0** or press **Menu** for server settings.
   On a phone, tap the left or right edge to change channels and press and
   hold to open server settings.

The app remembers your server address and tries to reconnect after a network
interruption. Use a browser for Broadcast Control at `/admin`.

The APK uses a development signing key for sideloading. If an installed copy
uses a different key, Android requires you to uninstall that copy first.
Record your server address before uninstalling, since uninstalling clears
the saved app settings. To build from source, open the extracted `android`
folder in Android Studio with Android SDK 36 installed.

## Standalone server

The browser account setup above applies to the Home Assistant add-on.
The standalone **v2.1.1** package uses its own provisioning and HTTPS
instructions. Follow the README bundled with that package.

## Verification

The server suite passed 21 tests, including account creation, login after
restart, and Admin API protection. The Android APK signature and phone and
TV launcher entries were verified. The add-on has yet to be tested on a live
Home Assistant OS host, and Android playback has yet to be tested on
physical devices.
