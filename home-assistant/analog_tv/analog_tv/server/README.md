# Analog TV 2.1.1 — local Admin login

Analog TV serves its player, guide, channel streams and weather without a login.
Broadcast Control at `/admin` uses one locally provisioned account. Optional
YouTube integration still has its own Google authorization.

## Install or upgrade

- **Python 3.11+:** Open a terminal in the extracted `server` folder. Create and
  activate a virtual environment, run `python -m pip install -r requirements.txt`,
  then run `python -m analog_tv.main`. The player defaults to port 8080.
  Install FFmpeg/ffprobe if using local media. Copy `.env.example` to `.env`
  if you need to set the database path or port.
- **Docker:** In `server`, create `.env` (copy `.env.example`, then set
  `ANALOG_DATABASE_URL=sqlite:///./data/analog_tv.db` for the bundled volume).
  To enable Admin, put the generated authentication settings into `.env`
  using a private editor and restrict it to mode 0600. The Compose file passes
  it at runtime. Run `docker compose up -d --build`; the player is on port 8155.
- **Home Assistant OS:** See the add-on README in the companion ZIP.

For upgrades, stop the old server and back up the database and configuration.
Preserve your database path or Docker data volume and keep existing media paths.
Extract the new source separately or replace the old source with the server
stopped. Install dependencies again or rebuild the container.

## Provision Admin

From the extracted `server` folder on a trusted computer:

```sh
python3 -m analog_tv.auth.provision auth.env.new operator https://tv.example.com
```

Use the exact origin you will open in your browser (include a nondefault port;
omit trailing slash and path). Enter a unique password of at least 16
characters at the hidden prompts. The command creates a mode-0600 file
containing a salted scrypt verifier and a random signing key. It refuses to
overwrite an existing file. Keep the file private, including in backups.

Standalone: rename the file to `auth.env` in the server working directory.
Docker: use the private `.env` as described above. Home Assistant: place it
at `/addon_configs/local_analog_tv/auth.env` on the host. Restart and visit
`https://tv.example.com/admin`.

### Migrate from Google Admin or rotate a password

Generate a fresh file, then replace the old authentication settings with the
generated ones. Remove `ANALOG_ADMIN_EMAIL` and `ANALOG_GOOGLE_*` entries and
any stale overrides in your service environment; preserve unrelated settings.
Google credentials cannot be converted to a local password. You do not need
to modify the database. Restart to apply changes; old Admin sessions are
invalidated. If the old Google OAuth client was dedicated to Admin, you can
retire it separately.

### HTTPS and login behavior

Put the server behind an HTTPS reverse proxy with a browser-trusted certificate.
A private HTTPS hostname on your LAN works; no public tunnel is required.
Redirect HTTP to HTTPS on the proxy and restrict backend access to the proxy
where practical. The proxy must send `X-Forwarded-Proto: https`. Configure
Uvicorn's `FORWARDED_ALLOW_IPS` environment variable with the exact proxy
address if it is not loopback; use only trusted proxy addresses. In Docker,
pass this variable through the container environment. In HA, use the add-on's
`trusted_proxy_ip` option. Keep `ANALOG_COOKIE_SECURE=true`. Only for local development,
provision an HTTP loopback origin such as `http://localhost:8080` and bind
the server to loopback with `ANALOG_HOST=127.0.0.1`.

Incomplete or invalid authentication settings lock Admin while playback
continues. The browser sends a login CSRF token and exact Origin; Admin writes
and sign-out require the session CSRF header. There is one active Admin
session, which expires after eight hours or ends on logout, replacement login
or restart. Run one server process: sessions and limits are kept in memory.
Login verification is limited to five attempts per client address and 30
across the server per minute, with one password check at a time. Clients
behind a proxy may share one limit. Do not trust forwarded client headers
from arbitrary peers. Avoid logging request bodies at the proxy.

Anyone who can reach the player can see the public channels and feeds. If
that audience should be limited, restrict network access to the whole service.

Run offline regression tests after installing dependencies: `python -m pytest -q`.
