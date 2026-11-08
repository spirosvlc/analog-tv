# Analog TV 2.1.1 for Home Assistant OS

1. Stop the existing Analog TV add-on and back up its persistent config,
   including the SQLite database. Keep the same `analog_tv` slug.
2. Extract the ZIP and copy the full `analog_tv` folder to `/addons/analog_tv`.
   In the Home Assistant app store, check for updates and install or update
   Analog TV. Keep the persistent config and media directories in place.
3. Start the add-on. On the LAN, open `http://HOME_ASSISTANT_IP:8155/` for
   public playback, guide and weather.
4. On a trusted computer, open a terminal in the extracted `analog_tv/server`
   directory and run:
   ```sh
   python3 -m analog_tv.auth.provision auth.env.new operator https://tv.example.com
   ```
   Enter a unique password of at least 16 characters at the hidden prompts.
   Use the exact HTTPS origin for your proxy, including any nondefault port.
5. Privately install the generated file at
   `/addon_configs/local_analog_tv/auth.env` (inside the add-on this is
   `/config/auth.env`). Replace the old Google Admin settings and keep
   unrelated settings if present. Restrict file access to the add-on and your
   administrator. Keep the existing database and media paths.
6. Use a trusted HTTPS reverse proxy that forwards to port 8155 and sets
   `X-Forwarded-Proto: https`. Set the add-on option `trusted_proxy_ip` to the
   exact address the add-on sees for the proxy. Never use a wildcard. Restart
   the add-on, then visit `https://tv.example.com/admin`.

A private HTTPS hostname is sufficient. Admin stays locked until configured;
the public player still works. YouTube's separate Google integration is
unchanged. To rotate the password, generate a fresh file and restart.
See [the bundled server README](server/README.md) for more details.
