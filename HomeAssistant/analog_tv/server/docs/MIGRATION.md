# Migrating a legacy installation to Analog TV

The application is now **fully renamed**. Home Assistant registers it as a
**new add-on slug** (`analog_tv`), and it stores its SQLite database as
`analog_tv.db`. This cannot share the old add-on's private folder automatically.

> Do not uninstall the previous add-on or delete its configuration before
> backing up the data. Stop both servers during the database copy, or SQLite
> may have uncheckpointed writes.

## Home Assistant OS

1. Stop your older TV app. In the Terminal/SSH app, make an offline copy:

   ```sh
   mkdir -p /addon_configs/local_analog_tv
   cp /addon_configs/local_rca_tv/rca.db /addon_configs/local_analog_tv/analog_tv.db
   ```

   If that path is unavailable inside your Terminal/SSH add-on, access the folders
   using a Samba share or an editor with `all_addon_configs` access. Do **not**
   modify or move the database while a server is running.

2. Install the new add-on under `/addons/analog_tv` and confirm slug `analog_tv`.
   Starting once creates `/addon_configs/local_analog_tv/` if necessary.
3. Place `analog_tv.db` in that folder, and place `auth.env` next to it.
4. Start Analog TV. It loads the migrated database at `/config/analog_tv.db`.
5. Verify channel count, settings, weather, Telegram, and YouTube OAuth. Change
   any old YouTube redirect URI to the new HTTPS hostname, if necessary.
6. Only after testing, uninstall the old add-on. Keep the offline backup.

## Docker / Python

Stop the old application and copy `data/rca.db` to `data/analog_tv.db`.
Update service names, Python module path `analog_tv.main` and env keys from
`RCA_` to `ANALOG_`. Do not reuse the old server's `RCA_` environment variables.

## Android

The Android application ID is `gr.analogtv.client`. It installs alongside the
old client, and its own app settings hold the new server address. The previous
client can be removed after Analog TV works.
