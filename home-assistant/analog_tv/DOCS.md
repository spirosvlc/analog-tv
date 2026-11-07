# Analog TV for Home Assistant OS

This is the new **Analog TV** app with slug `analog_tv` and port **8155**.
The new app does **not** automatically inherit the previous app's private
storage. See `docs/MIGRATION.md` in the bundled server folder to migrate the
database safely.

Database on HA host: `/addon_configs/local_analog_tv/analog_tv.db`

Database in app container: `/config/analog_tv.db`

Google Admin sign-in: Create private
`/addon_configs/local_analog_tv/auth.env` using `auth.env.example`. An HTTPS
hostname with a Google Web OAuth redirect is required for production login.
Without credentials the TV player works, but `/admin` remains locked.

Start the app, then open `http://HOME_ASSISTANT_IP:8155/` on your trusted LAN.
Open the admin at `https://YOUR_DOMAIN/admin` after completing Google OAuth
configuration. Detailed instructions are in the bundled server README.
