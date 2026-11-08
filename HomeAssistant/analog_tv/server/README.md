# Analog TV 2.1.2 for Home Assistant OS

1. Stop your existing Analog TV add-on and back up its persistent config.
   Extract this ZIP and replace the add-on source folder at
   `/addons/analog_tv` with the included `analog_tv` folder. Keep the
   persistent `/addon_configs/local_analog_tv` folder and its SQLite database.
2. Refresh the Home Assistant add-on store and install or update the local
   Analog TV add-on to **2.1.2**.
3. In the Analog TV add-on's **Configuration** tab, set
   `allow_admin_setup` to `true`, save and start or restart the add-on.
4. On your LAN, open `http://HOME_ASSISTANT_IP:8155/admin`. Enter a username
   and a password of at least 16 characters, confirm it, and select
   **Create Admin account**. Then sign in with those credentials.
5. Set `allow_admin_setup` back to `false` and restart the add-on. Sign in
   again at the same address.

The setup form is available only when setup is enabled and the database has
no Admin account. The first successful submission closes setup. Enable it
only while you are ready to create your account on a trusted LAN. Admin APIs
stay locked until you sign in.

The username and salted scrypt hash are stored in the existing
`analog_tv.db`. The add-on uses browser setup and ignores legacy
`auth.env` settings. If upgrading, create a fresh account from the form.

The player stays at `http://HOME_ASSISTANT_IP:8155/`. Direct HTTP leaves the
password and session cookie unencrypted in transit. Keep port 8155 on a
trusted LAN. Admin sessions expire after eight hours and end on restart,
logout or replacement login.
